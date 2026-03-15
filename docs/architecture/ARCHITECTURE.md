# 皇帝模拟器 V4 - 架构说明文档

## 概述

皇帝模拟器（Simu-Emperor）是一款基于事件驱动的多 Agent 回合制策略游戏。玩家扮演皇帝，AI 扮演朝廷官员，通过事件总线进行通信。

### 核心特性

- **事件驱动架构**：所有模块通过 EventBus 进行异步通信
- **Tick 游戏循环**：自动推进游戏时间（1 tick = 1 周）
- **文件驱动 Agent**：通过 soul.md 和 data_scope.yaml 定义 AI 官员
- **分层记忆系统**：支持短期记忆、长期记忆和跨会话检索
- **Clean Architecture**：应用层与协议层分离，支持多种适配器

---

## 1. 系统架构

### 1.1 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Adapter Layer (适配器层)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │     Web      │  │   Telegram   │  │   Future...  │      │
│  │   Adapter    │  │   Adapter    │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────────────┬────────────────────────────────┘
                             │ 仅协议转换
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   Application Layer (应用层)                 │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │
│  │ GameService   │  │ SessionService│  │ AgentService  │   │
│  └───────────────┘  └───────────────┘  └───────────────┘   │
│  ┌───────────────┐  ┌───────────────┐                       │
│  │ GroupChatSvc  │  │ MessageService│                       │
│  └───────────────┘  └───────────────┘                       │
└────────────────────────────┬────────────────────────────────┘
                             │ 业务逻辑
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                       Core Layer (核心层)                    │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌──────────────┐ │
│  │  Engine │  │ Agents  │  │ EventBus │  │ Repository   │ │
│  └─────────┘  └─────────┘  └──────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 模块依赖规则

| 规则 | 说明 |
|------|------|
| **上层依赖下层** | Adapter → Application → Core |
| **Core 无依赖** | Core 层不依赖上层 |
| **无循环依赖** | 严格避免循环依赖 |
| **依赖注入** | 通过 ApplicationServices 容器管理 |

---

## 2. EventBus 模块

### 2.1 模块结构

```
src/simu_emperor/event_bus/
├── event.py          # Event 数据模型
├── core.py           # EventBus 核心实现
├── logger.py         # 事件日志记录器
└── event_types.py    # 事件类型常量
```

### 2.2 Event 数据模型

```python
@dataclass
class Event:
    event_id: str            # evt_YYYYMMDDHHMMSS_uuid8
    src: str                 # 事件源（如 "player", "agent:revenue_minister"）
    dst: list[str]           # 目标列表（支持多个接收者）
    type: str                # 事件类型（CHAT, RESPONSE, TICK_COMPLETED 等）
    payload: dict            # 事件负载数据
    timestamp: str           # UTC 时间戳
    session_id: str          # 会话 ID（必填）
    parent_event_id: str     # 父事件 ID（事件链追踪）
    root_event_id: str       # 根事件 ID（自动计算）
```

### 2.3 事件路由规则

EventBus 支持三种路由模式，优先级从高到低：

1. **精确匹配**：`dst` 直接匹配订阅者
2. **前缀匹配**：`agent:*` 匹配所有 Agent
3. **广播匹配**：`*` 匹配所有订阅者

```python
# 订阅示例
event_bus.subscribe("agent:revenue_minister", handler)  # 精确
event_bus.subscribe("agent:*", handler)                 # 前缀
event_bus.subscribe("*", handler)                       # 广播
```

### 2.4 事件类型

| 分类 | 事件类型 | 说明 |
|------|----------|------|
| 玩家交互 | `CHAT` | 玩家命令/聊天 |
| Agent 响应 | `RESPONSE` | Agent 回复玩家 |
| Agent 通信 | `AGENT_MESSAGE` | Agent 间消息 |
| 系统事件 | `TICK_COMPLETED` | Tick 完成 |
| 系统事件 | `INCIDENT_CREATED` | 游戏事件创建 |
| 任务事件 | `TASK_CREATED` | 任务会话创建 |
| 任务事件 | `TASK_FINISHED` | 任务完成 |

