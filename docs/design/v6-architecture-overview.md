# V6 版本迭代设计方案

## 设计目标

1. **彻底解耦**：Agent 与 Server 通过 MCP 协议交互，不再内嵌 Server 调用
2. **Agent Core 统一**：采用 Bub 作为无状态 Runtime Core，状态管理通过 Plugin 实现
3. **Session 状态机**：将 task/reply 阻塞机制沉淀为通用的 Session 状态管理
4. **Server 通用化**：支持多种 Agent 类型，以 Claude Code 接入为验证
5. **长期演进**：Server 核心逐步使用 Rust 重写，提升性能

---

## 1. 整体架构

### 1.1 V5 → V6 架构变化

```
V5                                        V6
┌──────────────────────┐                 ┌──────────────────────┐
│  BaseAgent (SDK)     │                 │  SimuAgent           │
│  ┌────────────────┐  │                 │  ┌────────────────┐  │
│  │ on_event()     │  │                 │  │ on_event()     │  │
│  │ (状态判断+分派) │  │                 │  │ (状态机判断)    │  │
│  ├────────────────┤  │                 │  ├────────────────┤  │
│  │ react()        │  │      ───►       │  │ Bub Core       │  │
│  │ ReActLoop      │  │                 │  │ (无状态管线)    │  │
│  ├────────────────┤  │                 │  ├────────────────┤  │
│  │ StandardTools  │  │                 │  │ Plugins        │  │
│  │ (ServerClient) │  │                 │  │ (Hooks)        │  │
│  └────────────────┘  │                 │  ├────────────────┤  │
│                      │                 │  │ MCP Clients    │  │
└──────────────────────┘                 └──────────────────────┘
         │                                        │
    HTTP callbacks                           MCP Protocol
         ▼                                        ▼
┌──────────────────────┐                 ┌──────────────────────┐
│  FastAPI Server      │                 │  MCP Server Layer    │
│  (REST API)          │      ───►       │  (JSON-RPC)          │
└──────────────────────┘                 └──────────────────────┘
```

### 1.2 分层架构

```
┌─────────────────────────────────────────────────────────────────┐
│                       SimuAgent（编排层）                         │
│  on_event() → SessionStateManager → framework.process_inbound() │
│  状态机：IDLE / BLOCKED / DRAINING                                │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    Bub Framework Core（无状态）                    │
│  resolve_session → load_state → build_prompt → run_model        │
│  → save_state → render_outbound → dispatch_outbound             │
└───────────────────────────┬─────────────────────────────────────┘
                            │ hook 调用
┌───────────────────────────▼─────────────────────────────────────┐
│                       Plugins（状态 + 逻辑）                      │
│                                                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ SimuTapePlugin  │  │ SimuContextPlugin│  │ SimuReActPlugin │  │
│  │ load/save tape  │  │ build context    │  │ LLM + tool loop │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│                                                                   │
│  ┌─────────────────┐  ┌─────────────────┐                       │
│  │ MCPClientPlugin │  │ SimuMemoryPlugin│                       │
│  │ MCP tool 调用    │  │ 向量检索/存储    │                       │
│  └─────────────────┘  └─────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
                            │ MCP Protocol
┌───────────────────────────▼─────────────────────────────────────┐
│                    MCP Server Layer                               │
│                                                                   │
│  ┌─────────────────┐  ┌─────────────────┐                       │
│  │  simu-mcp       │  │  role-mcp       │                       │
│  │  query_state    │  │  query_role_map │                       │
│  │  create_incident│  │  get_agents     │                       │
│  │  send_message   │  │                 │                       │
│  └─────────────────┘  └─────────────────┘                       │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    SSE 事件推送通道                           │ │
│  │  Server → Agent 的消息推送（保留，MCP 不替代）                  │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    Server Core                                    │
│  Game Engine / Event Router / Queue Controller / Session Manager  │
│  （Phase 1: Python/FastAPI  →  Phase 2+: 逐步 Rust 重写）         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Agent 重构设计

### 2.1 Bub 作为无状态 Runtime Core

Bub 仅负责 hook 管线编排，不持有任何状态：

```python
# Bub Core — 无状态管线（~200 行）
class BubFramework:
    async def process_inbound(self, inbound: Envelope) -> TurnResult:
        session_id = await hooks.call_first("resolve_session", message=inbound)
        state = await hooks.call_many("load_state", message=inbound, session_id=session_id)
        prompt = await hooks.call_first("build_prompt", message=inbound, session_id=session_id, state=state)
        model_output = await hooks.call_first("run_model", prompt=prompt, session_id=session_id, state=state)
        await hooks.call_many("save_state", session_id=session_id, state=state, model_output=model_output)
        outbounds = await self._collect_outbounds(inbound, session_id, state, model_output)
        return TurnResult(session_id=session_id, prompt=prompt, model_output=model_output, outbounds=outbounds)
