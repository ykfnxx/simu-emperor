# Web Adapter 模块文档

## 模块概述

`src/simu_emperor/adapters/web` 模块是 Web 适配器层，基于 FastAPI 实现的实时通信服务器。

### 核心职责
- **协议转换**：HTTP/WebSocket 协议与内部 EventBus 事件之间的转换
- **实时通信**：WebSocket 连接管理和消息广播
- **REST API**：提供 HTTP 端点用于客户端交互

## 架构设计

### V4 重构要点
- 移除业务逻辑：所有业务逻辑委托给 ApplicationServices
- 单一职责：仅处理协议转换和消息路由
- 依赖注入：通过 WebGameInstance 管理服务依赖

### 模块结构
```
src/simu_emperor/adapters/web/
├── connection_manager.py  # WebSocket 连接管理
├── game_instance.py       # 游戏实例管理
├── message_converter.py   # 消息格式转换
└── server.py              # FastAPI 服务器实现
```

### 架构示意图

```mermaid
graph TB
    subgraph Clients["客户端层"]
        Browser["浏览器客户端"]
        WSClient["WebSocket 连接"]
        HTTPClient["HTTP REST API"]
    end

    subgraph WebAdapter["Web Adapter 层 (adapters/web)"]
        FastAPI["FastAPI 服务器<br/>server.py"]

        subgraph WSMgmt["WebSocket 管理"]
            ConnMgr["ConnectionManager<br/>连接管理器"]
            WSHandler["WebSocket Handler<br/>消息处理"]
        end

        subgraph Protocol["协议转换"]
            MsgConv["MessageConverter<br/>消息转换器"]
            Validator["输入校验器"]
        end

        subgraph Instance["实例管理"]
            GameInst["WebGameInstance<br/>游戏实例单例"]
        end
    end

    subgraph AppLayer["Application Layer (application/)"]
        AppSvc["ApplicationServices<br/>服务容器"]

        subgraph Services["业务服务"]
            GameSvc["GameService<br/>游戏服务"]
            SessionSvc["SessionService<br/>会话服务"]
            AgentSvc["AgentService<br/>Agent服务"]
            GroupSvc["GroupChatService<br/>群聊服务"]
            MsgSvc["MessageService<br/>消息服务"]
            TapeSvc["TapeService<br/>Tape服务"]
        end
    end

    subgraph CoreLayer["Core Layer (core)"]
        EventBus["EventBus<br/>事件总线"]
        Engine["Engine<br/>游戏引擎"]
        AgentMgr["AgentManager<br/>Agent管理器"]
    end

    %% 连接关系
    Browser -->|WebSocket| WSClient
    Browser -->|HTTP| HTTPClient

    WSClient --> FastAPI
    HTTPClient --> FastAPI

    FastAPI --> ConnMgr
    FastAPI --> WSHandler
    FastAPI --> MsgConv
    FastAPI --> GameInst

    WSHandler --> ConnMgr
    WSHandler --> Validator
    WSHandler --> GameInst

    ConnMgr -.->|广播| WSClient

    GameInst --> AppSvc
    AppSvc --> GameSvc
    AppSvc --> SessionSvc
    AppSvc --> AgentSvc
    AppSvc --> GroupSvc
    AppSvc --> MsgSvc
    AppSvc --> TapeSvc

    GameSvc --> Engine
    AgentSvc --> AgentMgr

    MsgSvc --> EventBus
    Engine --> EventBus

    EventBus -.->|订阅事件| MsgConv
    MsgConv --> ConnMgr

    style WebAdapter fill:#e1f5ff
    style AppLayer fill:#fff4e1
    style CoreLayer fill:#f0e1ff
    style Clients fill:#e8f5e9
```

## API 端点说明

### WebSocket 端点
```
ws://localhost:8000/ws
```

### REST API 端点

#### 游戏状态 API
- `POST /api/command` - 发送命令到游戏
- `GET /api/state` - 查询当前游戏状态
- `GET /api/overview` - 查询帝国概况

