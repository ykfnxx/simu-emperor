# Persistence 模块文档

## 模块概述

**Persistence 模块** 是数据持久化层，负责管理游戏状态和 Agent 相关数据的持久化存储。

### 核心职责
- **数据库连接管理**: 创建、管理和关闭 SQLite 数据库连接
- **数据持久化**: 保存和加载游戏状态（NationData）及 Agent 配置
- **序列化处理**: 处理复杂对象（特别是 Decimal 类型）与 JSON 的转换
- **Repository 模式封装**: 提供高级 API 抽象底层 SQL 操作

## 架构设计

### 模块架构图

```mermaid
graph TB
    subgraph "Application Layer (应用层)"
        GameService[GameService]
        AgentService[AgentService]
        SessionService[SessionService]
        MemoryService[MemoryService]
    end

    subgraph "Persistence Layer (持久化层)"
        direction TB

        subgraph "Repositories (database.py 单例连接)"
            GameRepo[GameRepository]
            AgentRepo[AgentRepository]
            IncidentRepo[IncidentRepository]
        end

        subgraph "Repositories (独立连接)"
            TapeRepo[TapeRepository]
        end

        subgraph "Serialization"
            Serial[Serialization]
        end

        subgraph "Database"
            DBMgr[DatabaseManager]
        end
    end

    subgraph "SQLite Database (7 张表)"
        GameState[(game_state)]
        AgentState[(agent_state)]
        TurnMetrics[(turn_metrics)]
        Events[(events)]
        Incidents[(incidents)]
        TapeEvents[(tape_events)]
        FailedEmbed[(failed_embeddings)]
    end

    %% Application to Persistence
    GameService -->|load_nation_data| GameRepo
    GameService -->|save_nation_data| GameRepo
    AgentService -->|get_active_agents| AgentRepo
    AgentService -->|set_agent_active| AgentRepo
    AgentService -->|save_agent_config| AgentRepo
    AgentService -->|load_agent_config| AgentRepo
    MemoryService -->|event_persistence| TapeRepo

    %% Repository to Serialization
    GameRepo -->|serialize| Serial
    GameRepo -->|deserialize| Serial
    AgentRepo -.->|no Decimal| Serial

    %% Repository to Database (单例连接)
    GameRepo -->|get_connection| DBMgr
    AgentRepo -->|get_connection| DBMgr
    IncidentRepo -->|get_connection| DBMgr
    Serial -.->|no DB| DBMgr

    %% TapeRepository 独立连接
    TapeRepo -->|own aiosqlite| TapeEvents
    TapeRepo -->|own aiosqlite| FailedEmbed

    %% Database to Tables
    DBMgr -->|query| GameState
    DBMgr -->|query| AgentState
    DBMgr -->|query| TurnMetrics
    DBMgr -->|query| Events
    DBMgr -->|query| Incidents

    style GameService fill:#e1f5fe
    style AgentService fill:#e1f5fe
    style SessionService fill:#e1f5fe
    style MemoryService fill:#e1f5fe
    style GameRepo fill:#fff3e0
    style AgentRepo fill:#fff3e0
    style IncidentRepo fill:#fff3e0
    style TapeRepo fill:#ffccbc
    style Serial fill:#f3e5f5
    style DBMgr fill:#e8f5e9
```

### 数据库表结构关系 (V4.2 - 7 张表)

