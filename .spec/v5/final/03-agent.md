# V5 Agent 重构 SPEC

> 可执行规格文档 — 2026-03-29

---

## 1. 概述

### 1.1 目标

将 V4 的 Agent 类（1457 行单体）迁移到独立 Worker 进程，主要变化：
- 进程内 Agent → 独立 Worker 进程
- 存储层：SQLite/JSONL → SeekDB
- EventBus：内存 → ZeroMQ
- **保留 V4 ReAct 架构**

### 1.2 设计原则

- **不过度设计**：保留 V4 的核心架构
- **完全重构**：不考虑兼容性
- **自主记忆简化**：只保留主动写入，去掉 tick 反思

---

## 2. Agent 架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      AgentWorker                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                      Agent                           │   │
│  │  - ToolRegistry (16 工具)                            │   │
│  │  - ContextManager (滑动窗口)                         │   │
│  │  - LLMProvider (LLM 调用)                            │   │
│  │  - _process_event_with_llm() (ReAct loop)           │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              ZeroMQ Layer                            │   │
│  │  - DEALER (点对点消息)                               │   │
│  │  - SUB (广播消息)                                    │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Persistence Layer                       │   │
│  │  - TapeRepository                                    │   │
│  │  - SegmentRepository                                 │   │
│  │  - GameStateRepository                               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 保留 V4 架构的原因

1. **Tape 管理**：自定义 loop 能完整控制 tape 写入时机
2. **成熟稳定**：V4 ReAct 已验证可用
3. **工具控制**：灵活的工具调用和结果处理
4. **迁移成本**：减少学习新框架的成本

---

## 3. Agent 类设计

### 3.1 类结构

```python
class Agent:
    """V5 Agent，保留 V4 ReAct 架构。"""
    
    def __init__(
        self,
        agent_id: str,
        config: AgentConfig,
        seekdb: SeekDBClient,
        mq_dealer: MQDealer,
        mq_publisher: MQPublisher
    ):
        self.agent_id = agent_id
        self.config = config
        
        # 外部依赖
        self._seekdb = seekdb
        self._mq_dealer = mq_dealer
        self._mq_publisher = mq_publisher
        
        # V4 组件
        self._tool_registry = ToolRegistry(self)
        self._llm_provider = LLMProvider(config.llm)
        
        # 权限
        self._permissions = PermissionChecker(config.permissions)
        
        # ContextManager（每个 session 一个实例）
        self._context_managers: dict[str, ContextManager] = {}
    
    async def handle_event(self, event: Event) -> Event:
        """处理点对点事件。"""
        # 获取或创建 ContextManager
        ctx = await self._get_context_manager(event.session_id)
        
        # 添加事件到 tape
        await ctx.add_event(event)
        
        # ReAct loop
        return await self._process_event_with_llm(event, ctx)
    
    async def handle_broadcast(self, event: Event) -> None:
        """处理广播事件（tick）。"""
        # tick 事件不触发 LLM，只更新内部状态
        if event.event_type == "TICK_COMPLETED":
            self._current_tick = event.payload["tick"]
```

### 3.2 ReAct Loop（保留 V4）

```python
async def _process_event_with_llm(
    self, 
    event: Event, 
    ctx: ContextManager
) -> Event:
    """V4 ReAct loop，存储迁移到 SeekDB。"""
    max_iterations = 10
    
    for iteration in range(max_iterations):
        # 1. 获取 LLM messages（滑动窗口 + 摘要）
        messages = await ctx.get_llm_messages()
        
        # 2. 调用 LLM
        response = await self._llm_provider.call_with_functions(
            functions=self._tool_registry.get_functions(),
            messages=messages,
            temperature=0.7
        )
        
        # 3. 处理 tool_calls
        if response.tool_calls:
            for tool_call in response.tool_calls:
                # 执行工具
                result = await self._tool_registry.dispatch(
                    tool_call.name,
                    tool_call.args,
                    event,
                    ctx
                )
                
                # 写入 tape
                await self._write_tool_result(
                    ctx.session_id, 
                    tool_call.name, 
                    result
                )
                
                # 更新 ContextManager
                await ctx.add_observation(
                    tool_name=tool_call.name,
                    result=result
                )
                
                # 检查是否需要结束
                if tool_call.name == "finish_loop":
                    return await self._build_response(event, result)
            
            continue  # 继续 ReAct loop
        
        # 4. 文本响应，结束 loop
        return await self._build_response(event, response.text)
    
    # 超过最大迭代次数
    return await self._build_error_response(event, "max_iterations_exceeded")
```