```

**关键设计决策：Bub Core 零改动。**

状态管理（session 阻塞、task 嵌套、消息队列）在 Bub 管线**之外**处理，由 SimuAgent 编排层负责。Bub 管线只处理确定要执行 ReAct 的事件。

### 2.2 SimuAgent 编排层 — Session 状态机

Session 状态机管理事件的分派，在调用 `process_inbound` 之前完成判断：

```python
class SimuAgent:
    def __init__(self):
        self._framework = BubFramework()  # 无状态 core
        self._session_mgr = SessionStateManager()  # 状态管理
    
    async def on_event(self, event: TapeEvent):
        session = self._session_mgr.get_or_create(event.session_id)
        
        # 1. 解阻塞事件（task 完成 / reply 到达）
        if self._session_mgr.try_resolve(session, event):
            if session.is_idle():
                await self._drain_queue(session)
            return
        
        # 2. session 被阻塞 → 入队
        if session.is_blocked():
            session.message_queue.append(event)
            return
        
        # 3. session 空闲 → 进入 Bub 管线
        await self._framework.process_inbound(Envelope(payload=event))
    
    async def _drain_queue(self, session: SessionState):
        """逐条消费队列，每条经过完整 process_inbound"""
        while session.message_queue and session.is_idle():
            event = session.message_queue.popleft()
            await self._framework.process_inbound(Envelope(payload=event))
```

### 2.3 Session 状态机模型

```
                    ┌──────────────┐
                    │   IDLE       │  ← 正常处理事件，进入 Bub 管线
                    │  (无阻塞)    │
                    └──────┬───────┘
                           │ create_task / send_message(await_reply)
                           ▼
                    ┌──────────────┐
                    │  BLOCKED     │  ← 新事件入消息队列，不进管线
                    │  (等待完成)   │
                    └──────┬───────┘
                           │ task_finished / reply_received
                           │
                    ┌──────┴───────┐
                    │ 还有未完成    │──► 保持 BLOCKED
                    │ task/reply?  │
                    └──────┬───────┘
                           │ 全部完成
                           ▼
                    ┌──────────────┐
                    │  DRAINING    │  ← 逐条消费消息队列
                    │  (消费队列)   │     每条经过完整 process_inbound
                    └──────┬───────┘     （可能重新进入 BLOCKED）
                           │ 队列清空
                           ▼
                    ┌──────────────┐
                    │   IDLE       │
                    └──────────────┘
```

**状态数据结构：**

```python
@dataclass
class SessionState:
    session_id: str
    status: Literal["idle", "blocked", "draining"]
    pending_tasks: set[str]           # 未完成的 task session IDs
    pending_replies: dict[str, str]   # msg_id → awaiting_from
    message_queue: deque[TapeEvent]   # 阻塞期间收到的事件
    parent_id: str | None = None      # 父 session（task session 才有）
    depth: int = 0                    # 嵌套深度（最大 5）
    goal: str = ""                    # task 目标