```mermaid
erDiagram
    game_state ||--o{ turn_metrics : "has"
    game_state {
        int id PK "固定值=1"
        text game_id "游戏标识"
        int turn "当前tick数"
        text state_json "NationData JSON"
        timestamp updated_at "更新时间"
    }

    turn_metrics {
        int id PK "自增"
        text game_id FK
        int turn "回合数"
        text metrics_json "指标JSON"
        timestamp created_at "创建时间"
    }

    agent_state {
        text agent_id PK
        boolean is_active "是否活跃"
        text soul_markdown "角色定义"
        text data_scope_yaml "数据权限"
        timestamp updated_at "更新时间"
    }

    events {
        text event_id PK
        text session_id "会话ID"
        text root_event_id "根事件ID"
        text parent_event_id "父事件ID"
        text src "源"
        text dst "目标"
        text type "类型"
        text payload "载荷JSON"
        timestamp timestamp "事件时间"
        timestamp created_at "创建时间"
    }

    incidents {
        text incident_id PK
        text title "标题"
        text description "描述"
        text source "来源"
        int created_tick "创建tick"
        int expired_tick "过期tick"
        int remaining_ticks "剩余tick"
        text status "状态"
        text effects_json "效果JSON"
        timestamp created_at "创建时间"
        timestamp expired_at "过期时间"
    }

    tape_events {
        int id PK "自增"
        text event_id UK "事件ID唯一"
        text session_id "会话ID"
        text agent_id "Agent ID"
        text src "源"
        text dst "目标JSON"
        text type "类型"
        text payload "载荷JSON"
        text timestamp "事件时间"
        int tick "游戏tick"
        text parent_event_id "父事件ID"
        text root_event_id "根事件ID"
        timestamp created_at "创建时间"
    }

    failed_embeddings {
        int id PK "自增"
        text segment_id UK "段落ID唯一"
        text summary "摘要内容"
        text metadata "元数据JSON"
        text error "错误信息"
        int retry_count "重试次数"
        timestamp created_at "创建时间"
        timestamp last_retry_at "最后重试时间"
    }

    game_state ||--o{ turn_metrics : "1:N"
```

### Decimal 序列化处理流程

```mermaid
flowchart LR
    subgraph "序列化 (保存)"
        A[NationData] --> B[asdict]
        B --> C[_decimal_to_str]
        C --> D[json.dumps]
        D --> E[JSON字符串]
    end

    subgraph "反序列化 (加载)"
        F[JSON字符串] --> G[json.loads]
        G --> H[_str_to_decimal]
        H --> I[ProvinceData重建]
        I --> J[NationData对象]
    end

    subgraph "白名单机制"
        K[DECIMAL_FIELDS] --> L{字段名匹配?}
        L -->|是| M[转换为Decimal]
        L -->|否| N[保持字符串]
    end

    H --> K
    K --> L

    style A fill:#e3f2fd
    style E fill:#c8e6c9
    style J fill:#c8e6c9
    style K fill:#fff9c4
```

## 关键类说明

### GameRepository
游戏状态持久化管理

**核心方法**:
```python
async def load_nation_data() -> NationData
async def save_nation_data(nation: NationData) -> None
async def get_current_tick() -> int
async def initialize_default_state() -> None
```

### AgentRepository
Agent 状态和配置管理

**核心方法**:
```python
async def get_active_agents() -> list[str]
async def set_agent_active(agent_id: str, is_active: bool = True) -> None
async def save_agent_config(agent_id: str, soul_markdown: str = None, data_scope_yaml: str = None)
async def load_agent_config(agent_id: str) -> dict
```

### IncidentRepository (Phase A - V4)
Incident 持久化管理

**核心方法**:
```python
async def save_incident(incident, tick: int) -> None
async def expire_incident(incident_id: str, tick: int) -> None
async def load_active_incidents() -> list[Incident]
async def get_incident_history(limit: int = 20, source: str = None) -> list[dict]
```

### TapeRepository (Phase B - V4.2)
磁带式事件存储仓库

> ⚠️ **重要**: TapeRepository 拥有**独立的 aiosqlite 连接**，与 database.py 模块级单例连接分离。需手动调用 `initialize()` 和 `close()` 管理生命周期。

**核心方法**:
```python
# 生命周期管理
def __init__(db_path: str = "game.db")
async def initialize() -> None      # 创建独立数据库连接
async def close() -> None           # 关闭连接

# tape_events 表操作
async def insert_event(event: Event, agent_id: str, tick: int = None) -> None
async def query_events(
    session_id: str = None,
    agent_id: str = None,
    event_type: str = None,
    tick: int = None,
    limit: int = 100,
    offset: int = 0
) -> list[dict]
async def count_events(session_id: str) -> int
async def query_by_session(
    session_id: str,
    agent_id: str = None,
    offset: int = 0,
    limit: int = 10000
) -> list[dict]  # ORDER BY timestamp ASC, id ASC
async def count_by_session(session_id: str, agent_id: str = None) -> int

# failed_embeddings 表操作
async def record_failed_embedding(
    segment_id: str,
    summary: str,
    metadata: dict,
    error: str
) -> None
async def get_failed_embeddings(limit: int = 100) -> list[dict]
async def mark_embedding_retried(segment_id: str) -> None
async def remove_failed_embedding(segment_id: str) -> None
```

