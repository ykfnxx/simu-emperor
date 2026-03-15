# Application Layer 模块文档

## 模块概述

`application` 模块是 V4.1 架构中的 **应用层（Application Layer）**，实现了 Clean Architecture 中的业务逻辑层。

### 核心定位
- **业务逻辑层**：封装所有业务规则和用例逻辑
- **服务容器**：通过 `ApplicationServices` 统一管理所有服务实例
- **依赖注入**：实现松耦合的组件设计和生命周期管理

## 架构设计

### Clean Architecture 分层

```mermaid
graph TB
    subgraph "Adapter Layer 适配层"
        WEB[Web Adapter]
        TG[Telegram Adapter]
    end

    subgraph "Application Layer 应用层 (V4.1)"
        GameSvc[GameService]
        SessionSvc[SessionService]
        AgentSvc[AgentService]
        GroupChatSvc[GroupChatService]
        MessageSvc[MessageService]
        TapeSvc[TapeService]
        Services[ApplicationServices Container]
    end

    subgraph "Core Layer 核心层"
        Engine[Engine]
        TickCo[TickCoordinator]
        Agents[Agents]
        EventBus[EventBus]
        Repo[Repository]
        SessionMgr[SessionManager]
        Memory[Memory Components]
    end

    WEB -->|"HTTP Request"| Services
    TG -->|"Update"| Services

    Services -->|"依赖"| GameSvc
    Services -->|"依赖"| SessionSvc
    Services -->|"依赖"| AgentSvc
    Services -->|"依赖"| GroupChatSvc
    Services -->|"依赖"| MessageSvc
    Services -->|"依赖"| TapeSvc

    GameSvc --> Engine
    GameSvc --> TickCo
    GameSvc --> EventBus
    GameSvc --> Repo

    AgentSvc --> Agents
    AgentSvc --> SessionMgr
    AgentSvc --> EventBus

    SessionSvc --> SessionMgr
    GroupChatSvc --> SessionMgr
    TapeSvc --> SessionMgr
    TapeSvc --> Memory

    MessageSvc --> EventBus
    MessageSvc --> SessionMgr

    style Services fill:#e1f5ff
    style GameSvc fill:#fff4e6
    style SessionSvc fill:#fff4e6
    style AgentSvc fill:#fff4e6
    style GroupChatSvc fill:#fff4e6
    style MessageSvc fill:#fff4e6
    style TapeSvc fill:#fff4e6
```

### 服务初始化顺序

```mermaid
graph TD
    subgraph "基础设施层 Infrastructure"
        LLM[1. LLM Provider]
        DB[2. Database + Repository]
        EB[3. EventBus + Logger]
    end

    subgraph "内存组件层 Memory"
        TM[4. TapeMetadataManager]
        TW[4. TapeWriter]
        SM[5. SessionManager]
    end

    subgraph "应用服务层 Application Services"
        GS[6. GameService]
        AS[7. AgentService]
        SS[8. SessionService]
        GCS[9. GroupChatService]
        MS[10. MessageService]
        TS[11. TapeService]
    end

    LLM --> DB
    DB --> EB
    EB --> TM
    TM --> TW
    TW --> SM
    SM --> GS
    GS --> AS
    AS --> SS
    SS --> GCS
    GCS --> MS
    MS --> TS

    style LLM fill:#e3f2fd
    style DB fill:#e3f2fd
    style EB fill:#e3f2fd
    style TM fill:#f3e5f5
    style TW fill:#f3e5f5
    style SM fill:#f3e5f5
    style GS fill:#fff9c4
    style AS fill:#fff9c4
    style SS fill:#fff9c4
    style GCS fill:#fff9c4
    style MS fill:#fff9c4
    style TS fill:#fff9c4
```

### 服务依赖关系图