```

**状态派生规则：**
- `pending_tasks` 或 `pending_replies` 非空 → `blocked`
- 两者都为空且 `message_queue` 非空 → `draining`
- 两者都为空且 `message_queue` 为空 → `idle`

### 2.4 Plugin 设计

#### SimuTapePlugin — Tape 读写

```python
class SimuTapePlugin:
    @hookimpl
    async def load_state(self, message, session_id) -> SimuTurnState:
        tape = await self._tape_mgr.query(session_id)
        return SimuTurnState(session_id=session_id, tape_events=tape)
    
    @hookimpl
    async def save_state(self, session_id, state, model_output):
        await self._tape_mgr.append(state.response_event)
        # 如果产生了新 task session，触发子 session 处理
        if state.new_task_session:
            parent = self._session_mgr.get(session_id)
            parent.pending_tasks.add(state.new_task_session.id)
            self._session_mgr.register_task_session(state.new_task_session)
            task_event = self._build_task_event(state.new_task_session)
            await self._agent.on_event(task_event)  # 重入 on_event
```

#### SimuContextPlugin — 上下文构建

```python
class SimuContextPlugin:
    @hookimpl
    async def load_state(self, message, session_id) -> dict:
        context = await self._context_mgr.get_context(session_id)
        return {"context_window": context}
    
    @hookimpl
    async def build_prompt(self, message, session_id, state) -> str:
        parts = [self._soul]
        if self._data_scope:
            parts.append(self._format_data_scope())
            parts.append(self._action_execution_instructions())
        parts.append(self._session_instructions(session_id))
        return "\n\n".join(parts)
```

#### SimuReActPlugin — ReAct 循环

```python
class SimuReActPlugin:
    @hookimpl
    async def run_model(self, prompt, session_id, state) -> str:
        """Bub 的一次 turn = 一次完整的 ReAct 循环"""
        tools = state.available_tools
        messages = state.context_window.messages
        
        for iteration in range(self._max_iterations):
            response = await self._llm.call(messages, tools)
            if response.has_tool_calls:
                for tc in response.tool_calls:
                    result = await self._execute_tool(tc, state)
                    if result.ends_loop:
                        return result.output
            else:
                return response.content
```

#### MCPClientPlugin — MCP 工具调用

```python
class MCPClientPlugin:
    @hookimpl
    async def dispatch_outbound(self, session_id, state, outbounds):
        """将 tool call 路由到对应的 MCP Server"""
        for call in outbounds:
            if call.tool_name.startswith("game."):
                result = await self._game_client.call(call.tool_name, call.args)
            elif call.tool_name.startswith("role."):
                result = await self._role_client.call(call.tool_name, call.args)
```

#### SimuMemoryPlugin — 记忆管理（agent 本地）

```python
class SimuMemoryPlugin:
    """记忆系统保持 agent 本地，不通过 MCP"""
    
    @hookimpl
    async def load_state(self, message, session_id) -> dict:
        memories = await self._retriever.search(message.content)
        return {"relevant_memories": memories}
    
    @hookimpl
    async def save_state(self, session_id, state, model_output):
        await self._store.add(session_id, model_output)
```

### 2.5 State 类型定义

Plugin 间传递的状态使用 dataclass，不使用 dict：

```python
@dataclass
class SimuTurnState:
    session_id: str
    tape_events: list[TapeEvent]
    context_window: ContextWindow
    available_tools: list[ToolDef]
    relevant_memories: list[Memory] = field(default_factory=list)
    # 由 run_model 填充
    response_event: TapeEvent | None = None
    new_task_session: TaskSessionInfo | None = None
    drain_queue_after: bool = False
```

### 2.6 Skill 系统设计

```
<workspace>/.agent/skills/
├── governor/
│   └── SKILL.md          # 巡抚技能定义
├── minister/
│   └── SKILL.md          # 尚书技能定义
└── censor/
    └── SKILL.md          # 御史技能定义
```

**SKILL.md 示例**：

```yaml
---
name: governor_zhili
description: 直隶巡抚技能集
agent_type: governor
province: zhili
mcp_servers:
  game: http://localhost:8080/mcp/game
  role: http://localhost:8082/mcp/roles
allowed_tools:
  - game.query_state
  - game.create_incident
  - game.send_message
  - role.query_role_map
tool_constraints:
  game.query_state:
    provinces: [zhili]
  game.create_incident:
    effects:
      - target_path: "provinces.zhili.*"
---

## 职责说明
- 管辖：直隶省（今河北、北京、天津）
- 事务：民政、农桑、商贸、治安

