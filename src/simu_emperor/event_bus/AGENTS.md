# EventBus 模块文档

## 模块概述

EventBus 是事件驱动架构的核心基础设施，提供了事件的订阅、发布、路由分发和日志记录功能。该模块实现了完全异步的事件处理机制，支持单播、组播和广播模式。

## 架构设计

### 系统架构示意图

```mermaid
graph TB
    subgraph "EventBus Core"
        EB["EventBus<br/>事件总线核心"]
        SUB["_subscribers<br/>订阅者注册表"]
        ROUTE["_route_event<br/>路由分发器"]
        TASKS["_background_tasks<br/>后台任务集"]
    end

    subgraph "Event 数据模型"
        EVT["Event<br/>数据类"]
        ID["event_id: str"]
        SRC["src: str"]
        DST["dst: list[str]"]
        TYP["type: str"]
        PL["payload: dict"]
        TS["timestamp: str"]
        SID["session_id: str"]
        PEID["parent_event_id: str|None"]
        REID["root_event_id: str"]
    end

    subgraph "EventLogger"
        FLOG["FileEventLogger<br/>JSONL 文件日志"]
        DLOG["DatabaseEventLogger<br/>数据库日志"]
    end

    subgraph "发布者"
        P1["Player<br/>玩家"]
        P2["Agent<br/>AI官员"]
        P3["TickCoordinator<br/>定时器"]
        P4["Engine<br/>游戏引擎"]
    end

    subgraph "订阅者"
        S1["Agent:revenue_minister<br/>户部尚书"]
        S2["Agent:zhili_governor<br/>直隶巡抚"]
        S3["Player<br/>玩家"]
        S4["WebAdapter<br/>Web适配器"]
    end

    P1 & P2 & P3 & P4 -->|send_event| EB
    EVT -->|实例化| EB
    EB -->|记录| FLOG & DLOG
    EB -->|路由查询| SUB
    SUB -->|返回处理器| ROUTE
    ROUTE -->|create_task| TASKS
    TASKS -->|异步调用| S1 & S2 & S3 & S4

    style EB fill:#4A90E2,stroke:#2171C5,color:#fff
    style EVT fill:#50E3C2,stroke:#3DB89A,color:#000
    style FLOG fill:#F5A623,stroke:#D48806,color:#000
    style DLOG fill:#F5A623,stroke:#D48806,color:#000
```

### Event 数据类结构

```mermaid
classDiagram
    class Event {
        +str event_id
        +str src
        +list[str] dst
        +str type
        +dict payload
        +str timestamp
        +str session_id
        +str|None parent_event_id
        +str root_event_id
        +to_json() str
        +from_json(json_str) Event
        +to_dict() dict
        +from_dict(data) Event
        +__post_init__() void
    }

    note for Event "事件链追踪：\nparent_event_id 指向父事件\nroot_event_id 指向事件链根节点"
```

### 路由规则示意图

```mermaid
graph LR
    subgraph "事件 Event.dst = ['agent:revenue_minister', 'player']"
        A1["agent:revenue_minister"]
        A2["player"]
    end

    subgraph "订阅者注册表 _subscribers"
        B1["'agent:revenue_minister'<br/>→ [handler1, handler2]"]
        B2["'agent:*'<br/>→ [handler3]"]
        B3["'*'<br/>→ [handler4]"]
        B4["'player'<br/>→ [handler5]"]
    end

    subgraph "路由匹配优先级"
        C1["1️⃣ 精确匹配<br/>agent:revenue_minister → handler1,2"]
        C2["2️⃣ 前缀匹配<br/>agent:revenue_minister → agent:* → handler3"]
        C3["3️⃣ 广播匹配<br/>* → handler4"]
    end

    A1 -.->|精确匹配| B1
    A1 -.->|前缀匹配| B2
    A2 -.->|精确匹配| B4
    A1 & A2 -.->|广播匹配| B3

    style C1 fill:#E74C3C,stroke:#C0392B,color:#fff
    style C2 fill:#F39C12,stroke:#D68910,color:#fff
    style C3 fill:#3498DB,stroke:#2980B9,color:#fff
```

### 核心组件

#### 1. EventBus 类 (`core.py`)

事件总线的主要实现，负责：
- **事件订阅管理**：维护目标标识符与处理器映射关系
- **事件路由分发**：根据目标标识符将事件路由到匹配的处理器
- **异步任务调度**：使用 fire-and-forget 模式异步执行处理器
- **日志记录集成**：支持文件和数据库双重日志记录