## 数据库表结构

### game_state
```sql
CREATE TABLE game_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    state_json TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### agent_state
```sql
CREATE TABLE agent_state (
    agent_id TEXT PRIMARY KEY,
    is_active INTEGER NOT NULL DEFAULT 0,
    soul_markdown TEXT,
    data_scope_yaml TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### events
```sql
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    root_event_id TEXT NOT NULL,
    parent_event_id TEXT,
    src TEXT NOT NULL,
    dst TEXT NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
```

### incidents (Phase A - V4)
```sql
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    source TEXT NOT NULL,
    created_tick INTEGER NOT NULL,
    expired_tick INTEGER,
    remaining_ticks INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    effects_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expired_at TEXT
);
```

### tape_events (Phase B - V4.2)
```sql
CREATE TABLE IF NOT EXISTS tape_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    src TEXT NOT NULL,
    dst TEXT NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    tick INTEGER,
    parent_event_id TEXT,
    root_event_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### failed_embeddings (Phase B - V4.2)
```sql
CREATE TABLE IF NOT EXISTS failed_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id TEXT UNIQUE NOT NULL,
    summary TEXT NOT NULL,
    metadata TEXT NOT NULL,
    error TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    last_retry_at TEXT
);
```

## 开发约束

### 连接管理

**模块级单例连接** (database.py 管理):
```python
# 应用启动时初始化
await init_database()

# 获取连接（GameRepository, AgentRepository, IncidentRepository 使用）
conn = await get_connection()

# 应用关闭时清理
await close_database()
```

**TapeRepository 独立连接** (V4.2 新增):
```python
# TapeRepository 有自己的 aiosqlite 连接，不使用模块单例
tape_repo = TapeRepository(db_path="game.db")
await tape_repo.initialize()  # 创建独立连接

# 使用...
await tape_repo.insert_event(event, agent_id, tick)

# 必须手动关闭
await tape_repo.close()
```

> ⚠️ **注意**: TapeRepository 的独立连接设计是为了隔离事件存储的 IO 负载，避免阻塞主数据库连接。

### V4 推荐 API
```python
# 使用 NationData 对象
nation = await repo.load_nation_data()
await repo.save_nation_data(nation)
```

### Decimal 处理
- 序列化自动处理 Decimal → str
- 反序列化自动处理 str → Decimal（白名单）

## 详细运行流程

### 数据库初始化流程

```mermaid
sequenceDiagram
    participant App as Application
    participant DB as DatabaseManager
    participant SQLite as SQLite数据库

    App->>DB: init_database(db_path)
    DB->>SQLite: aiosqlite.connect(db_path)
    SQLite-->>DB: Connection
    DB->>DB: _create_schema(conn)
    
    Note over DB,SQLite: 创建 7 张表
    DB->>SQLite: EXECUTE CREATE TABLE game_state
    DB->>SQLite: EXECUTE CREATE TABLE turn_metrics
    DB->>SQLite: EXECUTE CREATE TABLE agent_state
    DB->>SQLite: EXECUTE CREATE TABLE events
    DB->>SQLite: EXECUTE CREATE TABLE incidents (V4)
    DB->>SQLite: EXECUTE CREATE TABLE tape_events (V4.2)
    DB->>SQLite: EXECUTE CREATE TABLE failed_embeddings (V4.2)
    
    DB->>SQLite: EXECUTE INSERT 默认状态
    DB->>SQLite: EXECUTE CREATE INDEXES
    DB->>SQLite: COMMIT
    DB-->>App: Connection