## 行为准则
1. 只能查询和操作直隶省数据
2. 税率调整超过5%需请示皇帝
```

---

## 3. Server 重构设计

### 3.1 MCP Server 拆分

| MCP Server | 功能 | 说明 |
|------------|------|------|
| **simu-mcp** | query_state, create_incident, send_message, await_reply | 游戏交互 + 通信合并，共享 session/invocation 状态 |
| **role-mcp** | query_role_map, get_agent_info | 公开读取，受限写入 |

**设计决策：**
- **Memory 保持 agent 本地**，不通过 MCP。ChromaDB 向量检索 + Tape 存储由 agent 进程本地管理，与 V5 一致
- **game + channel 合并为 simu-mcp**，避免跨服务状态同步（两者都需要 SessionManager、InvocationManager）
- **SSE 事件推送保留**，MCP 用于主动调用（query_state、create_incident 等），消息接收仍走 SSE。MCP 是请求-响应模式，不适合"发消息后等另一条不相关消息到达"的场景

### 3.2 send_message + await_reply 的 MCP 实现

`send_message(await_reply=True)` 在 MCP 中拆为两步：

1. `simu-mcp.send_message(recipients, message)` → 返回 `message_id`
2. Agent 侧状态机将 session 标记为 BLOCKED，记录 pending reply
3. Reply 通过 SSE 事件推送到达 agent
4. 状态机 `try_resolve` → 解阻塞 → drain → 重新进入 Bub 管线

```
Agent                           simu-mcp                    Target Agent
  │                                │                              │
  │── send_message(await_reply) ──►│                              │
  │◄── message_id ─────────────────│── SSE event ────────────────►│
  │                                │                              │
  │  [session → BLOCKED]           │                              │
  │  [新事件入队]                   │                              │
  │                                │◄── reply (HTTP callback) ────│
  │◄── SSE: reply event ──────────│                              │
  │                                │                              │
  │  [try_resolve → IDLE]          │                              │
  │  [drain_queue]                 │                              │
```

### 3.3 权限模型

```yaml
# Agent 注册时由 Server 根据 token 绑定权限
agent_id: governor_zhili
agent_type: governor
capabilities:
  game.query_state:
    provinces: [zhili]
  game.create_incident:
    target_paths: ["provinces.zhili.*"]
  game.send_message: true
  role.query_role_map: true
```

**权限由 Server 端控制**，不信任 agent 自报的 type。Agent 连接时通过 token 认证，Server 根据注册表查询权限并过滤。

### 3.4 多 Agent 类型支持

```yaml
# agents.yaml — Agent 类型注册表
agent_types:
  governor:
    base_skills: [governor_base]
    mcp_access: [simu-mcp, role-mcp]
    
  minister:
    base_skills: [minister_base]
    mcp_access: [simu-mcp, role-mcp]
    extra_capabilities:
      game.query_state:
        provinces: "*"  # 可查全国
    
  external:
    base_skills: [advisor_base]
    mcp_access: [simu-mcp.readonly, role-mcp]
    rate_limit: 10/min
```

**Claude Code 接入验证**：

```
Claude Code (External Agent)
         │
         │ MCP Protocol
         ▼
┌─────────────────────────┐
│  MCP Gateway            │
│  - token 认证           │
│  - 权限过滤（readonly） │
└─────────────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
simu-mcp   role-mcp
(readonly)
```

---

## 4. Phase 1 必须修复的问题

在 MCP 化之前/同时，以下 V5 已知问题需要在 Phase 1 解决：

| 问题 | 修复方案 | 优先级 |
|------|---------|--------|
| QueueController TOCTOU 竞态 | `self._processing.add(agent_id)` 放到 `create_task` 之前 | 立即 |
| EventRouter broadcast 迭代竞态 | 遍历前 snapshot：`list(self._queues.items())` | 立即 |
| Incident 未持久化 | 写入 SQLite，Server 重启后恢复 | 立即 |
| dispatch 失败无回滚 | try/except，失败时 mark invocation FAILED | 高 |
| GameState 无并发保护 | `asyncio.Lock` 保护 tick + query 互斥 | 高 |
| CORS 配置 allow_origins=* | 限制为具体域名 | 中 |

---

## 5. Rust 重写路线图

### 5.1 分阶段演进

| 阶段 | 目标 | 技术栈 | 说明 |
|------|------|--------|------|
| **V6.0** | MCP Server 提取 + 状态机 | Python (FastAPI) | 功能验证 |
| **V6.1** | 多 Agent 验证 + Claude Code | Python + MCP | 接口稳定 |
| **V6.2** | Event Router Rust 化 | Rust (Axum/Tokio) | 最简模块先行 |
| **V6.3** | Game Engine Rust 化 | Rust | 有状态但逻辑独立 |
| **V6.4** | MCP Server 层 Rust 化 | Rust | 依赖前两者 |

**关键原则：每步保留 Python fallback，可回滚。**

### 5.2 Rust Server 架构

```rust
mod mcp_server {
    mod simu;    // query_state, create_incident, send_message
    mod role;    // query_role_map
}