---

## 3. Engine 模块

### 3.1 模块结构

```
src/simu_emperor/engine/
├── models/
│   ├── base_data.py     # NationData, ProvinceData
│   └── incident.py      # Incident, Effect
├── engine.py            # Engine 核心类
├── tick_coordinator.py  # Tick 定时器
└── protocols.py         # Repository 协议
```

### 3.2 数据模型

#### ProvinceData（省级数据）

```python
@dataclass
class ProvinceData:
    province_id: str
    name: str

    # 四个核心字段（V4 简化）
    production_value: Decimal    # 产值
    population: Decimal          # 人口
    fixed_expenditure: Decimal   # 固定支出
    stockpile: Decimal           # 库存

    # 增长率（固定）
    base_production_growth: Decimal = 0.01   # 1%/tick
    base_population_growth: Decimal = 0.005  # 0.5%/tick

    # 税率修正
    tax_modifier: Decimal = 0.0
```

#### NationData（国家数据）

```python
@dataclass
class NationData:
    turn: int                           # 当前 tick 数
    base_tax_rate: Decimal = 0.10       # 基础税率 10%
    tribute_rate: Decimal = 0.8         # 上缴比例 80%
    fixed_expenditure: Decimal = 0      # 国库固定支出
    imperial_treasury: Decimal = 0      # 国库
    provinces: Dict[str, ProvinceData]   # 省份数据
```

#### Incident/Effect（游戏事件）

```python
@dataclass
class Effect:
    target_path: str        # "provinces.zhili.production_value"
    add: Decimal            # 一次性变化（与 factor 二选一）
    factor: Decimal          # 持续比例（与 add 二选一）

@dataclass
class Incident:
    incident_id: str
    title: str
    description: str
    effects: List[Effect]
    source: str
    remaining_ticks: int    # 持续 tick 数
    applied: bool = False   # add 效果是否已生效
```

### 3.3 Tick 计算流程

```
┌─────────────────────────────────────────────────────────────┐
│                    Engine.apply_tick()                      │
├─────────────────────────────────────────────────────────────┤
│  1. _save_previous_values()    # 保存当前状态用于计算 delta │
│  2. _apply_base_growth()       # 应用基础增长率             │
│  3. _apply_effects()           # 应用所有活跃 Effect        │
│  4. _calculate_tax_and_treasury()  # 税收和国库结算        │
│  5. _refresh_incidents()       # 刷新 Incident 状态         │
│  6. state.turn += 1            # 增加 tick 计数            │
└─────────────────────────────────────────────────────────────┘
```

### 3.4 经济公式

**省级税收**：
```
province_tax = production_value × (base_tax_rate + tax_modifier)
```

**省级结余**：
```
province_surplus = province_tax - fixed_expenditure
```

**省级上缴**：
```
province_remittance = max(0, province_surplus × tribute_rate)
```

**省级库存**：
```
stockpile = max(0, province_surplus - province_remittance)
```

**国库更新**：
```
imperial_treasury = max(0, imperial_treasury + sum(上缴) - fixed_expenditure)
```

### 3.5 TickCoordinator

定时触发 tick 的协调器，默认每 5 秒执行一次：

```python
class TickCoordinator:
    async def _tick_loop(self):
        while self._running:
            # 1. 执行 tick
            new_state = self.engine.apply_tick()

            # 2. 持久化状态
            await self._persist_state(new_state)

            # 3. 广播事件
            await self.event_bus.send_event(Event(
                type="tick_completed",
                dst=["*"],
                payload={"tick": new_state.turn}
            ))

            # 4. 等待固定间隔
            await asyncio.sleep(tick_interval)
```

---

## 4. Agents 模块

### 4.1 模块结构