```

### NationData 加载流程

```mermaid
sequenceDiagram
    participant App as GameService
    participant Repo as GameRepository
    participant Serial as Serialization
    participant DB as Database

    App->>Repo: load_nation_data()
    Repo->>Repo: _get_conn()
    Repo->>DB: SELECT state_json FROM game_state
    DB-->>Repo: JSON字符串
    alt 状态不存在
        Repo-->>App: NationData(turn=0)
    else 状态存在
        Repo->>Serial: deserialize_nation_data(json_str)
        Serial->>Serial: json.loads()
        Serial->>Serial: _str_to_decimal(data)
        Note over Serial: 白名单匹配<br/>Decimal字段转换
        Serial->>Serial: 重建ProvinceData对象
        Serial-->>Repo: NationData对象
        Repo-->>App: NationData对象
    end
```

### NationData 保存流程

```mermaid
sequenceDiagram
    participant App as GameService
    participant Repo as GameRepository
    participant Serial as Serialization
    participant DB as Database

    App->>Repo: save_nation_data(nation)
    Repo->>Serial: serialize_nation_data(nation)
    Serial->>Serial: asdict(nation)
    Serial->>Serial: _decimal_to_str(dict)
    Note over Serial: 递归转换<br/>Decimal → str
    Serial->>Serial: json.dumps()
    Serial-->>Repo: JSON字符串
    Repo->>DB: INSERT/UPDATE game_state
    Note over DB: ON CONFLICT(id) DO UPDATE
    DB->>DB: COMMIT
    Repo-->>App: None
```

### Agent 配置读写流程

```mermaid
sequenceDiagram
    participant App as AgentService
    participant Repo as AgentRepository
    participant DB as Database

    Note over App,DB: 保存配置
    App->>Repo: save_agent_config(agent_id, soul, scope)
    Repo->>DB: INSERT OR REPLACE agent_state
    DB->>DB: COMMIT
    Repo-->>App: None

    Note over App,DB: 加载配置
    App->>Repo: load_agent_config(agent_id)
    Repo->>DB: SELECT soul_markdown, data_scope_yaml
    DB-->>Repo: 行数据
    alt Agent不存在
        Repo-->>App: {soul: None, scope: None}
    else Agent存在
        Repo-->>App: {soul: "...", scope: "..."}
    end

    Note over App,DB: 设置活跃状态
    App->>Repo: set_agent_active(agent_id, is_active)
    Repo->>DB: INSERT/UPDATE agent_state
    DB->>DB: COMMIT
    Repo-->>App: None
```

### 事件记录流程

```mermaid
flowchart TD
    A[事件发生] --> B{事件类型}
    B -->|COMMAND| C[玩家命令]
    B -->|QUERY| D[玩家查询]
    B -->|RESPONSE| E[Agent响应]
    B -->|GAME_EVENT| F[游戏状态变化]

    C --> G[EventLogger]
    D --> G
    E --> G
    F --> G

    G --> H[写入events表]
    H --> I[记录session_id]
    H --> J[记录root_event_id]
    H --> K[记录parent_event_id]

    I --> L[事件链追踪]
    J --> L
    K --> L

    style A fill:#e3f2fd
    style G fill:#fff3e0
    style H fill:#c8e6c9
    style L fill:#f3e5f5
```

### TapeRepository 生命周期流程 (V4.2)

```mermaid
sequenceDiagram
    participant App as MemoryService
    participant Repo as TapeRepository
    participant DB as SQLite

    Note over App,DB: 初始化阶段
    App->>Repo: new TapeRepository(db_path)
    App->>Repo: initialize()
    Repo->>DB: aiosqlite.connect(db_path)
    DB-->>Repo: Connection (独立连接)
    Repo-->>App: Ready

    Note over App,DB: 事件记录
    App->>Repo: insert_event(event, agent_id, tick)
    Repo->>DB: INSERT INTO tape_events
    DB-->>Repo: OK

    Note over App,DB: 事件查询
    App->>Repo: query_by_session(session_id)
    Repo->>DB: SELECT * FROM tape_events WHERE...
    DB-->>Repo: Rows
    Repo-->>App: Event List

    Note over App,DB: Embedding 失败记录
    App->>Repo: record_failed_embedding(...)
    Repo->>DB: INSERT INTO failed_embeddings
    DB-->>Repo: OK

    Note over App,DB: 关闭阶段
    App->>Repo: close()
    Repo->>DB: conn.close()
    DB-->>Repo: Closed

    style App fill:#e1f5fe
    style Repo fill:#ffccbc
    style DB fill:#e8f5e9
```