mod engine {
    mod state;     // NationData, ProvinceData
    mod tick;      // TickCoordinator
    mod incident;  // IncidentSystem（持久化到 SQLite）
}

mod routing {
    mod event;     // EventRouter（Arc<RwLock<HashMap>>）
    mod queue;     // QueueController（Mutex 保护）
}
```

### 5.3 通信方式

```
Python Agent (Bub Core + Plugins)
         │
         │ MCP Protocol (SSE transport，复用连接)
         ▼
Rust MCP Server (Axum)
         │
         │ Internal
         ▼
Rust Game Engine

同机部署优化：Unix Domain Socket 替代 TCP
```

---

## 6. 数据流对比

### 6.1 V5 数据流

```
Player → Frontend → Server → QueueController → EventRouter → SSE → Agent
                                                                      │
                                                               on_event (分派)
                                                                      │
                                                               react (ReAct)
                                                                      │
                                                          HTTP callback → Server
```

### 6.2 V6 数据流

```
Player → Frontend → Server → QueueController → EventRouter → SSE → Agent
                                                                      │
                                                              on_event (状态机)
                                                               ├── blocked → 入队
                                                               └── idle → Bub 管线
                                                                           │
                                                                    Plugins (hooks)
                                                                           │
                                                                    MCP Client → MCP Server
```

---

## 7. 关键设计决策汇总

| 决策 | 选择 | 理由 |
|------|------|------|
| Agent Core | Bub（无状态 runtime） | ~200行，hook-first，零改动使用 |
| 状态管理 | Bub 管线外的 Session 状态机 | 阻塞/队列逻辑不属于 core 关注点 |
| 协议 | MCP（主动调用）+ SSE（事件推送） | MCP 不替代推送，两者互补 |
| MCP 拆分 | simu-mcp + role-mcp（2个） | 避免跨服务状态同步 |
| Memory | 保持 agent 本地 | ChromaDB + Tape 与 agent 进程绑定 |
| State 传递 | dataclass（SimuTurnState） | 类型安全，IDE 可补全 |
| Server 语言 | 先 Python 后 Rust，逐模块迁移 | 快速验证 → 性能优化 |
| Plugin 拆分 | Tape / Context / ReAct / MCP / Memory | 单一职责，可独立测试 |

---

## 8. 下一步行动

### Phase 1: MCP + 状态机（4 周）

**Week 1-2: Server MCP 化**
- 将 callback.py 中的 game/channel 接口封装为 simu-mcp Server
- 将 role-map 接口封装为 role-mcp Server
- 实现 token 认证 + 权限过滤
- 修复 QueueController/EventRouter 竞态 + Incident 持久化

**Week 3-4: Agent 重构**
- 引入 Bub Framework
- 实现 SimuAgent 编排层 + SessionStateManager 状态机
- 实现 5 个 Plugin：Tape / Context / ReAct / MCP / Memory
- 端到端验证："给直隶加税5%" 完整链路

### Phase 2: Skill + 多 Agent（2 周）

- 设计 SKILL.md 规范
- 将现有 soul.md + data_scope.yaml 迁移到 SKILL.md
- Claude Code 作为外部 Agent 接入验证

### Phase 3: Rust 重写（逐步）

- Event Router Rust 化（最简模块）
- Game Engine Rust 化（有状态但独立）
- MCP Server Rust 化（依赖前两者）
