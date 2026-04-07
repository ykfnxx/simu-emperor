# 皇帝模拟器 V5 - 架构说明文档

## 概述

皇帝模拟器（Simu-Emperor）是一款基于 Process-per-Agent 架构的多 Agent 策略游戏。玩家扮演皇帝，AI Agent 扮演朝廷官员（巡抚、尚书等），各自运行在独立进程中，通过中央 Server 进行通信和协调。

### 核心特性

- **Process-per-Agent**：每个 Agent 是独立的 Python 子进程
- **SSE + HTTP Callback**：Server 通过 SSE 推送事件，Agent 通过 HTTP 回调执行操作
- **ReAct 推理循环**：Agent 使用 LLM 进行 reason-act-observe 循环
- **文件驱动 Agent**：通过 `soul.md` 和 `data_scope.yaml` 定义 AI 官员
- **Tape 事件溯源**：JSONL + SQLite 双写，支持向量检索的记忆系统
- **Task Session**：层级任务会话，支持多 Agent 协作

---

## 1. 系统架构

### 1.1 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Web Frontend                           │
│              React + Vite + TypeScript + Tailwind            │
│         WebSocket (/ws)          REST (/api/*)              │
└──────────┬──────────────────────────┬───────────────────────┘
           │ real-time push           │ commands/queries
           ▼                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Server                            │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐ │
│  │ client.py    │  │ callback.py  │  │  WebSocket Mgr    │ │
│  │ (Frontend)   │  │ (Agent API)  │  │  (broadcast)      │ │
│  └──────┬───────┘  └──────┬───────┘  └───────────────────┘ │
│         │                 │                                 │
│  ┌──────▼─────────────────▼──────────────────────────────┐ │
│  │                  Services Layer                        │ │
│  │  QueueController    EventRouter    InvocationManager   │ │
│  │  SessionManager     MessageStore   ProcessManager      │ │
│  │  AgentRegistry      GroupStore     WSManager           │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │                   Game Engine                         │ │
│  │  GameState    TickCoordinator    IncidentSystem       │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
           │ SSE event stream              ▲ HTTP callbacks
           ▼                               │
┌─────────────────────────────────────────────────────────────┐
│              Agent Processes (独立子进程)                     │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    BaseAgent (SDK)                   │   │
│  │  ServerClient ◄── SSE /api/callback/events          │   │
│  │  on_event() → SessionStateManager → react(event)    │   │
│  │  ReActLoop: LLM ↔ Tool Calls ↔ Observations        │   │
│  │  TapeManager + ContextManager + MemoryStore         │   │
│  │  soul.md + data_scope.yaml (personality/permissions) │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 四个包的职责

| 包 | 路径 | 职责 |
|---|---|---|
| **shared** | `packages/shared/` | Pydantic 数据模型（TapeEvent, NationData, Effect 等），EventType 常量 |
| **server** | `packages/server/` | FastAPI 服务、事件路由、队列调度、游戏引擎、进程管理、WebSocket |
| **sdk** | `packages/sdk/` | Agent 运行时：ReAct 循环、LLM 抽象、工具注册、Tape 持久化、Memory 系统 |
| **agents** | `packages/agents/` | 具体 Agent 配置（`soul.md` + `data_scope.yaml`） |

### 1.3 包依赖规则

```
shared ← sdk ← agents
shared ← server
```

SDK 和 Server 之间**不存在代码依赖** — 它们通过 HTTP/SSE 协议通信。

---

## 2. Server 模块

### 2.1 路由层

#### client.py — 前端 API

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/command` | POST | 发送玩家指令，路由到目标 Agent |
| `/api/sessions` | GET/POST | 会话管理 |
| `/api/sessions/select` | POST | 切换当前会话 |
| `/api/state` | GET | 获取完整游戏状态 |
| `/api/overview` | GET | 获取帝国概况 |
| `/api/state/tick` | POST | 手动触发 tick |
| `/api/agents` | GET | 获取已注册 Agent 列表 |
| `/api/incidents` | GET | 获取活跃 Incident 列表 |
| `/api/tape/current` | GET | 获取当前会话 tape 事件 |
| `/api/tape/subsessions` | GET | 获取子会话列表 |
| `/api/groups` | GET/POST | Agent 分组管理 |
| `/ws` | WebSocket | 实时事件推送 |

#### callback.py — Agent 回调 API

所有请求携带 `X-Agent-Id` 和 `X-Callback-Token` 头：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/callback/register` | POST | Agent 注册（进程启动后） |
| `/api/callback/heartbeat` | POST | 心跳 |
| `/api/callback/status` | POST | 状态变更（停止） |
| `/api/callback/events` | GET (SSE) | 事件流推送 |
| `/api/callback/message` | POST | Agent 发送消息 |
| `/api/callback/state` | GET | 查询游戏状态 |
| `/api/callback/role-map` | GET | 查询官员-AgentID 映射 |
| `/api/callback/tape-event` | POST | 推送内部事件到 MessageStore |
| `/api/callback/task-session/create` | POST | 创建任务子会话 |
| `/api/callback/task-session/finish` | POST | 完成任务会话 |
| `/api/callback/incident` | POST | 创建经济事件 |
| `/api/callback/session/title` | POST | 更新会话标题 |
| `/api/callback/invocation/complete` | POST | 标记调用完成 |

### 2.2 服务层

#### QueueController
- 每个 Agent 一个 FIFO 队列（`asyncio.Queue`，max_depth=10）
- 串行调度：一个 Agent 同时只处理一个 invocation
- `enqueue()` → `_process_loop()` → `dispatch_fn()`

#### EventRouter
- 每个连接的 Agent 维护一个 `asyncio.Queue`
- Agent 通过 SSE 长连接接收事件
- 支持精确路由（`agent:xxx`）和广播（`*`）

#### ProcessManager
- 通过 `asyncio.create_subprocess_exec` 启动 Agent 子进程
- 环境变量传递配置：`SIMU_SERVER_URL`, `SIMU_AGENT_ID`, `SIMU_AGENT_TOKEN`, `SIMU_CONFIG_PATH`
- 支持优雅关闭（SIGTERM + 30s timeout）

#### InvocationManager
- 追踪每次 Agent 调用的生命周期：QUEUED → RUNNING → SUCCEEDED/FAILED
- SQLite 持久化

#### SessionManager
- 会话 CRUD（SQLite）
- 支持父子会话关系（task session 嵌套）
- 元数据存储（标题、Agent 列表、状态）

#### MessageStore
- 消息持久化（SQLite + JSONL 双写）
- 为前端提供会话消息历史

### 2.3 游戏引擎

#### GameState
- 内存中维护 `NationData`（国库、税率、省份数据）
- 省份字段：`production_value`, `population`, `fixed_expenditure`, `stockpile`, `tax_modifier`, `base_production_growth`, `base_population_growth`
- 国家字段：`imperial_treasury`, `base_tax_rate`, `tribute_rate`, `fixed_expenditure`

#### TickCoordinator
- 手动触发（`POST /api/state/tick`）
- 流程：应用增长率 → 应用 Incident 效果 → 计算税收/国库 → 刷新 Incident

#### IncidentSystem
- 管理有时限的经济事件
- Effect 类型：`add`（一次性加减）/ `factor`（每 tick 乘性变化）
- `tax_modifier` 等修正字段允许为零或负值

### 2.4 经济公式

```
省级税收 = production_value × (base_tax_rate + tax_modifier)
省级结余 = 省级税收 - fixed_expenditure
省级上缴 = max(0, 省级结余 × tribute_rate)
省级库存 += max(0, 省级结余 - 省级上缴)
国库 += sum(各省上缴) - 国家 fixed_expenditure
```

---

## 3. Agent SDK 模块

### 3.1 BaseAgent 生命周期

```
__init__() → 初始化 ServerClient, SessionStateManager, LLM, Tape, Memory, Tools
start()    → tape.initialize() → server.register() → _event_loop() + _heartbeat_loop()
on_event() → 事件分发（SHUTDOWN / TASK_FINISHED / AGENT_MESSAGE / CHAT 等）
react()    → ReActLoop.run() → RESPONSE → push_tape_event → post_message
stop()     → server.deregister() → cleanup
```

### 3.2 事件分发逻辑 (`on_event`)

```python
if SHUTDOWN:        stop()
if RELOAD_CONFIG:   reload personality
if TASK_FINISHED/FAILED:
    _handle_task_completion()  # unblock parent, react, drain queue
if AGENT_MESSAGE/RESPONSE:
    if clears pending reply:
        if fully unblocked: react() + drain queue
        else: enqueue for later
    # falls through if not a reply
if session blocked: enqueue
else: react(event)
```

### 3.3 ReAct 循环

```
while iterations < max_iterations:
  1. LLM(system_prompt + context + event)
  2. if tool_calls:
       execute each tool, record to tape
       if any tool returns ends_loop=True → return
  3. else:
       return text as final response
```

- 最大迭代次数：10（默认）
- 最大工具调用次数：20（默认）
- 支持 Anthropic 和 OpenAI 消息格式

### 3.4 系统提示构建

`_build_system_prompt(session_id)` 按顺序拼接：
1. `soul.md` — 角色性格
2. `data_scope.yaml` — 数据权限范围
3. 行动执行指令 — 何时使用 `create_incident`（仅有 `data_scope` 的 agent）
4. 任务派发指令 / 任务执行指令 — 根据会话类型
5. 消息回复指令 — 区分 send_message 与直接文字回复

### 3.5 SessionStateManager

每个 Agent 内部维护的会话状态：

| 状态 | 说明 |
|------|------|
| `pending_tasks` | 未完成的 task sub-session ID 集合 |
| `pending_replies` | 等待回复的消息 ID → 发送者映射 |
| `message_queue` | 被阻塞时的事件队列 |
| `session hierarchy` | parent/child 关系，嵌套深度（最大 5 层） |
| `active_session` | 当前 ReAct 循环目标会话 |

**阻塞语义**：当 session 有 pending tasks 或 pending replies 时，新事件被入队而非立即处理。

### 3.6 标准工具

| 工具 | 类别 | 关键行为 |
|------|------|---------|
| `send_message` | communication | `await_reply=true` 阻塞会话等待回复 |
| `query_state` | communication | 查询游戏状态（path 参数支持点号导航） |
| `query_role_map` | communication | 返回所有官员的名称、agent_id、职责 |
| `create_incident` | action | 创建经济效果，Server 校验权限和数值 |
| `create_task_session` | session | 返回 `ends_loop=True`，切换到子会话 |
| `finish_task_session` | session | 返回 `ends_loop=True`，切回父会话 |
| `fail_task_session` | session | 同上，标记失败 |
| `search_memory` | memory | ChromaDB 向量检索历史会话 |

### 3.7 Tape 与 Memory 系统

**TapeManager**：
- 每个 agent、每个 session 独立的 JSONL 文件
- SQLite 索引用于查询
- 可选 mirror 到 `data/memory/` 共享目录

**ContextManager**：
- 滑动窗口：保留最近事件，压缩旧事件为 ViewSegment
- 会话摘要：每次 response 后由 LLM 更新
- ViewSegment 存入 ChromaDB 供跨会话检索

**MemoryRetriever**（两级搜索）：
- L1：跨会话搜索（session 标题/摘要匹配）
- L2：会话内搜索（ViewSegment 内容匹配）

---

## 4. 前端

**技术栈**：React 18 + Vite + TypeScript + Tailwind CSS

**主要功能**：
- WebSocket 实时接收事件
- 会话列表和切换
- 聊天界面（发送指令，显示 Agent 回复）
- 游戏状态面板（省份数据、国库、Incident 列表）

**WebSocket 消息类型**：
- `chat`: Agent 消息
- `state`: 游戏状态更新
- `event`: TapeEvent
- `session_state`: 会话状态变更
- `task_finished`: 任务完成通知

---

## 5. 核心数据流

### 5.1 玩家指令 → Agent 执行

```
1. Frontend: POST /api/command {text, session_id, agent?}
2. Server client.py:
   - 创建 TapeEvent(src=player, type=CHAT, dst=[agent:xxx])
   - 存入 MessageStore
   - QueueController.enqueue(agent_id, event)
3. QueueController:
   - dispatch_fn(agent_id, event)
   - InvocationManager.create() → mark_running()
   - EventRouter.route(event) → agent 的 SSE 队列
4. Agent (via SSE):
   - ServerClient.event_stream() 接收 TapeEvent
   - on_event() → react(event)
5. ReActLoop:
   - LLM 读取 system_prompt + context + event
   - 决定调用工具或直接回复
   - 工具执行（query_state, create_incident 等）
6. Agent 发送 RESPONSE:
   - push_tape_event(response, route=should_route)
   - post_message(recipients=["player"], message=content)
7. Server:
   - 存入 MessageStore
   - WebSocket broadcast → Frontend 显示
```

### 5.2 Agent 间通信

```
1. Agent A 调用 send_message(recipients=["agent_b"], await_reply=true)
2. ServerClient POST /api/callback/message
3. Server 创建 TapeEvent(src=agent:A, type=AGENT_MESSAGE)
4. QueueController.enqueue("agent_b", event) → EventRouter → Agent B SSE
5. Agent B: on_event() → react(event) → 输出文字回复
6. 文字输出包装为 RESPONSE event，push_tape_event(route=True)
7. Server callback.py: 检测 route=True + type=RESPONSE → enqueue 给 Agent A
8. Agent A: on_event() → _try_clear_pending_reply() → 成功
9. Session 解除阻塞 → react(reply_event) → 处理回复
```

### 5.3 Task Session 流程

```
1. 玩家: "问问张廷玉身体如何" → Agent A (governor)
2. Agent A react():
   - query_role_map() → 找到 minister_of_revenue
   - create_task_session(goal="询问张廷玉身体状况")
     → ends_loop=True, 父 session 标记为 blocked
3. Agent A 进入 task session:
   - 收到 TASK_CREATED 合成事件
   - send_message(recipients=["minister_of_revenue"], await_reply=true)
     → ends_loop=True, task session 等待回复
4. Agent B (minister) 收到消息 → react → 文字回复
5. RESPONSE 路由回 Agent A (task session)
6. Agent A task session 解除阻塞 → react(reply):
   - finish_task_session(result="张廷玉说...")
     → ends_loop=True
7. Server: finish_task_session → TASK_FINISHED event → enqueue 给 Agent A (parent session)
8. Agent A parent session: _handle_task_completion() → react(TASK_FINISHED)
   - 向 player 汇报结果
```

---

## 6. 事件类型

| 类型 | 方向 | 说明 |
|------|------|------|
| `CHAT` | player → agent | 玩家指令 |
| `AGENT_MESSAGE` | agent → agent | 主动发起的消息 |
| `RESPONSE` | agent → agent/player | 自动路由的回复 |
| `TASK_CREATED` | agent → self | 进入任务会话的合成事件 |
| `TASK_FINISHED` | server → agent | 任务完成（路由到父会话） |
| `TASK_FAILED` | server → agent | 任务失败 |
| `TOOL_CALL` | agent → tape | 工具调用记录 |
| `TOOL_RESULT` | agent → tape | 工具结果记录 |
| `SHUTDOWN` | server → agent | 优雅关闭 |
| `RELOAD_CONFIG` | server → agent | 热重载配置 |

---

## 7. Agent 配置

### 7.1 soul.md 示例

```markdown
# 户部尚书 - 张廷玉

## 身份
你是大清户部尚书张廷玉，掌管天下财政。

## 性格
- 为人谨慎，善于揣摩圣意
- 有一定的贪墨倾向，会在账目上做手脚

## 说话风格
文言与白话混用，言辞恭敬但暗含城府。
```

### 7.2 data_scope.yaml 示例

```yaml
display_name: 户部尚书

provinces: all
fields:
  - production_value
  - population
  - stockpile
  - tax_modifier
nation_fields:
  - imperial_treasury
  - base_tax_rate
  - tribute_rate
  - fixed_expenditure
```

### 7.3 添加新 Agent

1. 创建 `data/default_agents/{agent_id}/` 目录
2. 编写 `soul.md`（性格定义）
3. 编写 `data_scope.yaml`（权限定义）
4. Server 启动时自动加载并注册

---

## 8. 已知限制与风险

### 8.1 并发风险

- QueueController `enqueue()` 存在 TOCTOU 竞态（应原子化状态检查）
- EventRouter/WSManager 遍历中可能被并发修改
- GameState 读写无锁保护（tick 和 query_state 可能并发）
- SessionManager 的 read-modify-write 模式可能丢失更新

### 8.2 性能瓶颈

- Server 为单进程 asyncio，所有 Agent 的 IO 集中于此
- SQLite 写操作互斥
- LLM 调用延迟（3-30 秒）是主要时间开销
- `_update_session_summary` 的 LLM 调用曾阻塞事件循环（已改为异步后台执行）

### 8.3 扩展方向

参见 `docs/research/v6-architecture-research.md`：
- MCP 协议化工具
- 核心服务从 Python/SQLite 迁移到 Go/Rust + PostgreSQL
- EventRouter 用 Redis Stream 或 NATS 替代

---

## 附录

### A. 时间单位

- 1 tick = 1 周
- 4 ticks = 1 月
- 48 ticks = 1 年

### B. ID 规范

- Agent ID: `{role}_{province}` 或 `{role}`（如 `governor_zhili`, `minister_of_revenue`）
- Agent 前缀: `agent:{agent_id}`
- 主会话: `session:web:{suffix}`
- 任务会话: `task:{suffix}`

### C. 环境变量

```bash
# Agent 进程配置（由 ProcessManager 设置）
SIMU_SERVER_URL=http://localhost:8000
SIMU_AGENT_ID=governor_zhili
SIMU_AGENT_TOKEN=<hex token>
SIMU_CONFIG_PATH=data/agents/governor_zhili

# LLM 配置
SIMU_LLM_PROVIDER=anthropic
SIMU_LLM_MODEL=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=sk-ant-...

# 可选
SIMU_MEMORY_DIR=data/memory  # 启用 tape mirror
```