### 3.3 ContextManager（SeekDB 版本）

```python
class ContextManager:
    """滑动窗口上下文管理，存储在 SeekDB。"""
    
    def __init__(
        self,
        session_id: str,
        agent_id: str,
        tape_repo: TapeRepository,
        segment_repo: SegmentRepository,
        embedding_service: EmbeddingService
    ):
        self.session_id = session_id
        self.agent_id = agent_id
        
        self._tape_repo = tape_repo
        self._segment_repo = segment_repo
        self._embedding_service = embedding_service
        
        # 内存缓存
        self._events: list[Event] = []
        self._summary: str | None = None
        self._window_offset: int = 0
    
    async def load(self) -> None:
        """从 SeekDB 加载。"""
        # 获取会话元数据
        session = await self._tape_repo.get_session(self.session_id)
        if session:
            self._window_offset = session["window_offset"]
            self._summary = session["summary"]
        
        # 加载事件（从 offset 开始）
        events = await self._tape_repo.load_events(
            self.session_id, 
            self.agent_id, 
            self._window_offset
        )
        self._events = [self._parse_event(e) for e in events]
    
    async def add_event(self, event: Event) -> None:
        """添加事件并写入 SeekDB。"""
        self._events.append(event)
        await self._tape_repo.append_event(event)
        
        # 检查是否需要压缩
        await self._maybe_compact()
    
    async def add_observation(self, tool_name: str, result: str) -> None:
        """添加工具执行结果。"""
        event = Event(
            event_id=str(uuid4()),
            event_type="OBSERVATION",
            src=self.agent_id,
            dst=[self.agent_id],
            session_id=self.session_id,
            payload={"tool": tool_name, "result": result}
        )
        await self.add_event(event)
    
    async def get_llm_messages(self) -> list[dict]:
        """获取 LLM 消息列表（system + summary + events）。"""
        messages = []
        
        # System prompt
        messages.append({
            "role": "system",
            "content": await self._get_system_prompt()
        })
        
        # 累积摘要
        if self._summary:
            messages.append({
                "role": "system",
                "content": f"[历史摘要]\n{self._summary}"
            })
        
        # 事件
        for event in self._events:
            messages.extend(self._event_to_messages(event))
        
        return messages
```

### 3.4 滑动窗口压缩

```python
async def _maybe_compact(self) -> None:
    """检查并执行滑动窗口压缩。"""
    # 计算当前 token
    total_tokens = self._count_tokens()
    threshold = MAX_TOKENS * 0.95  # 95%
    
    # 检查触发条件
    if total_tokens < threshold and len(self._events) <= KEEP_RECENT_EVENTS:
        return
    
    # 执行压缩
    await self._slide_window()

async def _slide_window(self) -> None:
    """滑动窗口压缩。"""
    # 1. 识别锚点事件（保留）
    anchor_indices = self._find_anchor_events()
    
    # 2. 计算要丢弃的事件
    dropped_events = self._select_dropped_events(anchor_indices)
    if not dropped_events:
        return
    
    # 3. 生成段摘要
    summary = await self._summarize_events(dropped_events)
    
    # 4. 更新累积摘要
    self._summary = await self._update_cumulative_summary(summary)
    
    # 5. 异步写入向量索引
    asyncio.create_task(self._index_segment(
        start_pos=self._window_offset,
        end_pos=self._window_offset + len(dropped_events),
        summary=summary
    ))
    
    # 6. 更新内存和 offset
    self._events = self._events[len(dropped_events):]
    self._window_offset += len(dropped_events)
    
    # 7. 更新 SeekDB
    await self._tape_repo.update_window_offset(
        self.session_id,
        self._window_offset,
        self._summary
    )
```

---

## 4. 工具体系

### 4.1 工具清单（16 个）