```
src/simu_emperor/agents/
├── agent.py              # Agent 基类
├── manager.py            # Agent 生命周期管理
├── agent_generator.py    # LLM 动态生成 Agent
├── skills/               # Skill 文件系统
│   ├── models.py         # Skill 数据模型
│   ├── parser.py         # YAML Frontmatter 解析
│   ├── loader.py         # 三级缓存加载器
│   ├── registry.py       # 事件到技能映射
│   └── validator.py      # Skill 校验
├── tools/                # Function Calling 工具
│   ├── query_tools.py    # 查询工具（返回数据）
│   ├── action_tools.py   # 行动工具（执行副作用）
│   └── memory_tools.py   # 记忆工具
└── response_parser.py    # LLM 响应解析
```

### 4.2 Agent 设计

**核心原则**：
- **被动 Agent**：只响应事件，不主动发起
- **文件驱动**：soul.md 定义性格，data_scope.yaml 定义权限
- **Function Calling**：LLM 自主决定调用哪些工具

**Agent 生命周期**：
```
初始化 → 订阅事件 → 接收事件 → 构建上下文 → LLM 调用 → 执行工具 → 响应
```

### 4.3 Skill 系统（v2.0）

**三级缓存架构**：
```
L1: 内存缓存（LRU，最多 50 项）
  ↓ (miss)
L2: mtime 缓存（文件修改时间检测）
  ↓ (changed)
L3: 文件系统（通过 SkillParser 加载）
```

**Skill 文件格式**：
```markdown
---
name: query_data
description: 查询职权范围内的数据
version: "2.0"
priority: 20
required_tools:
  - query_national_data
  - query_province_data
---

# 查阅数据

## 任务说明
你可以查阅你职权范围内的数据...

## 执行流程
1. 理解查询需求
2. 查询数据
3. 分析数据
4. 回复皇帝
```

**事件到技能映射**：
```python
DEFAULT_EVENT_SKILL_MAP = {
    EventType.CHAT: "chat",
    EventType.AGENT_MESSAGE: "receive_message",
    EventType.TICK_COMPLETED: "on_tick_completed",
}
```

### 4.4 Tool 系统

| 工具类型 | 函数名 | 功能 |
|----------|--------|------|
| Query | `query_national_data` | 查询国家级数据 |
| Query | `query_province_data` | 查询省份数据 |
| Query | `list_provinces` | 列出可用省份 |
| Query | `list_agents` | 列出所有官员 |
| Query | `retrieve_memory` | 检索历史记忆 |
| Action | `respond_to_player` | 回复皇帝 |
| Action | `send_message_to_agent` | 发消息给其他 Agent |
| Action | `create_incident` | 创建游戏事件 |

### 4.5 文件驱动的 Agent 定义

**soul.md 示例**：
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

**data_scope.yaml 示例**：
```yaml
display_name: 户部尚书

skills:
  query_data:
    provinces: [zhili, jiangnan]
    fields:
      - population.*
      - agriculture.*

  execute_command:
    provinces: [zhili]
    fields:
      - taxation.land_tax_rate
```

---

## 5. Memory 模块

### 5.1 模块结构

```
src/simu_emperor/memory/
├── tape_writer.py         # 事件写入 tape.jsonl
├── tape_metadata.py       # 元数据管理
├── context_manager.py     # 滑动窗口上下文
├── manifest_index.py      # 会话索引
└── ...
```

### 5.2 Tape 文件结构

```
data/memory/
├── tape_meta.jsonl              # 全局元数据索引
├── session_manifest.json        # Session 状态管理
└── agents/
    └── {agent_id}/
        └── sessions/
            └── {session_id}/
                ├── tape.jsonl    # 事件日志
                └── tape_meta.jsonl # 会话元数据
```

### 5.3 ContextManager - 滑动窗口