```mermaid
graph LR
    subgraph "基础设施 Infrastructure"
        LLMProv[LLM Provider]
        Repository[Repository]
        EventBus[EventBus]
    end

    subgraph "核心组件 Core Components"
        SessionMgr[SessionManager]
        TapeWriter[TapeWriter]
        TapeMeta[TapeMetadataManager]
    end

    GameSvc[GameService]
    AgentSvc[AgentService]
    SessionSvc[SessionService]
    GroupChatSvc[GroupChatService]
    MessageSvc[MessageService]
    TapeSvc[TapeService]

    LLMProv --> GameSvc
    LLMProv --> AgentSvc
    LLMProv --> SessionMgr

    Repository --> GameSvc
    Repository --> AgentSvc

    EventBus --> GameSvc
    EventBus --> AgentSvc
    EventBus --> MessageSvc

    SessionMgr --> AgentSvc
    SessionMgr --> SessionSvc
    SessionMgr --> GroupChatSvc
    SessionMgr --> MessageSvc
    SessionMgr --> TapeSvc

    TapeWriter --> AgentSvc
    TapeWriter --> TapeSvc
    TapeWriter --> SessionMgr

    TapeMeta --> TapeWriter
    TapeMeta --> SessionMgr

    AgentSvc --> SessionSvc

    MessageSvc -.->|"可选引用"| GroupChatSvc

    style LLMProv fill:#bbdefb
    style Repository fill:#bbdefb
    style EventBus fill:#bbdefb
    style SessionMgr fill:#e1bee7
    style TapeWriter fill:#e1bee7
    style TapeMeta fill:#e1bee7
```

## 运行流程详解

### 服务初始化流程

```mermaid
sequenceDiagram
    participant Client as 客户端
    participant AS as ApplicationServices
    participant Infra as 基础设施
    participant Memory as 内存组件
    participant Services as 应用服务

    Client->>AS: ApplicationServices.create(settings)
    activate AS

    Note over AS,Infra: 1. 初始化基础设施
    AS->>Infra: 创建 LLM Provider
    AS->>Infra: 创建 Database + Repository
    AS->>Infra: 创建 EventBus + Logger

    Note over AS,Memory: 2. 初始化内存组件
    AS->>Memory: 创建 TapeMetadataManager
    AS->>Memory: 创建 TapeWriter
    AS->>Memory: 创建 SessionManager
    AS->>Memory: 创建主会话 session:web:main

    Note over AS,Services: 3. 创建应用服务（按依赖顺序）
    AS->>Services: 创建 GameService
    AS->>Services: 创建 AgentService
    AS->>Services: 创建 SessionService
    AS->>Services: 创建 GroupChatService
    AS->>Services: 创建 MessageService
    AS->>Services: 创建 TapeService

    AS-->>Client: 返回 ApplicationServices 实例
    deactivate AS

    Note over Client,Services: 4. 启动服务
    Client->>AS: await services.start()
    AS->>Services: GameService.initialize()
    AS->>Services: AgentService.initialize_agents()
    deactivate AS
```

### 命令发送流程

```mermaid
sequenceDiagram
    participant Web as Web Adapter
    participant MS as MessageService
    participant EB as EventBus
    participant Agent as Agent
    participant SM as SessionManager
    participant TW as TapeWriter

    Web->>MS: send_command(agent_id, command, session_id)
    activate MS

    Note over MS: 规范化 agent_id<br/>normalize_agent_id()

    MS->>MS: 创建 Event 对象
    Note right of MS: type: CHAT<br/>src: "player:web"<br/>dst: ["agent:governor_zhili"]<br/>payload: {query: command}

    MS->>EB: await send_event(event)
    activate EB

    Note over EB: 路由事件到订阅者

    EB->>Agent: 触发 _on_event()
    activate Agent

    Agent->>SM: 获取会话上下文
    SM-->>Agent: session_data

    Agent->>Agent: 处理消息<br/>构建 LLM 上下文

    Agent->>TW: 记录事件到 tape.jsonl
    activate TW
    TW-->>Agent: 写入完成
    deactivate TW

    Agent-->>EB: 返回响应事件
    deactivate Agent

    EB-->>MS: 事件已发送
    deactivate EB

    MS-->>Web: 命令发送完成
    deactivate MS
```

### 会话创建流程

