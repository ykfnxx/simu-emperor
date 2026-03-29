# V5 Event Bus 重构 SPEC

> 可执行规格文档 — 2026-03-29

---

## 1. 概述

### 1.1 目标

将 V4 的单进程内存 EventBus 重构为基于 ZeroMQ 的多进程架构，支持：
- 精确路由（点对点消息）
- 广播（tick 事件）
- Agent 间通信
- 动态 Agent 创建

### 1.2 设计原则

- **不过度设计**：保持简单，满足当前需求
- **完全重构**：不考虑与 V4 的兼容性
- **职责分离**：每个进程单一职责

---

## 2. 进程拓扑

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                         Gateway                              │
│  - HTTP/WS 接入                                              │
│  - ROUTER (bind: ipc://@simu_gateway)                       │
│  - DEALER (connect: ipc://@simu_router)                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                          Router                              │
│  - 精确路由 (dst -> Worker/Engine)                           │
│  - 多播支持 (dst 列表)                                       │
│  - ROUTER (bind: ipc://@simu_router)                        │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │ Worker 1 │    │ Worker 2 │    │ Engine   │
        │(governor)│    │(minister)│    │          │
        │DEALER+SUB│    │DEALER+SUB│    │DEALER+PUB│
        └──────────┘    └──────────┘    └──────────┘
              │               │               │
              └───────────────┴───────────────┘
                              │
                              ▼
                       (PUB broadcast)
```

### 2.2 Socket 配置

| 进程 | Socket 类型 | 地址 | 方向 | 用途 |
|------|-------------|------|------|------|
| Gateway | ROUTER | ipc://@simu_gateway | bind | 接收 HTTP/WS 请求 |
| Gateway | DEALER | ipc://@simu_router | connect | 发送消息到 Router |
| Router | ROUTER | ipc://@simu_router | bind | 接收所有消息 |
| Engine | DEALER | ipc://@simu_router | connect | 接收点对点消息 |
| Engine | PUB | ipc://@simu_broadcast | bind | 广播 tick 事件 |
| Worker | DEALER | ipc://@simu_router | connect | 接收点对点消息 |
| Worker | SUB | ipc://@simu_broadcast | connect | 接收广播消息 |

---

## 3. 消息协议

### 3.1 Event 结构

```python
@dataclass
class Event:
    event_id: str              # UUID，唯一标识
    event_type: str            # 事件类型（见 3.2）
    src: str                   # 发送方 ID，如 "player:web:client_001"
    dst: list[str]             # 目标列表，支持多播
    session_id: str            # 会话 ID
    payload: dict              # 事件内容
    timestamp: str             # ISO 8601 格式
```

### 3.2 事件类型

| 类型 | 发布者 | 说明 |
|------|--------|------|
| CHAT | Gateway | Player 消息 |
| AGENT_MESSAGE | Worker | Agent 消息 |
| OBSERVATION | Worker | 工具执行结果 |
| TICK_COMPLETED | Engine | Tick 完成 |
| INCIDENT_CREATED | Worker | 创建 Incident |
| INCIDENT_EXPIRED | Engine | Incident 过期 |
| TASK_FINISHED | Worker | 任务完成 |
| TASK_FAILED | Worker | 任务失败 |
| TASK_TIMEOUT | Worker | 任务超时 |

### 3.3 目标格式

| dst 格式 | 路由目标 | 示例 |
|----------|----------|------|
| `agent:{agent_id}` | 精确路由到 Worker | `agent:governor_zhili` |
| `engine:*` | 路由到 Engine | `engine:*` |
| `player:{client_id}` | 路由到 Gateway（WebSocket） | `player:web:client_001` |
| 多目标 | 多播到所有目标 | `["agent:minister1", "agent:minister2"]` |

### 3.4 序列化

- 格式：JSON
- 编码：UTF-8

```python
def to_json(self) -> str:
    return json.dumps(asdict(self))

@classmethod
def from_json(cls, data: str) -> "Event":
    return cls(**json.loads(data))
```

---

## 4. Router 设计

### 4.1 路由表

```python
class Router:
    def __init__(self):
        self._routing_table: dict[str, str] = {}
        # agent_id -> worker_identity (ZeroMQ 内部 ID)
```

### 4.2 注册协议

**Worker 注册消息：**

```python
{
    "type": "REGISTER",
    "agent_id": "governor_zhili"
}
```

**Router 处理：**

```python
async def handle_register(self, identity: bytes, msg: dict):
    agent_id = msg["agent_id"]
    self._routing_table[agent_id] = identity
    logger.info(f"Agent registered: {agent_id}")
```

**Worker 注销：**
- ZeroMQ 自动检测连接断开
- Router 从 routing_table 移除对应条目

### 4.3 路由逻辑

```python
async def route(self, event: Event, sender_identity: bytes):
    """路由消息到目标。"""
    for dst in event.dst:
        # 解析目标类型
        if dst.startswith("agent:"):
            agent_id = dst[6:]
            worker_identity = self._routing_table.get(agent_id)
            if worker_identity:
                await self._send_to_worker(worker_identity, event)
            else:
                logger.warning(f"No worker for agent: {agent_id}")
        
        elif dst.startswith("engine:"):
            await self._send_to_engine(event)
        
        elif dst.startswith("player:"):
            # 转发回 Gateway
            await self._send_to_gateway(event)
```

---

## 5. Worker 设计

### 5.1 初始化

```python
class AgentWorker:
    def __init__(self, agent_id: str, config: AgentConfig):
        self.agent_id = agent_id
        self.config = config
        
        # ZeroMQ
        self.dealer = MQDealer("ipc://@simu_router")
        self.subscriber = MQSubscriber("ipc://@simu_broadcast")
        
        # Agent
        self.agent = Agent(agent_id, config)
    
    async def start(self):
        # 1. 连接 Router
        await self.dealer.connect()
        
        # 2. 注册
        await self.dealer.send(json.dumps({
            "type": "REGISTER",
            "agent_id": self.agent_id
        }))
        
        # 3. 连接广播
        await self.subscriber.connect()
        await self.subscriber.subscribe("")  # 接收所有广播
        
        # 4. 启动事件循环
        await asyncio.gather(
            self._receive_loop(),
            self._broadcast_loop()
        )
```

### 5.2 事件循环

```python
async def _receive_loop(self):
    """处理点对点消息。"""
    while True:
        data = await self.dealer.receive()
        event = Event.from_json(data)
        response = await self.agent.handle_event(event)
        await self.dealer.send(response.to_json())

async def _broadcast_loop(self):
    """处理广播消息（tick）。"""
    while True:
        topic, data = await self.subscriber.receive()
        event = Event.from_json(data)
        await self.agent.handle_broadcast(event)
```

---

## 6. Engine 设计

### 6.1 职责

- 游戏状态管理（tick 推进、经济计算）
- 处理来自 Agent 的 Incident
- 广播 TICK_COMPLETED 事件

### 6.2 初始化

```python
class Engine:
    def __init__(self):
        self.dealer = MQDealer("ipc://@simu_router")
        self.publisher = MQPublisher("ipc://@simu_broadcast")
        self.game_state = GameState()
    
    async def start(self):
        await self.dealer.connect()
        await self.publisher.bind()
        
        # 注册
        await self.dealer.send(json.dumps({
            "type": "REGISTER",
            "agent_id": "engine:*"
        }))
        
        await asyncio.gather(
            self._receive_loop(),
            self._tick_loop()
        )
```

### 6.3 Tick 广播

```python
async def _tick_loop(self):
    """定时推进 tick 并广播。"""
    while True:
        await asyncio.sleep(5)  # 5 秒 = 1 tick
        
        self.game_state.tick += 1
        await self.game_state.calculate()
        
        # 广播
        event = Event(
            event_id=str(uuid4()),
            event_type="TICK_COMPLETED",
            src="engine:*",
            dst=["broadcast:*"],
            session_id="system",
            payload={"tick": self.game_state.tick},
            timestamp=datetime.now().isoformat()
        )
        await self.publisher.publish("tick", event.to_json())
```

---

## 7. Gateway 设计

### 7.1 职责

- HTTP/WS 接入
- 消息格式转换
- WebSocket 推送给 Player

### 7.2 WebSocket 处理

```python
class Gateway:
    def __init__(self):
        self.router = MQRouter("ipc://@simu_gateway")
        self.dealer = MQDealer("ipc://@simu_router")
        self.ws_clients: dict[str, WebSocket] = {}  # client_id -> WebSocket
    
    async def handle_ws_message(self, client_id: str, message: str):
        """处理 WebSocket 消息。"""
        # 解析并构建 Event
        event = Event(
            event_id=str(uuid4()),
            event_type="CHAT",
            src=f"player:web:{client_id}",
            dst=["agent:governor_zhili"],  # 根据消息内容确定
            session_id=f"session:web:{client_id}",
            payload={"message": message},
            timestamp=datetime.now().isoformat()
        )
        
        # 发送到 Router
        await self.dealer.send(event.to_json())
        
        # 等待响应（超时 30 秒）
        try:
            response = await asyncio.wait_for(
                self.dealer.receive(),
                timeout=30.0
            )
            return Event.from_json(response)
        except asyncio.TimeoutError:
            return {"error": "timeout"}
```

---

## 8. 错误处理

### 8.1 超时处理

**发送方负责超时：**

```python
async def send_with_timeout(event: Event, timeout: float = 30.0) -> Event:
    await dealer.send(event.to_json())
    try:
        response = await asyncio.wait_for(dealer.receive(), timeout=timeout)
        return Event.from_json(response)
    except asyncio.TimeoutError:
        return Event(
            event_id=event.event_id,
            event_type="ERROR",
            payload={"error": "timeout"},
            ...
        )
```

### 8.2 错误响应格式

```python
# Worker 处理失败时返回
{
    "event_id": "xxx",
    "event_type": "ERROR",
    "payload": {
        "error": "LLM call failed",
        "details": "Connection timeout"
    }
}
```

### 8.3 广播丢失处理

- **投递语义**：at-most-once
- **可接受**：tick 事件丢失可接受（下一个 tick 会来）
- **关键事件**：AGENT_MESSAGE 等关键事件通过点对点发送，有响应确认

---

## 9. 实现清单

### 9.1 文件结构

```
src/simu_emperor/mq/
├── __init__.py
├── event.py           # Event 数据类
├── router.py          # MQRouter, Router
├── dealer.py          # MQDealer
├── publisher.py       # MQPublisher
├── subscriber.py      # MQSubscriber
└── gateway.py         # Gateway

src/simu_emperor/worker/
├── __init__.py
├── main.py            # Worker 入口
└── agent_worker.py    # AgentWorker

src/simu_emperor/engine/
├── __init__.py
└── main.py            # Engine 入口
```

### 9.2 实现顺序

1. **Phase 1**: ZeroMQ 封装层
   - event.py
   - dealer.py
   - publisher.py
   - subscriber.py

2. **Phase 2**: Router
   - router.py
   - 注册协议
   - 路由逻辑

3. **Phase 3**: Worker 框架
   - agent_worker.py
   - 事件循环

4. **Phase 4**: Engine
   - main.py
   - tick 广播

5. **Phase 5**: Gateway
   - gateway.py
   - WebSocket 集成

---

## 10. 测试清单

- [ ] Router 注册/注销
- [ ] 点对点消息路由
- [ ] 多播消息（dst 列表）
- [ ] 广播消息（tick）
- [ ] 超时处理
- [ ] 错误响应
- [ ] Worker 重启后重新注册
- [ ] Engine 故障恢复