#### 会话管理 API
- `GET /api/sessions` - 列出所有 session
- `POST /api/sessions` - 新建 session
- `POST /api/sessions/select` - 选择当前 session

#### Tape API
- `GET /api/tape/current` - 查询当前 session 的 tape 事件
- `GET /api/tape/subsessions` - 获取指定主会话的所有子 session

#### Agent API
- `GET /api/agents` - 列出所有活跃 agents
- `POST /api/agents/generate` - LLM 生成 agent 配置
- `POST /api/agents/add-generated` - 生成并启动 agent
- `GET /api/agents/jobs/{task_id}` - 查询 Agent 创建任务状态

#### Incident API
- `GET /api/incidents` - 列出所有活跃的 incidents

#### 群聊 API
- `GET /api/groups` - 列出所有群聊
- `POST /api/groups` - 创建群聊
- `POST /api/groups/message` - 向群聊发送消息
- `POST /api/groups/add-agent` - 添加 agent 到群聊
- `POST /api/groups/remove-agent` - 移除 agent

## 消息格式

### WebSocket 消息
**客户端 → 服务器**：
```json
{
    "type": "command" | "chat",
    "agent": "governor_zhili",
    "text": "查看直隶省情况",
    "session_id": "optional_session_id"
}
```

**服务器 → 客户端**：
```json
{
    "kind": "chat" | "state" | "event" | "error" | "session_state",
    "data": {...}
}
```

## 运行流程

### 1. WebSocket 连接流程

```mermaid
sequenceDiagram
    participant C as 客户端
    participant WS as WebSocket Handler
    participant CM as ConnectionManager
    participant GI as WebGameInstance
    participant EB as EventBus

    C->>WS: WebSocket 连接请求 (ws://localhost:8000/ws)
    WS->>CM: connect(websocket)
    CM->>C: accept() 接受连接
    CM->>CM: 添加到 active_connections
    Note over C,CM: 连接建立成功

    C->>WS: 发送消息 JSON
    WS->>WS: 校验消息格式
    WS->>GI: 调用服务处理
    GI->>EB: 发布事件

    Note over CM: 广播给所有连接
    EB-->>CM: 事件回调
    CM->>C: broadcast(ws_message)

    C->>WS: 断开连接
    WS->>CM: disconnect(websocket)
    CM->>CM: 从 active_connections 移除
```

### 2. 命令发送流程

```mermaid
flowchart TD
    Start([客户端发送命令]) --> Parse[解析 WebSocket 消息]

    Parse --> Validate{消息校验}
    Validate -->|失败| SendError[返回错误消息]
    Validate -->|成功| ExtractMsg[提取 agent, text, session_id]

    ExtractMsg --> SelectMsg{消息类型}
    SelectMsg -->|command| CmdSvc[MessageService.send_command]
    SelectMsg -->|chat| ChatSvc[MessageService.send_chat]

    CmdSvc --> CreateEvent[创建 Event 对象]
    ChatSvc --> CreateEvent

    CreateEvent --> Publish[EventBus.publish]
    Publish --> Agent[Agent 接收事件]
    Agent --> Process[Agent 处理命令]
    Process --> Response[生成响应事件]

    Response --> Convert[MessageConverter.convert]
    Convert --> Broadcast[ConnectionManager.broadcast]
    Broadcast --> Client([客户端接收响应])

    SendError --> End([结束])
    Client --> End

    style Start fill:#e8f5e9
    style End fill:#ffebee
    style Validate fill:#fff9c4
    style Agent fill:#e1f5ff
```

### 3. REST API 调用流程

```mermaid
sequenceDiagram
    participant C as 客户端
    participant API as FastAPI REST API
    participant GI as WebGameInstance
    participant SVC as ApplicationServices
    participant DB as Repository

    C->>API: HTTP GET/POST 请求
    API->>API: 校验请求参数

    alt 服务未就绪
        API-->>C: 503 Service Unavailable
    else 参数无效
        API-->>C: 400 Bad Request
    else 正常请求
        API->>GI: 调用对应服务方法
        GI->>SVC: 委托给应用服务层

        Note over SVC,DB: 根据请求类型
        SVC->>DB: 查询数据
        DB-->>SVC: 返回结果

        SVC-->>GI: 返回业务结果
        GI-->>API: 返回响应数据
        API-->>C: JSON 响应 + 200 OK
    end
```