**配置参数**：
```python
ContextConfig:
    max_tokens: 8000              # LLM 上下文窗口
    threshold_ratio: 0.95         # 触发压缩阈值（95%）
    keep_recent_events: 20        # 保留的最小事件数
    anchor_buffer: 3              # 锚点附近保留事件数
    enable_anchor_aware: True     # 启用锚点感知
```

**锚点事件**：
- 用户查询（USER_QUERY）
- Agent 响应（RESPONSE, ASSISTANT_RESPONSE）
- 关键游戏状态（GAME_EVENT）

**滑动窗口压缩策略**：
1. 识别锚点位置
2. 总是保留最近 N 个事件
3. 额外保留锚点附近 ±K 个事件
4. 如果 token 仍超阈值，继续删除最旧事件
5. 更新 segment_index 和累积摘要

### 5.4 Session 管理

**会话类型**：
- 主会话：`session:web:{timestamp}:{suffix}`
- 任务会话：`task:{agent_name}:{timestamp}:{suffix}`

**会话嵌套**：
- 最大嵌套深度：5 层
- 父子关系：parent_id ↔ child_ids
- 祖先链：get_parent_chain()

**Agent 状态**：
- `ACTIVE`：正常处理
- `WAITING_REPLY`：等待异步回复
- `FINISHED`：已完成
- `FAILED`：失败

---

## 6. Application 层

### 6.1 模块结构

```
src/simu_emperor/application/
├── services.py            # ApplicationServices 容器
├── game_service.py        # 游戏生命周期
├── session_service.py     # 会话管理
├── agent_service.py       # Agent 生命周期
├── group_chat_service.py  # 群聊功能
├── message_service.py     # 消息路由
└── tape_service.py        # Tape 查询
```

### 6.2 ApplicationServices 容器

**依赖注入容器**，按顺序初始化：
```
1. LLM Provider
2. Database + Repository
3. EventBus + Logger
4. Memory Components
5. SessionManager
6. GameService
7. AgentService
8. SessionService
9. GroupChatService
10. MessageService
11. TapeService
```

### 6.3 服务职责

| 服务 | 职责 |
|------|------|
| GameService | 游戏状态初始化、tick 协调、状态查询 |
| SessionService | 会话创建/选择、标题管理、Agent 绑定 |
| AgentService | Agent 初始化、动态生成、可用性查询 |
| GroupChatService | 群聊创建、成员管理、消息广播 |
| MessageService | 命令/聊天发送、广播、消息解析 |
| TapeService | Tape 查询、子会话支持、事件检索 |

---

## 7. Web Adapter 模块

### 7.1 模块结构

```
src/simu_emperor/adapters/web/
├── server.py              # FastAPI 服务器
├── connection_manager.py  # WebSocket 连接管理
├── game_instance.py       # 游戏实例包装
└── message_converter.py   # 消息格式转换
```

### 7.2 REST API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/ws` | WebSocket | 实时通信 |
| `/api/command` | POST | 发送命令 |
| `/api/state` | GET | 获取游戏状态 |
| `/api/overview` | GET | 获取帝国概况 |
| `/api/sessions` | GET/POST | 会话管理 |
| `/api/tape/current` | GET | 获取事件记录 |
| `/api/agents` | GET/POST | Agent 管理 |
| `/api/groups` | GET/POST | 群聊管理 |
| `/api/health` | GET | 健康检查 |

### 7.3 WebSocket 消息格式

**客户端 → 服务器**：
```json
{
    "type": "command" | "chat",
    "agent": "governor_zhili",
    "text": "查看直隶省情况",
    "session_id": "session:web:..."
}
```

**服务器 → 客户端**：
```json
{
    "kind": "chat" | "state" | "event" | "error",
    "data": {
        "agent": "governor_zhili",
        "text": "回复内容",
        "timestamp": "2026-03-15T12:00:00Z"
    }
}
```

---

## 8. LLM 模块

### 8.1 模块结构

