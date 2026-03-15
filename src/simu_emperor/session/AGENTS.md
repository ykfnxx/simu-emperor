# Session 模块文档

## 模块概述

`src/simu_emperor/session` 模块实现了 V4 任务会话架构，提供了完整的会话生命周期管理。

### 核心特性
- **会话嵌套机制**: 支持 Task Session 嵌套，最大深度 5 层
- **Per-Agent 状态管理**: 每个会话中每个 Agent 的独立状态跟踪
- **异步响应管理**: 支持异步工具调用的等待和恢复机制
- **ContextManager 集成**: 无缝集成上下文管理系统
- **持久化支持**: 会话状态持久化到 `session_manifest.json`

## 架构设计

### 模块结构
```
src/simu_emperor/session/
├── __init__.py
├── constants.py     # 常量定义
├── models.py        # 数据模型
├── manager.py      # 会话管理器
├── group_chat.py   # 群聊模型
└── task_monitor.py # 任务监控
```

### 架构示意图

#### Session 嵌套结构

```mermaid
graph TD
    MS[Main Session<br/>session:timestamp:suffix]
    T1[Task Session 1<br/>task:agent1:timestamp:suffix]
    T2[Task Session 2<br/>task:agent2:timestamp:suffix]
    T3[Task Session 3<br/>task:agent3:timestamp:suffix]
    T4[Task Session 4<br/>task:agent4:timestamp:suffix]
    T5[Task Session 5<br/>task:agent5:timestamp:suffix]
    T6[Task Session 6<br/>❌ 超过最大深度]

    MS -->|parent_id| T1
    T1 -->|parent_id| T2
    T2 -->|parent_id| T3
    T3 -->|parent_id| T4
    T4 -->|parent_id| T5
    T5 -.->|parent_id| T6

    style MS fill:#e1f5fe
    style T1 fill:#fff3e0
    style T2 fill:#fff3e0
    style T3 fill:#fff3e0
    style T4 fill:#fff3e0
    style T5 fill:#fff3e0
    style T6 fill:#ffebee
```

#### Session 数据模型结构

```mermaid
classDiagram
    class Session {
        +str session_id
        +str~None parent_id
        +list~str~ child_ids
        +str status
        +str created_by
        +datetime~None timeout_at
        +datetime~None timeout_notified_at
        +str~None root_event_id
        +list~str~ waiting_for_tasks
        +int pending_async_replies
        +list~str~ pending_message_ids
        +dict~str,str~ agent_states
        +datetime created_at
        +datetime updated_at
        +bool is_task
        +dict~ to_dict()
        +Session from_dict()
    }

    class GroupChat {
        +str group_id
        +str name
        +list~str~ agent_ids
        +str created_by
        +datetime created_at
        +str session_id
        +int message_count
        +dict~ to_dict()
        +GroupChat from_dict()
    }

    class TaskMonitor {
        +SessionManager session_manager
        +EventBus event_bus
        +float check_interval
        +start()
        +stop()
        +_monitor_loop()
        +_check_timeouts()
    }

    Session "1" --> "0..*" GroupChat : session_id
    TaskMonitor --> Session : monitors
```

#### SessionManager 与各组件关系

```mermaid
graph LR
    subgraph "Session Module"
        SM[SessionManager]
        M[models.py<br/>Session/GroupChat]
        GM[group_chat.py<br/>GroupChat]
        TM[task_monitor.py<br/>TaskMonitor]
        C[constants.py<br/>MAX_TASK_DEPTH=5]
    end

    subgraph "Memory Module"
        CM[ContextManager]
        TM2[TapeMetadataManager]
        TW[TapeWriter]
    end

    subgraph "Event System"
        EB[EventBus]
    end

    subgraph "Persistence"
        MF[session_manifest.json]
        TF[tape.jsonl]
    end

    SM --> M
    SM --> C
    SM --> CM
    SM --> TM2
    SM --> TW
    TM --> EB
    SM --> MF
    CM --> TF

    style SM fill:#4caf50,color:#fff
    style CM fill:#2196f3,color:#fff
    style MF fill:#ff9800
```

## 关键类说明

### SessionManager
会话管理的核心类

**核心功能**：
- 会话生命周期管理
- 会话嵌套深度控制（最大 5 层）
- Per-Agent 状态管理
- 异步响应计数管理
- ContextManager 实例缓存

### Session 数据模型

**核心字段**：
- `session_id`: 会话唯一标识
- `parent_id`: 父会话 ID
- `child_ids`: 子会话列表
- `status`: 会话状态
- `agent_states`: Per-Agent 状态字典
- `pending_async_replies`: 异步响应计数

## 会话状态机

| 状态 | 描述 |
|------|------|
| `ACTIVE` | 活跃状态 |
| `WAITING_REPLY` | 等待回复 |
| `FINISHED` | 已完成 |
| `FAILED` | 已失败 |

## 会话嵌套机制

### 命名规范
- Main Session: `session:{timestamp}:{suffix}`
- Task Session: `task:{agent_id}:{timestamp}:{suffix}`

### 嵌套示例
```
Main Session
└── Task Session 1
    └── Task Session 2
        └── Task Session 3
            └── Task Session 4 (❌ 超过最大深度)
```

## session_manifest.json 结构