| 类别 | 工具 | Handler 类 | V5 变化 |
|------|------|------------|---------|
| Query | query_province_data | QueryTools | SeekDB 查询 + 权限检查 |
| Query | query_national_data | QueryTools | SeekDB 查询 |
| Query | list_provinces | QueryTools | SeekDB 查询 |
| Query | list_agents | QueryTools | SeekDB 查询 |
| Query | get_agent_info | QueryTools | SeekDB 查询 |
| Query | query_incidents | QueryTools | SeekDB 查询 |
| Memory | retrieve_memory | MemoryTools | SeekDB VECTOR 搜索 |
| Memory | write_memory | MemoryTools | 写 tape_events |
| Action | send_message | ActionTools | ZeroMQ 发布 |
| Action | finish_loop | ActionTools | 无变化 |
| Action | create_incident | ActionTools | ZeroMQ → Engine |
| Action | update_soul | ActionTools | 更新 agent_config |
| Session | create_task_session | TaskSessionTools | SeekDB 写入 |
| Session | finish_task_session | TaskSessionTools | SeekDB 更新 |
| Session | fail_task_session | TaskSessionTools | SeekDB 更新 |

### 4.2 ToolRegistry

```python
class ToolRegistry:
    """V4 ToolRegistry，保留原有架构。"""
    
    def __init__(self, agent: Agent):
        self._agent = agent
        self._tools: dict[str, Tool] = {}
        self._handlers: dict[str, Callable] = {}
        
        # 初始化 handler 类
        self._query_tools = QueryTools(agent)
        self._action_tools = ActionTools(agent)
        self._memory_tools = MemoryTools(agent)
        self._session_tools = TaskSessionTools(agent)
        
        # 注册工具
        self._register_all_tools()
    
    def get_functions(self) -> list[dict]:
        """获取 OpenAI function calling 格式的工具列表。"""
        return [tool.to_openai_schema() for tool in self._tools.values()]
    
    async def dispatch(
        self, 
        name: str, 
        args: dict, 
        event: Event,
        ctx: ContextManager
    ) -> str:
        """分发工具调用。"""
        handler = self._handlers.get(name)
        if not handler:
            return f"Unknown tool: {name}"
        
        try:
            return await handler(args, event, ctx)
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            return f"Tool execution failed: {str(e)}"
```

### 4.3 关键工具实现

**query_province_data（SeekDB + 权限）：**

```python
async def query_province_data(
    self, 
    args: dict, 
    event: Event,
    ctx: ContextManager
) -> str:
    province_id = args.get("province_id")
    field = args.get("field")
    
    # 权限检查
    if not self._agent._permissions.has_tool_permission(
        "query_province_data", province_id
    ):
        return f"无权限查询省份 {province_id}"
    
    # 查询 SeekDB
    data = await self._agent._seekdb.get_province(province_id)
    if not data:
        return f"省份 {province_id} 不存在"
    
    # 返回指定字段或全部
    if field:
        return str(data.get(field, f"字段 {field} 不存在"))
    return json.dumps(data, ensure_ascii=False, indent=2)
```

**send_message（ZeroMQ）：**

```python
async def send_message(
    self, 
    args: dict, 
    event: Event,
    ctx: ContextManager
) -> str:
    target = args.get("target")
    message = args.get("message")
    
    # 构建事件
    msg_event = Event(
        event_id=str(uuid4()),
        event_type="AGENT_MESSAGE",
        src=f"agent:{self._agent.agent_id}",
        dst=[f"agent:{target}"],
        session_id=event.session_id,
        payload={"message": message}
    )
    
    # 通过 ZeroMQ 发送
    await self._agent._mq_dealer.send(msg_event.to_json())
    
    return f"消息已发送给 {target}"
```

**create_incident（ZeroMQ → Engine）：**

```python
async def create_incident(
    self, 
    args: dict, 
    event: Event,
    ctx: ContextManager
) -> str:
    incident_type = args.get("incident_type")
    title = args.get("title")
    description = args.get("description", "")
    severity = args.get("severity", "medium")
    duration = args.get("duration", 4)  # tick 数
    
    # 构建事件
    incident_event = Event(
        event_id=str(uuid4()),
        event_type="INCIDENT_CREATED",
        src=f"agent:{self._agent.agent_id}",
        dst=["engine:*"],
        session_id=event.session_id,
        payload={
            "incident_type": incident_type,
            "title": title,
            "description": description,
            "severity": severity,
            "duration": duration
        }
    )
    
    # 发送给 Engine
    await self._agent._mq_dealer.send(incident_event.to_json())
    
    return f"Incident '{title}' 已创建"
```

**retrieve_memory（SeekDB VECTOR）：**