```
src/simu_emperor/llm/
├── base.py          # LLMProvider 接口
├── anthropic.py     # Claude 实现
├── openai.py        # GPT 实现
└── mock.py          # 测试提供商
```

### 8.2 LLMProvider 接口

```python
class LLMProvider(ABC):
    async def call(
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str

    async def call_with_functions(
        prompt: str,
        functions: list[dict],
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> dict  # {response_text, tool_calls}

    def get_context_window_size() -> int
```

### 8.3 Function Calling 支持

统一函数定义格式：
```python
{
    "name": "query_province_data",
    "description": "查询省份数据",
    "parameters": {
        "type": "object",
        "properties": {
            "province_id": {"type": "string"},
            "field_path": {"type": "string"}
        },
        "required": ["province_id", "field_path"]
    }
}
```

---

## 9. 数据持久化

### 9.1 模块结构

```
src/simu_emperor/persistence/
├── database.py       # SQLite 连接管理
├── repositories.py   # Repository 模式 CRUD
└── serialization.py  # 状态序列化
```

### 9.2 数据库表

**game_state**：
```sql
CREATE TABLE game_state (
    id INTEGER PRIMARY KEY,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

**agent_state**：
```sql
CREATE TABLE agent_state (
    agent_id TEXT PRIMARY KEY,
    is_active INTEGER NOT NULL,
    soul_markdown TEXT,
    data_scope_yaml TEXT,
    updated_at TEXT NOT NULL
);
```

**events**：
```sql
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    src TEXT NOT NULL,
    dst TEXT NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
```

---

## 10. 配置管理

### 10.1 配置文件

**config.yaml**（可选）：
```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-20250514
  context_window: 200000

memory:
  enabled: true
  context:
    max_tokens: 8000
    threshold_ratio: 0.95
    keep_recent_events: 20
  retrieval:
    cross_session_enabled: true
```

### 10.2 环境变量

```bash
# LLM 配置
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
SIMU_LLM__PROVIDER=anthropic

# 游戏配置
SIMU_DB_PATH=game.db
SIMU_DATA_DIR=data
SIMU_LOG_DIR=data/logs