```json
{
  "version": "2.0",
  "last_updated": "2026-03-15T12:00:00.000000Z",
  "sessions": {
    "session:20260315120000:a1b2c3d4": {
      "parent_id": null,
      "child_ids": ["task:agent1:20260315120001:b2c3d4e5"],
      "status": "ACTIVE",
      "created_by": "player",
      "timeout_at": null,
      "timeout_notified_at": null,
      "root_event_id": null,
      "waiting_for_tasks": [],
      "pending_async_replies": 0,
      "pending_message_ids": [],
      "agent_states": {
        "agent:revenue_minister": "ACTIVE",
        "agent:governor_zhili": "WAITING_REPLY"
      },
      "created_at": "2026-03-15T12:00:00.000000Z",
      "updated_at": "2026-03-15T12:00:00.000000Z"
    }
  }
}
```

## 详细运行流程

### 会话创建流程

```mermaid
flowchart TD
    Start[开始: create_session] --> CheckParent{是否有<br/>parent_id?}
    CheckParent -->|是| ValidateParent[获取父会话]
    CheckParent -->|否| GenerateID[生成 session_id]
    ValidateParent --> CalcDepth[计算嵌套深度]
    CalcDepth --> CheckDepth{深度 >= 5?}
    CheckDepth -->|是| RaiseError[❌ 抛出异常<br/>深度超限]
    CheckDepth -->|否| GenerateID
    GenerateID --> CreateSession[创建 Session 对象]
    CreateSession --> HasParent{是否有<br/>parent_id?}
    HasParent -->|是| AddChild[父会话添加 child_id]
    HasParent -->|否| StoreSession
    AddChild --> StoreSession[存储到 _sessions]
    StoreSession --> SaveManifest[保存到 session_manifest.json]
    SaveManifest --> Return[返回 Session 对象]

    style Start fill:#e3f2fd
    style Return fill:#c8e6c9
    style RaiseError fill:#ffcdd2
```

### 会话嵌套流程

```mermaid
sequenceDiagram
    participant Player as 玩家
    participant SM as SessionManager
    participant MS as Main Session
    participant T1 as Task Session 1
    participant T2 as Task Session 2

    Player->>SM: create_session(created_by="player")
    SM->>MS: 创建主会话
    SM-->>Player: session:timestamp:suffix

    Player->>SM: create_session(parent_id=MS, created_by="agent:A")
    SM->>MS: 检查深度=0
    SM->>T1: 创建 Task Session 1
    SM->>MS: 添加 child_ids=[T1.id]
    SM-->>Player: task:A:timestamp:suffix

    Player->>SM: create_session(parent_id=T1, created_by="agent:B")
    SM->>T1: 检查深度=1
    SM->>T2: 创建 Task Session 2
    SM->>T1: 添加 child_ids=[T2.id]
    SM-->>Player: task:B:timestamp:suffix

    Note over SM: 嵌套最多 5 层
```

### 异步回复计数流程

```mermaid
sequenceDiagram
    participant Agent as Agent (调用者)
    participant SM as SessionManager
    participant Session as Session
    participant Tool as 异步工具

    Agent->>SM: increment_async_replies(count=N)
    SM->>Session: pending_async_replies += N
    SM->>Session: agent_states[agent] = "WAITING_REPLY"
    SM->>SM: save_manifest()
    SM-->>Agent: 计数已增加

    loop 每次收到回复
        Tool->>SM: decrement_async_replies(count=1)
        SM->>Session: pending_async_replies -= 1
        alt pending_async_replies == 0
            SM->>Session: agent_states[agent] = "ACTIVE"
            SM-->>Tool: all_replies_received=True
        else pending_async_replies > 0
            SM-->>Tool: all_replies_received=False
        end
        SM->>SM: save_manifest()
    end
```

### 会话状态转换流程

```mermaid
stateDiagram-v2
    [*] --> ACTIVE: 创建会话
    ACTIVE --> WAITING_REPLY: 发起异步调用
    WAITING_REPLY --> ACTIVE: 收到所有回复
    ACTIVE --> FINISHED: 任务完成
    ACTIVE --> FAILED: 任务失败
    WAITING_REPLY --> FAILED: 超时/错误
    FINISHED --> [*]
    FAILED --> [*]

    note right of ACTIVE
        默认初始状态
        可以正常处理事件
    end note

    note right of WAITING_REPLY
        等待异步响应
        pending_async_replies > 0
    end note
```

### ContextManager 实例缓存流程

```mermaid
flowchart TD
    Start[get_context_manager<br/>session_id, agent_id] --> GenKey[生成缓存键<br/>cache_key = session_id:agent_id]
    GenKey --> CheckCache{缓存中存在?}
    CheckCache -->|是| ReturnCached[返回缓存实例]
    CheckCache -->|否| ImportModule[import ContextManager]
    ImportModule --> GetTapePath[获取 tape.jsonl 路径]
    GetTapePath --> ReadConfig[从 settings 读取配置]
    ReadConfig --> CreateCM[创建 ContextManager 实例]
    CreateCM --> LoadTape[load_from_tape<br/>include_ancestors]
    LoadTape --> Cache[存入 _context_managers]
    Cache --> ReturnCM[返回实例]

    style Start fill:#e3f2fd
    style ReturnCached fill:#fff9c4
    style ReturnCM fill:#c8e6c9
```

## 异步回复管理

```python
# 增加异步回复计数
await session_manager.increment_async_replies(session_id, agent_id, count=1)

# 减少异步回复计数
all_replies_received, remaining = await session_manager.decrement_async_replies(
    session_id, agent_id, count=1
)
```

## 开发约束

### 会话创建约束
- 最大嵌套深度：5 层
- Task Session 最多 2 个成员

### 状态管理
- 惰性初始化：首次访问时自动初始化为 ACTIVE
- 状态持久化：任何状态变更都会自动保存

### ContextManager 使用
- 懒加载：在首次请求时创建并缓存
- 按 `{session_id}:{agent_id}` 缓存实例