```mermaid
sequenceDiagram
    participant Web as Web Adapter
    participant SS as SessionService
    participant SM as SessionManager
    participant AS as AgentService
    participant Tape as TapeWriter

    Web->>SS: create_session(name, agent_id)
    activate SS

    Note over SS: 生成唯一 session_id<br/>格式: session:web:{agent}:{timestamp}:{uuid}

    SS->>SM: create_session(session_id, created_by, status)
    activate SM
    SM->>SM: 创建会话状态
    SM->>SM: 写入 session_manifest.json
    SM-->>SS: 会话已创建
    deactivate SM

    SS->>SM: set_agent_state(session_id, agent_id, status)
    activate SM
    SM->>SM: 更新会话中的 agent 状态
    SM-->>SS: 状态已更新
    deactivate SM

    Note over SS: 缓存会话标题<br/>_session_titles[session_id] = title

    SS->>SS: 更新 agent 绑定<br/>_current_session_by_agent[agent_id] = session_id

    SS-->>Web: 返回 session_info
    deactivate SS

    Note over Web,Tape: 后续: 事件写入时<br/>TapeWriter 自动创建 tape.jsonl
```

### 消息路由流程

```mermaid
flowchart TD
    Start([接收消息]) --> Parse{消息类型判断}

    Parse -->|/command| Command[命令消息]
    Parse -->|普通文本| Chat[聊天消息]
    Parse -->|/group| GroupMsg[群聊消息]

    Command --> Normalize[规范化 agent_id<br/>strip_agent_prefix]
    Chat --> Normalize
    GroupMsg --> Normalize

    Normalize --> CreateEvent[创建 Event 对象]
    CreateEvent --> SetPayload{设置 payload}

    SetPayload -->|命令| CmdPayload[payload: {query: command}]
    SetPayload -->|聊天| ChatPayload[payload: {message: text}]
    SetPayload -->|群聊| GroupPayload[payload: {message: text}]

    CmdPayload --> Emit
    ChatPayload --> Emit
    GroupPayload --> Emit

    Emit[EventBus.emit] --> Route{路由类型}

    Route -->|单 agent| Single[dst: [agent:xxx]]
    Route -->|多 agent| Multi[dst: [agent:a, agent:b]]
    Route -->|广播| Broadcast[dst: [*]]

    Single --> AgentTrigger[触发 Agent._on_event]
    Multi --> AgentTrigger
    Broadcast --> AllAgents[触发所有订阅者]

    AgentTrigger --> Process[Agent 处理流程]
    Process --> GetSession[获取会话上下文]
    GetSession --> BuildContext[构建 LLM 上下文]
    BuildContext --> CallLLM[调用 LLM]
    CallLLM --> WriteTape[写入 tape.jsonl]
    WriteTape --> Response[发送响应事件]

    AllAgents --> Response
    Response --> End([完成])

    style Start fill:#c8e6c9
    style End fill:#c8e6c9
    style Command fill:#fff9c4
    style Chat fill:#fff9c4
    style GroupMsg fill:#fff9c4
    style AgentTrigger fill:#e1bee7
    style Response fill:#b2dfdb
```

## 服务类详解

### GameService
- 游戏实例的生命周期管理
- 游戏状态的初始化和加载
- Engine 和 TickCoordinator 的协调

### SessionService
- 会话的创建、选择和管理
- 代理与会话的绑定
- 会话上下文管理

### AgentService
- 代理的生命周期管理
- 代理可用性检查
- 动态代理生成

### GroupChatService
- 群聊的创建和管理
- 代理的添加和移除
- 群聊消息处理

### MessageService
- 消息解析（command/chat）
- 事件创建和路由
- 消息投递到代理

### TapeService
- 磁带事件查询
- 子会话管理
- 从磁带文件检索事件

## 开发约束

### 依赖注入原则
- 构造函数注入
- 接口分离
- 依赖倒置

### 生命周期管理
- 严格按照依赖关系初始化
- 反向顺序关闭
- 单例模式用于全局共享组件

### 错误处理
- 显式错误：不使用静默失败或硬编码回退
- 错误传播：异常向上传播
- 日志记录：使用结构化日志