### 4. 消息广播流程

```mermaid
flowchart LR
    Event([EventBus 事件]) --> Subscribe[事件订阅回调]

    Subscribe --> Check{检查消息类型}

    Check -->|TICK_COMPLETED| TickMsg[转换为 state 消息]
    Check -->|RESPONSE| ChatMsg[转换为 chat 消息]
    Check -->|SESSION_STATE| SessionMsg[转换为 session_state 消息]
    Check -->|其他| Ignore[忽略]

    TickMsg --> BuildMsg[构建 WSMessage]
    ChatMsg --> BuildMsg
    SessionMsg --> BuildMsg

    BuildMsg --> Broadcast[ConnectionManager.broadcast]

    Broadcast --> Loop[遍历 active_connections]
    Loop --> Send[send_json 发送]

    Send --> Success{发送成功?}
    Success -->|是| NextConn[下一个连接]
    Success -->|否| Remove[从列表移除]

    NextConn --> CheckEnd{还有连接?}
    Remove --> CheckEnd

    CheckEnd -->|是| Loop
    CheckEnd -->|否| Done([广播完成])

    style Event fill:#fff3e0
    style Done fill:#e8f5e9
    style BuildMsg fill:#e1f5ff
    style Broadcast fill:#f3e5f5
```

### 5. 会话选择流程

```mermaid
stateDiagram-v2
    [*] --> 未选择会话

    未选择会话 --> 检查默认会话: 客户端首次连接
    检查默认会话 --> 使用默认会话: DEFAULT_WEB_SESSION_ID 存在
    检查默认会话 --> 列出可用会话: 需要选择特定会话

    列出可用会话 --> 用户选择会话: 用户发起选择
    用户选择会话 --> 验证会话存在: session_id 校验

    验证会话存在 --> 选择成功: 会话存在
    验证会话存在 --> 返回404错误: 会话不存在

    选择成功 --> 会话激活: SessionService.select_session
    会话激活 --> 加载会话上下文: 加载 tape 元数据
    加载会话上下文 --> [*]

    返回404错误 --> [*]

    使用默认会话 --> [*]

    note right of 检查默认会话
        默认会话 ID:
        "web:main"
    end note
```

### 6. 组件交互时序图（完整流程）

```mermaid
sequenceDiagram
    participant C as 客户端
    participant WS as WebSocket Handler
    participant CM as ConnectionManager
    participant MC as MessageConverter
    participant MS as MessageService
    participant EB as EventBus
    participant A as Agent
    participant TC as TapeWriter

    C->>WS: 建立 WebSocket 连接
    WS->>CM: connect()
    CM-->>C: 连接已建立

    Note over C: 用户发送命令
    C->>WS: {"type": "command", "agent": "governor_xxx", "text": "查看情况"}
    WS->>WS: 校验参数

    WS->>MS: send_command(agent_id, command, session_id)
    MS->>EB: publish(Event)
    MS-->>WS: 事件已发布

    EB->>A: deliver(Event)
    A->>TC: 写入 USER_QUERY 事件
    A->>A: 处理命令 (查询数据/生成响应)
    A->>EB: publish(RESPONSE Event)

    EB->>MC: _on_event(RESPONSE)
    MC->>MC: convert() 转换为 WSMessage
    MC->>CM: broadcast(ws_message)

    loop 每个连接
        CM->>C: send_json(ws_message)
    end

    C-->>C: 显示响应消息
```

## 开发约束

### 架构约束
- Clean Architecture：Web 适配器不能直接依赖 Core 层
- 依赖注入：所有服务通过 ApplicationServices 获取

### 错误处理
- 验证失败：400 状态码
- 服务未就绪：503 状态码
- 资源不存在：404 状态码

### 性能考虑
- 并发发送：WebSocket 广播使用并发提高性能
- 连接清理：自动清理断开连接