```python
async def retrieve_memory(
    self, 
    args: dict, 
    event: Event,
    ctx: ContextManager
) -> str:
    query = args.get("query")
    max_results = args.get("max_results", 5)
    
    # 计算 query embedding
    query_embedding = await self._embedding_service.embed(query)
    
    # 向量搜索
    results = await self._segment_repo.search_similar(
        query_embedding=query_embedding,
        agent_id=self._agent.agent_id,
        limit=max_results
    )
    
    if not results:
        return "未找到相关记忆"
    
    # 格式化结果
    output = []
    for r in results:
        output.append(f"- [{r['session_id']}] {r['summary']}")
    
    return "\n".join(output)
```

---

## 5. Worker 生命周期

### 5.1 AgentManager

```python
class AgentManager:
    """管理 Agent 的创建、修改、删除。"""
    
    def __init__(
        self, 
        seekdb: SeekDBClient,
        router_addr: str,
        broadcast_addr: str
    ):
        self._seekdb = seekdb
        self._router_addr = router_addr
        self._broadcast_addr = broadcast_addr
        self._workers: dict[str, subprocess.Popen] = {}
    
    async def create_agent(self, config: AgentConfig) -> None:
        """创建 Agent。"""
        # 1. 写入 agent_config
        await self._seekdb.execute("""
            INSERT INTO agent_config 
            (agent_id, role_name, soul_text, skills, permissions, is_active)
            VALUES (?, ?, ?, ?, ?, TRUE)
        """, config.agent_id, config.role_name, config.soul_text,
            json.dumps(config.skills), json.dumps(config.permissions))
        
        # 2. 启动 Worker 进程
        process = subprocess.Popen(
            [
                sys.executable, "-m", "simu_emperor.worker",
                "--agent-id", config.agent_id,
                "--router", self._router_addr,
                "--broadcast", self._broadcast_addr
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        self._workers[config.agent_id] = process
        logger.info(f"Agent {config.agent_id} created, PID: {process.pid}")
    
    async def update_agent(self, agent_id: str, updates: dict) -> None:
        """更新 Agent 配置。"""
        # 1. 更新 agent_config
        set_clauses = []
        args = []
        for key, value in updates.items():
            if key in ('skills', 'permissions'):
                value = json.dumps(value)
            set_clauses.append(f"{key} = ?")
            args.append(value)
        args.append(agent_id)
        
        await self._seekdb.execute(
            f"UPDATE agent_config SET {', '.join(set_clauses)} WHERE agent_id = ?",
            *args
        )
        
        # 2. 重启 Worker（它会重新加载配置）
        if agent_id in self._workers:
            self._workers[agent_id].terminate()
            self._workers[agent_id].wait()
        
        config = await self._load_config(agent_id)
        await self.create_agent(config)
    
    async def delete_agent(self, agent_id: str) -> None:
        """删除 Agent。"""
        # 1. 停止 Worker
        if agent_id in self._workers:
            self._workers[agent_id].terminate()
            self._workers[agent_id].wait()
            del self._workers[agent_id]
        
        # 2. 删除配置
        await self._seekdb.execute(
            "DELETE FROM agent_config WHERE agent_id = ?", agent_id
        )
        logger.info(f"Agent {agent_id} deleted")
    
    async def list_agents(self) -> list[dict]:
        """列出所有 Agent。"""
        return await self._seekdb.fetch_all(
            "SELECT * FROM agent_config WHERE is_active = TRUE"
        )
```

### 5.2 Worker 进程入口