# 日志配置
SIMU_LOGGING__LOG_LEVEL=INFO
SIMU_LOGGING__LLM_AUDIT_ENABLED=true
```

---

## 11. 关键设计模式

### 11.1 事件驱动

所有模块通过 EventBus 通信，无直接函数调用：
```
Player → Event → EventBus → Agent → Event → EventBus → Player
```

### 11.2 Repository 模式

数据访问通过 Repository 抽象：
```
Application → Repository → Database
```

### 11.3 依赖注入

通过 ApplicationServices 容器管理依赖：
```
ApplicationServices.create() → 所有服务初始化
```

### 11.4 文件驱动

Agent 配置通过文件定义，无需修改代码：
```
soul.md + data_scope.yaml → Agent 行为
```

---

## 12. 数据流

### 12.1 玩家命令流

```
1. 玩家输入 → WebSocket/REST
2. Web Adapter → MessageService.send_command()
3. MessageService → EventBus (CHAT event)
4. EventBus → Agent (订阅者)
5. Agent → TapeWriter.write_event() (写入 tape.jsonl)
6. Agent → ContextManager (构建上下文)
7. Agent → LLM.call_with_functions()
8. LLM → Agent (tool_calls)
9. Agent → ActionTools/QueryTools (执行工具)
10. Agent → respond_to_player()
11. EventBus → Web Adapter (RESPONSE event)
12. WebSocket → 玩家
```

### 12.2 Tick 流

```
1. TickCoordinator._tick_loop() 触发
2. Engine.apply_tick()
3. 状态持久化
4. EventBus.send_event(TICK_COMPLETED)
5. 所有 Agent 接收事件
6. Agent 执行 tick 响应逻辑
```

---

## 13. 扩展指南

### 13.1 添加新 Agent

1. 创建 `data/default_agents/{agent_id}/` 目录
2. 编写 `soul.md`（性格定义）
3. 编写 `data_scope.yaml`（权限定义）
4. 重启服务自动加载

### 13.2 添加新 Skill

1. 创建 `data/skills/{skill_name}.md`
2. 定义 YAML Frontmatter（元数据）
3. 编写 Markdown Body（任务说明）
4. 更新 registry.py 映射

### 13.3 添加新 Tool

1. 在 `tools/query_tools.py` 或 `tools/action_tools.py` 添加函数
2. 在 `tool_definitions.py` 注册定义
3. 在 Agent 中注册处理器

---

## 14. 模块详细文档

本文档提供系统架构的总体概览。各模块的详细架构图和运行流程请参考对应的 AGENTS.md 文档：

### 核心层模块

| 模块 | 文档路径 | 内容 |
|------|----------|------|
| **EventBus** | [`src/simu_emperor/event_bus/AGENTS.md`](../../src/simu_emperor/event_bus/AGENTS.md) | 事件路由规则、异步处理机制、事件链追踪 |
| **Engine** | [`src/simu_emperor/engine/AGENTS.md`](../../src/simu_emperor/engine/AGENTS.md) | Tick 计算流程、Incident/Effect 系统、经济公式 |
| **Agents** | [`src/simu_emperor/agents/AGENTS.md`](../../src/simu_emperor/agents/AGENTS.md) | Agent 生命周期、Skill 系统、Tool 调用、三级缓存 |
| **Memory** | [`src/simu_emperor/memory/AGENTS.md`](../../src/simu_emperor/memory/AGENTS.md) | Tape 写入、滑动窗口、累积摘要、跨会话检索 |

### 应用层模块

| 模块 | 文档路径 | 内容 |
|------|----------|------|
| **Application** | [`src/simu_emperor/application/AGENTS.md`](../../src/simu_emperor/application/AGENTS.md) | 服务容器、依赖注入、消息路由、会话管理 |
| **Session** | [`src/simu_emperor/session/AGENTS.md`](../../src/simu_emperor/session/AGENTS.md) | 会话嵌套、Per-Agent 状态、异步回复计数 |

### 适配器层模块

| 模块 | 文档路径 | 内容 |
|------|----------|------|
| **Web Adapter** | [`src/simu_emperor/adapters/web/AGENTS.md`](../../src/simu_emperor/adapters/web/AGENTS.md) | WebSocket 连接、REST API、消息转换 |

### 基础设施模块

| 模块 | 文档路径 | 内容 |
|------|----------|------|
| **LLM** | [`src/simu_emperor/llm/AGENTS.md`](../../src/simu_emperor/llm/AGENTS.md) | LLMProvider 接口、Function Calling、多提供商支持 |
| **Persistence** | [`src/simu_emperor/persistence/AGENTS.md`](../../src/simu_emperor/persistence/AGENTS.md) | Repository 模式、数据库表结构、Decimal 序列化 |

### 文档内容概览

每个 AGENTS.md 文档包含：

1. **架构示意图**（Mermaid 图表）
   - 模块组件关系
   - 数据模型结构
   - 与其他模块的接口

2. **详细运行流程**（Mermaid 图表）
   - 完整的处理流程
   - 决策分支和条件
   - 时序交互关系

3. **开发约束**
   - 架构约束规则
   - 错误处理规范
   - 性能考虑事项

---

## 附录

### A. 时间单位

- 1 tick = 1 周
- 4 ticks = 1 月
- 48 ticks = 1 年

### B. Agent ID 规范

- 格式：`{role}_{province}` 或 `{role}`
- 示例：`governor_zhili`, `minister_of_revenue`
- 前缀：`agent:{agent_id}`

### C. Session ID 规范

- 主会话：`session:web:{agent_id}:{timestamp}:{suffix}`
- 任务会话：`task:{agent_name}:{timestamp}:{suffix}`
- Telegram：`session:telegram:{user_id}:{timestamp}:{suffix}`