**路由规则优先级**（从高到低）：
1. **精确匹配**：`dst` 精确匹配订阅者
2. **前缀匹配**：`dst` 以 "agent:" 开头时匹配 "agent:*"
3. **广播匹配**：匹配 `*` 通配符

#### 2. Event 数据模型 (`event.py`)

事件的数据结构实现，包含：
- **事件标识**：`event_id`（自动生成UUID）
- **源目标**：`src`（事件发起方）、`dst`（接收方列表）
- **事件类型**：`type`（定义事件分类）
- **负载数据**：`payload`（任意JSON序列化数据）
- **会话标识**：`session_id`（多用户隔离）
- **事件链追踪**：`parent_event_id`、`root_event_id`

#### 3. EventType 枚举 (`event_types.py`)

预定义的事件类型常量，分类包括：

**玩家交互事件**：`CHAT`

**Agent响应事件**：`RESPONSE`, `AGENT_MESSAGE`

**记忆系统事件**（V3 Memory）：`USER_QUERY`, `ASSISTANT_RESPONSE`, `TOOL_CALL`, `TOOL_RESULT`

**系统事件**：`SESSION_STATE`, `TICK_COMPLETED`, `INCIDENT_CREATED`

**Task生命周期事件**：`TASK_CREATED`, `TASK_FINISHED`, `TASK_FAILED`, `TASK_TIMEOUT`

#### 4. EventLogger 接口及其实现 (`logger.py`)

**FileEventLogger**：
- JSONL 格式（每行一个JSON对象）
- 按日期自动轮转
- 支持事件查询和过滤

**DatabaseEventLogger**：
- 记录到 SQLite 数据库
- 支持会话隔离和事件链追踪
- 提供 Agent 可见性查询功能

## 数据模型

### Event 数据结构

```python
@dataclass
class Event:
    event_id: str                    # evt_YYYYMMDDHHMMSS_uuid8
    src: str                        # 事件源
    dst: list[str]                 # 目标列表
    type: str                       # 事件类型
    payload: dict[str, Any]         # 负载数据
    timestamp: str                  # ISO时间戳
    session_id: str                 # 会话标识符（必填）
    parent_event_id: str | None     # 父事件ID
    root_event_id: str              # 根事件ID
```

## 运行流程

### 事件发布完整流程

```mermaid
sequenceDiagram
    participant P as 发布者<br/>(Player/Agent)
    participant EB as EventBus
    participant LOG as EventLogger
    participant ROUTE as 路由分发器
    participant H as 处理器<br/>(Handler)
    participant T as 后台任务

    P->>EB: send_event(event)
    EB->>EB: 验证 session_id
    EB->>EB: 计算 root_event_id

    par 并行日志记录
        EB->>LOG: 文件日志记录
        EB->>LOG: 数据库日志记录
    end

    EB->>ROUTE: _route_event(event)
    ROUTE->>ROUTE: 精确匹配订阅者
    ROUTE->>ROUTE: 前缀匹配订阅者
    ROUTE->>ROUTE: 广播匹配订阅者
    ROUTE->>ROUTE: 去重处理器
    ROUTE-->>EB: 返回处理器列表

    loop 每个处理器
        EB->>T: asyncio.create_task(handler(event))
        T->>H: 异步执行
        H-->>T: 完成
        Note over T: Fire-and-Forget<br/>不等待完成
    end

    EB-->>P: 立即返回
```

### 路由匹配决策流程

```mermaid
flowchart TD
    START([开始: 事件到达]) --> INIT[初始化 handlers 和 seen_handlers]

    INIT --> LOOP1[遍历 event.dst 中的每个目标]

    LOOP1 --> CHECK1{目标在<br/>_subscribers 中?}

    CHECK1 -->|是| ADD1[添加精确匹配处理器到 handlers]
    ADD1 --> CHECK2{还有更多<br/>dst 目标?}

    CHECK1 -->|否| CHECK2
    CHECK2 -->|是| LOOP1
    CHECK2 -->|否| PREFIX[前缀匹配检查]

    PREFIX --> LOOP2[遍历 event.dst 中的每个目标]

    LOOP2 --> CHECK3{目标以<br/>'agent:' 开头?}

    CHECK3 -->|是| CHECK4{agent:*<br/>在订阅表中?}
    CHECK4 -->|是| ADD2[添加前缀匹配处理器]
    ADD2 --> CHECK5{还有更多目标?}

    CHECK3 -->|否| CHECK5
    CHECK4 -->|否| CHECK5
    CHECK5 -->|是| LOOP2
    CHECK5 -->|否| BROADCAST[广播匹配检查]

    BROADCAST --> CHECK6{* 在订阅表中?}
    CHECK6 -->|是| ADD3[添加广播处理器]
    ADD3 --> RETURN[返回去重后的处理器列表]
    CHECK6 -->|否| RETURN

    RETURN --> END([结束])

    style ADD1 fill:#E8F5E9,stroke:#4CAF50
    style ADD2 fill:#FFF3E0,stroke:#FF9800
    style ADD3 fill:#E3F2FD,stroke:#2196F3
```