```python
# src/simu_emperor/worker/main.py

async def main(
    agent_id: str,
    router_addr: str,
    broadcast_addr: str
):
    # 1. 初始化 SeekDB
    seekdb = await create_db_pool()
    agent_config_repo = AgentConfigRepository(seekdb)
    
    # 2. 加载 Agent 配置
    config = await agent_config_repo.get(agent_id)
    if not config:
        logger.error(f"Agent {agent_id} not found")
        return
    
    # 3. 初始化 ZeroMQ
    dealer = MQDealer(router_addr)
    subscriber = MQSubscriber(broadcast_addr)
    publisher = MQPublisher(broadcast_addr)  # 用于 send_message
    
    await dealer.connect()
    await subscriber.connect()
    await subscriber.subscribe("")
    
    # 4. 注册到 Router
    await dealer.send(json.dumps({
        "type": "REGISTER",
        "agent_id": agent_id
    }))
    
    # 5. 创建 Agent
    agent = Agent(
        agent_id=agent_id,
        config=AgentConfig.from_dict(config),
        seekdb=seekdb,
        mq_dealer=dealer,
        mq_publisher=publisher
    )
    
    # 6. 事件循环
    logger.info(f"Worker started for agent {agent_id}")
    await asyncio.gather(
        _receive_loop(agent, dealer),
        _broadcast_loop(agent, subscriber)
    )

async def _receive_loop(agent: Agent, dealer: MQDealer):
    """点对点消息循环。"""
    while True:
        data = await dealer.receive()
        try:
            event = Event.from_json(data)
            response = await agent.handle_event(event)
            await dealer.send(response.to_json())
        except Exception as e:
            logger.error(f"Error handling event: {e}")
            await dealer.send(json.dumps({
                "event_id": event.event_id if 'event' in locals() else "unknown",
                "event_type": "ERROR",
                "payload": {"error": str(e)}
            }))

async def _broadcast_loop(agent: Agent, subscriber: MQSubscriber):
    """广播消息循环。"""
    while True:
        topic, data = await subscriber.receive()
        try:
            event = Event.from_json(data)
            await agent.handle_broadcast(event)
        except Exception as e:
            logger.error(f"Error handling broadcast: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--router", default="ipc://@simu_router")
    parser.add_argument("--broadcast", default="ipc://@simu_broadcast")
    args = parser.parse_args()
    
    asyncio.run(main(args.agent_id, args.router, args.broadcast))
```

---

## 6. GroupChat

### 6.1 设计

利用 Event.dst 多目标支持，无需额外表或服务。

### 6.2 使用方式

```python
# Agent 发送群聊消息
event = Event(
    event_id=str(uuid4()),
    event_type="AGENT_MESSAGE",
    src="agent:governor",
    dst=["agent:minister1", "agent:minister2", "agent:minister3"],
    session_id=session_id,
    payload={"message": "诸位，今年税收情况如何？"}
)

# Router 会遍历 dst，发送给每个目标
```

### 6.3 Router 多播处理

```python
# 在 Router.route() 中
for dst in event.dst:
    if dst.startswith("agent:"):
        agent_id = dst[6:]
        worker_identity = self._routing_table.get(agent_id)
        if worker_identity:
            await self._send_to_worker(worker_identity, event)
```

---

## 7. Task Session

### 7.1 数据库表

见 `02-persistence.md` 中的 `task_sessions` 表。

### 7.2 TaskSessionTools

```python
class TaskSessionTools:
    def __init__(self, agent: Agent):
        self._agent = agent
    
    async def create_task_session(
        self, 
        args: dict, 
        event: Event,
        ctx: ContextManager
    ) -> str:
        task_type = args.get("task_type")
        timeout = args.get("timeout", 300)
        
        task_id = f"task:{uuid4().hex[:8]}"
        
        await self._agent._seekdb.execute("""
            INSERT INTO task_sessions 
            (task_id, session_id, creator_id, task_type, timeout_seconds, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        """, task_id, event.session_id, self._agent.agent_id, task_type, timeout)
        
        return f"任务会话 {task_id} 已创建"
    
    async def finish_task_session(
        self, 
        args: dict, 
        event: Event,
        ctx: ContextManager
    ) -> str:
        task_id = args.get("task_id")
        result = args.get("result", {})
        
        # 更新状态
        await self._agent._seekdb.execute("""
            UPDATE task_sessions 
            SET status = 'completed', result = ?, completed_at = NOW()
            WHERE task_id = ?
        """, json.dumps(result), task_id)
        
        # 通知创建者
        task = await self._agent._seekdb.fetch_one(
            "SELECT creator_id, session_id FROM task_sessions WHERE task_id = ?",
            task_id
        )
        if task:
            notify_event = Event(
                event_id=str(uuid4()),
                event_type="TASK_FINISHED",
                src=f"agent:{self._agent.agent_id}",
                dst=[f"agent:{task['creator_id']}"],
                session_id=task["session_id"],
                payload={"task_id": task_id, "result": result}
            )
            await self._agent._mq_dealer.send(notify_event.to_json())
        
        return f"任务 {task_id} 已完成"
    
    async def fail_task_session(
        self, 
        args: dict, 
        event: Event,
        ctx: ContextManager
    ) -> str:
        task_id = args.get("task_id")
        error = args.get("error", "Unknown error")
        
        await self._agent._seekdb.execute("""
            UPDATE task_sessions 
            SET status = 'failed', result = ?, completed_at = NOW()
            WHERE task_id = ?
        """, json.dumps({"error": error}), task_id)
        
        # 通知创建者（类似 finish_task_session）
        # ...
        
        return f"任务 {task_id} 已失败"
```