### 订阅流程

```mermaid
sequenceDiagram
    participant S as 订阅者
    participant EB as EventBus
    participant REG as _subscribers<br/>订阅表

    S->>EB: subscribe(dst, handler)

    EB->>EB: 检查 handler 可调用性

    alt handler 不可调用
        EB-->>S: TypeError 异常
    else handler 可调用
        EB->>REG: 检查 dst 是否存在

        alt dst 已存在
            REG->>REG: 检查是否重复订阅
            alt 重复订阅
                EB-->>S: 警告日志，跳过
            else 未重复
                REG->>REG: 添加 handler 到列表
                EB-->>S: 订阅成功
            end
        else dst 不存在
            REG->>REG: 创建 dst 并添加 handler
            EB-->>S: 订阅成功
        end
    end
```

### Fire-and-Forget 异步处理机制

```mermaid
flowchart TD
    START([send_event 调用]) --> ROUTE[路由获取处理器列表]

    ROUTE --> LOOP{遍历处理器}

    LOOP --> CHECK{处理器类型?}

    CHECK -->|async def| ASYNC[创建 asyncio.Task]
    CHECK -->|def| SYNC[包装为异步任务]

    ASYNC --> ADD1[添加到 _background_tasks]
    SYNC --> ADD2[添加到 _background_tasks]

    ADD1 --> DONE[add_done_callback<br/>自动清理完成的任务]
    ADD2 --> DONE

    DONE --> CHECK2{还有更多处理器?}
    CHECK2 -->|是| LOOP
    CHECK2 -->|否| RETURN([立即返回<br/>不等待任务完成])

    ASYNC -.->|后台执行| BG1[处理器异步执行]
    SYNC -.->|后台执行| BG2[处理器同步执行]

    style ASYNC fill:#E1F5FE,stroke:#0288D1
    style SYNC fill:#F3E5F5,stroke:#7B1FA2
    style RETURN fill:#C8E6C9,stroke:#388E3C
```

### 事件链追踪流程

```mermaid
flowchart LR
    subgraph "事件链示例"
        E1["Event 1<br/>root_event_id: evt_001<br/>parent_event_id: None"]
        E2["Event 2<br/>root_event_id: evt_001<br/>parent_event_id: evt_001"]
        E3["Event 3<br/>root_event_id: evt_001<br/>parent_event_id: evt_002"]
    end

    E1 -->|触发| E2
    E2 -->|触发| E3

    style E1 fill:#E8F5E9,stroke:#4CAF50
    style E2 fill:#FFF3E0,stroke:#FF9800
    style E3 fill:#E3F2FD,stroke:#2196F3
```

## 异步处理模式

### Fire-and-Forget 模式

- `send_event()` 立即返回，不等待处理器完成
- 处理器通过 `asyncio.create_task()` 异步执行
- 后台任务自动管理，支持任务清理

## 使用示例

### 基本使用

```python
from simu_emperor.event_bus import EventBus, Event, EventType

# 创建事件总线
event_bus = EventBus()

# 订阅事件
event_bus.subscribe("player", handle_player_chat)
event_bus.subscribe("agent:*", handle_agent_messages)

# 发送事件
event = Event(
    src="player",
    dst=["agent:revenue_minister"],
    type=EventType.CHAT,
    payload={"message": "Hello, Minister!"},
    session_id="session:cli:default"
)

await event_bus.send_event(event)
```

## 开发约束和最佳实践

### 1. 会话隔离约束
- 所有事件都必须有有效的 `session_id`
- 不同会话的事件不会相互干扰

### 2. 事件路由规则
- 避免过度使用广播 `*` 通配符
- 优先使用精确匹配而非通配符

### 3. 异步处理最佳实践
- 处理器不要执行长时间阻塞操作
- 处理器内部要有适当的错误处理

### 4. 错误处理
```python
# ✅ 正确的错误处理
try:
    await event_bus.send_event(event)
except ValueError as e:
    # 处理 session_id 为空等错误
    print(f"Event validation error: {e}")
```