### 7.3 超时监控

由创建者 Worker 在空闲时检查：

```python
class Agent:
    async def _check_task_timeouts(self) -> None:
        """检查超时任务。"""
        expired = await self._seekdb.fetch_all("""
            SELECT * FROM task_sessions 
            WHERE creator_id = ? AND status = 'pending'
            AND TIMESTAMPDIFF(SECOND, created_at, NOW()) > timeout_seconds
        """, self.agent_id)
        
        for task in expired:
            # 标记失败
            await self._seekdb.execute("""
                UPDATE task_sessions 
                SET status = 'failed', result = ?, completed_at = NOW()
                WHERE task_id = ?
            """, json.dumps({"error": "timeout"}), task["task_id"])
            
            # 触发 TASK_TIMEOUT 事件
            # ...
```

---

## 8. System Prompt

### 8.1 分离策略

- **通用指导**：在代码中定义（AgentBuilder）
- **角色特定内容**：从 SeekDB agent_config.soul_text 加载

### 8.2 实现

```python
class AgentBuilder:
    async def build(self, agent_id: str) -> Agent:
        # 1. 从 SeekDB 加载配置
        config = await self._agent_config_repo.get(agent_id)
        
        # 2. 构建完整 system prompt
        system_prompt = self._build_system_prompt(config["soul_text"])
        
        # 3. 创建 Agent
        agent = Agent(agent_id, AgentConfig(
            soul_text=system_prompt,
            permissions=json.loads(config["permissions"]),
            ...
        ))
        
        return agent
    
    def _build_system_prompt(self, soul_text: str) -> str:
        """构建完整 system prompt。"""
        return f"""{soul_text}

## 行为准则

1. 你可以使用工具来查询信息、执行操作
2. 调用工具后，根据结果继续思考和行动
3. 完成任务后，调用 finish_loop 结束

## 工具使用

- 查询数据：优先使用 query_* 工具
- 发送消息：使用 send_message
- 记录重要信息：使用 write_memory
- 创建任务：使用 create_task_session

## 约束

- 不要编造不存在的数据
- 权限不足时，明确告知
- 保持角色一致性
"""
```

---

## 9. 实现清单

### 9.1 文件结构

```
src/simu_emperor/agent/
├── __init__.py
├── agent.py              # Agent 类（保留 V4 架构）
├── context_manager.py    # ContextManager（SeekDB 版本）
├── tool_registry.py      # ToolRegistry
├── tools/
│   ├── __init__.py
│   ├── query.py          # QueryTools
│   ├── action.py         # ActionTools
│   ├── memory.py         # MemoryTools
│   └── session.py        # TaskSessionTools
├── permissions.py        # PermissionChecker
└── builder.py            # AgentBuilder

src/simu_emperor/worker/
├── __init__.py
├── main.py               # Worker 入口
└── manager.py            # AgentManager
```

### 9.2 实现顺序

1. **Phase 1**: Agent 核心
   - agent.py（骨架）
   - context_manager.py（SeekDB 版本）
   - builder.py

2. **Phase 2**: 工具迁移
   - tool_registry.py
   - tools/query.py
   - tools/action.py
   - tools/memory.py
   - tools/session.py

3. **Phase 3**: Worker
   - worker/main.py
   - manager.py

4. **Phase 4**: 权限
   - permissions.py
   - 集成到工具

---

## 10. 测试清单

- [ ] Agent 事件处理
- [ ] ReAct loop（max_iterations）
- [ ] ContextManager 加载/保存
- [ ] 滑动窗口压缩
- [ ] 向量索引写入
- [ ] 16 个工具逐一测试
- [ ] 权限检查
- [ ] Worker 启动/注册
- [ ] AgentManager 创建/更新/删除
- [ ] GroupChat 多播
- [ ] Task Session 创建/完成/超时
- [ ] System prompt 生成
