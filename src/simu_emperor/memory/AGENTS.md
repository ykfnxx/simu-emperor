# Memory 模块文档

## 模块概述

`src/simu_emperor/memory` 模块实现了 V4 版本的事件驱动记忆系统，采用累积摘要和增量加载机制。

### 核心特性
- **累积摘要机制**: 压缩事件时生成和更新摘要
- **增量加载**: 基于 `window_offset` 的增量 tape 加载
- **锚点感知滑动窗口**: 保留关键事件的智能压缩
- **两级搜索**: 元数据过滤 → 事件段搜索
- **V4.2 Phase B 特性**:
  - TapeRepository 注入，支持 tape_events SQLite 双写
  - DB-first 读取策略，JSONL 降级兜底
  - VectorStore 封装向量搜索，带重试逻辑

## 架构设计

### 系统架构图

```mermaid
graph TB
    subgraph "Memory 模块架构"
        subgraph "写入层 (Write Layer)"
            TW[TapeWriter<br/>事件写入]
            TMM[TapeMetadataManager<br/>元数据管理]
        end

        subgraph "上下文管理层 (Context Layer)"
            CM[ContextManager<br/>滑动窗口管理]
            CS[cumulative_summary<br/>累积摘要]
            SI[segment_index<br/>段索引]
            WO[window_offset<br/>增量加载锚点]
        end

        subgraph "搜索层 (Search Layer)"
            TLS[TwoLevelSearcher<br/>两级搜索协调]
            TMI[TapeMetadataIndex<br/>Level 1: 元数据搜索]
            SS[SegmentSearcher<br/>Level 2: 段搜索]
            VS[VectorStore<br/>向量搜索封装]
        end

        subgraph "处理层 (Processing Layer)"
            QP[QueryParser<br/>查询解析]
            SR[StructuredRetriever<br/>检索协调]
        end

        subgraph "存储层 (Storage Layer)"
            TR[TapeRepository<br/>tape_events 仓库]
        end

        subgraph "数据存储 (Storage)"
            tape[tape.jsonl<br/>事件日志]
            meta[tape_meta.jsonl<br/>元数据索引]
            db[(tape_events<br/>SQLite DB)]
        end

        TW --> tape
        TW -.->|V4.2 双写| TR
        TR --> db
        TMM --> meta
        CM --> CS
        CM --> SI
        CM --> WO
        CM -.->|V4.2 DB优先| TR
        CM --> tape
        TMI --> meta
        SS --> tape
        TLS --> TMI
        TLS --> SS
        TLS --> VS
        SR --> QP
        SR --> TLS
        SR --> CM

        style TW fill:#e1f5fe
        style CM fill:#f3e5f5
        style TLS fill:#e8f5e9
        style SR fill:#fff3e0
        style TR fill:#fce4ec
        style VS fill:#e0f2f1
        style tape fill:#eceff1
        style meta fill:#eceff1
        style db fill:#e3f2fd
    end
```

### 数据结构关系图

```mermaid
erDiagram
    TAPE_META ||--o{ TAPE_ENTRY : "contains"
    TAPE_ENTRY ||--o{ SEGMENT_INDEX : "has"
    TAPE_ENTRY ||--|| TAPE_FILE : "indexes"
    TAPE_FILE ||--o{ EVENT : "contains"
    TAPE_EVENTS_DB ||--o{ EVENT : "stores V4.2"

    TAPE_META {
        string file_path "tape_meta.jsonl"
    }

    TAPE_ENTRY {
        string session_id "会话ID"
        string title "LLM生成标题"
        int created_tick "创建时游戏回合"
        string created_time "创建时间戳"
        int event_count "事件数量"
        int window_offset "增量加载锚点"
        string summary "累积摘要"
        segment_index[] segment_index "压缩段索引"
    }

    SEGMENT_INDEX {
        int start "起始位置"
        int end "结束位置"
        string summary "段摘要"
        int tick "游戏回合"
    }

    TAPE_FILE {
        string file_path "tape.jsonl"
    }

    TAPE_EVENTS_DB {
        string table_name "tape_events"
        string db_file "SQLite"
    }

    EVENT {
        string event_id "事件ID"
        string src "来源"
        string[] dst "目标"
        string type "事件类型"
        payload payload "事件内容"
        string timestamp "时间戳"
        string session_id "会话ID"
        int tick "游戏回合"
    }
```

### 组件职责说明

| 层级 | 组件 | 职责 |
|------|------|------|
| **写入层** | TapeWriter | 事件持久化到 tape.jsonl + tape_events (V4.2 双写) |
| | TapeMetadataManager | 管理元数据索引 (tape_meta.jsonl) |
| **上下文层** | ContextManager | 滑动窗口上下文管理，V4.2 DB-first 读取 |
| | cumulative_summary | 累积摘要 (持续更新) |
| | segment_index | 压缩段索引 (已压缩事件的摘要) |
| | window_offset | 增量加载位置锚点 |
| **搜索层** | TwoLevelSearcher | 两级搜索协调器 |
| | TapeMetadataIndex | Level 1: 搜索元数据 |
| | SegmentSearcher | Level 2: 搜索事件段 |
| | VectorStore | V4.2: 向量搜索封装，带重试逻辑 |
| **处理层** | QueryParser | 自然语言查询解析 |
| | StructuredRetriever | 检索路由和结果格式化 |
| **存储层** | TapeRepository | V4.2: tape_events SQLite 仓库 |

## 关键类说明

### TapeWriter
**功能**：事件的写入器，负责将事件写入 `tape.jsonl` 文件

**构造签名 (V4.2)**：
```python
def __init__(
    self,
    tape_dir: str,
    session_id: str,
    ...,
    tape_repository: "TapeRepository | None" = None,  # V4.2 注入
) -> None:
```

**V4 新特性**：
- 首事件检测和自动标题生成
- 同步更新 `tape_meta.jsonl` 的事件计数
- 支持增量加载

**V4.2 Phase B 新特性**：
- **双写机制**：当 `tape_repository` 注入时，`write_event()` 同时写入 `tape_events` SQLite 表
- 关键代码 (L123-129)：
  ```python
  # 先写 JSONL (保持兼容)
  event_id = self._write_to_jsonl(event)
  # 双写到 tape_events DB
  if self._tape_repository is not None:
      self._tape_repository.insert(event)  # 异步双写
  ```

### ContextManager
**功能**：滑动窗口上下文管理器，控制 token 数量并管理历史摘要

**构造签名 (V4.2)**：
```python
def __init__(
    self,
    tape_dir: str,
    session_id: str,
    ...,
    tape_repository: "TapeRepository | None" = None,  # V4.2 注入
) -> None:
```

**滑动窗口策略**：
1. 锚点识别：user_query, response, key GAME_EVENTs
2. 保留最近 N 事件（默认 20）
3. 保留锚点附近 ±K 事件（默认 3）
4. 确保总 token ≤ 阈值（95% context window）

**V4.2 Phase B 读取策略 (DB-first)**：
- `_load_session_events()`：优先通过 `tape_repository.query_by_session()` 从 `tape_events` 读取，失败时降级到 JSONL
- `_read_events_from_offset(offset=N)`：优先 `tape_repository.query_by_session(offset=N)`，降级到 JSONL
- `_count_all_events()`：优先 `tape_repository.count_by_session()`，降级到 JSONL 行数统计
- 降级策略：当 `tape_repository` 为 `None` 或查询失败时，回退到传统 JSONL 读取

### VectorStore (V4.2)
**功能**：向量搜索的封装层，包装 `VectorSearcher` 并提供重试逻辑

**特性**：
- 封装底层 VectorSearcher 实现
- 内置重试机制，处理临时性向量数据库故障
- 统一的搜索接口，屏蔽底层实现细节
- 支持相似度搜索和元数据过滤

**典型用法**：
```python
vector_store = VectorStore(searcher=vector_searcher)
results = await vector_store.search(query_embedding, top_k=5)
```

### TapeRepository (V4.2)
**功能**：`tape_events` SQLite 表的仓库类，提供事件的 DB 持久化和查询

**核心方法**：
| 方法 | 说明 |
|------|------|
| `insert(event)` | 插入事件到 tape_events 表 |
| `query_by_session(session_id, offset=None)` | 按会话查询事件，支持分页 |
| `count_by_session(session_id)` | 统计会话事件数量 |
| `query_by_timerange(start, end)` | 按时间范围查询事件 |

**依赖注入**：
- TapeWriter 和 ContextManager 通过构造函数注入 `tape_repository`
- 注入为 `None` 时自动降级到纯 JSONL 模式（向后兼容）

## 详细运行流程

### 1. 事件写入流程 (TapeWriter.write_event)

```mermaid
sequenceDiagram
    participant Agent as Agent/Caller
    participant TW as TapeWriter
    participant TMM as TapeMetadataManager
    participant Tape as tape.jsonl
    participant Meta as tape_meta.jsonl
    participant TR as TapeRepository
    participant DB as tape_events DB

    Agent->>TW: write_event(event)
    TW->>TW: 提取 agent_id, session_id
    TW->>Tape: 检测是否首事件<br/>(文件不存在或为空)
    alt 首事件
        TW->>TMM: append_or_update_entry()<br/>生成标题
        TMM->>TMM: _generate_title()<br/>调用 LLM 生成会话标题
        TMM->>Meta: 写入新元数据条目
    end
    TW->>Tape: 追加事件到文件
    TW->>TMM: increment_event_count()
    TMM->>Meta: 更新 event_count
    
    rect rgb(240, 248, 255)
        Note over TW,DB: V4.2 双写流程
        alt tape_repository 已注入
            TW->>TR: insert(event)
            TR->>DB: INSERT INTO tape_events
            DB-->>TR: 成功
        else tape_repository 未注入
            Note over TW: 跳过 DB 写入
        end
    end
    
    TW-->>Agent: 返回 event_id
```

### 2. 累积摘要生成流程 (ContextManager.slide_window)

```mermaid
flowchart TD
    A[事件添加到上下文] --> B{总 token > 阈值?}
    B -->|否| C[正常继续]
    B -->|是| D[触发 slide_window]

    D --> E[识别锚点事件]
    E --> F[保留最近 N 事件]
    F --> G[保留锚点 ±K 事件]
    G --> H{仍超阈值?}
    H -->|是| I[继续删除最旧事件]
    H -->|否| J[计算 dropped_events]

    I --> J
    J --> K[生成 dropped 摘要]
    K --> L[合并到累积摘要]
    L --> M[更新 tape_meta.jsonl]
    M --> N[更新 segment_index]
    N --> O[前移 window_offset]

    K --> P[调用 LLM]
    P --> Q{成功?}
    Q -->|是| R[使用 LLM 摘要]
    Q -->|否| S[使用降级摘要]

    style D fill:#ffcdd2
    style L fill:#c8e6c9
    style M fill:#c8e6c9
    style N fill:#c8e6c9
    style O fill:#c8e6c9
```

### 3. Context 滑动窗口流程

```mermaid
flowchart TB
    subgraph "滑动窗口触发条件"
        A1[事件数 > keep_recent]
        A2[总 token > threshold]
    end

    subgraph "锚点识别"
        B1[USER_QUERY]
        B2[RESPONSE/ASSISTANT_RESPONSE]
        B3[GAME_EVENT<br/>allocate_funds, adjust_tax]
    end

    subgraph "保留策略"
        C1[最近 N 事件]
        C2[锚点 ±K 缓冲区]
    end

    subgraph "元数据更新"
        D1[累积摘要更新]
        D2[segment_index 添加]
        D3[window_offset 前移]
    end

    A1 --> E[触发 compact]
    A2 --> E
    E --> F[识别锚点位置]
    F --> G[确定保留索引]
    G --> H[应用保留策略]
    C1 --> H
    C2 --> H
    H --> I[删除其他事件]
    I --> J[更新元数据]
    D1 --> J
    D2 --> J
    D3 --> J

    style E fill:#ffcdd2
    style J fill:#c8e6c9
```

### 4. 跨会话检索流程

```mermaid
sequenceDiagram
    participant Agent as Agent
    participant SR as StructuredRetriever
    participant QP as QueryParser
    participant TLS as TwoLevelSearcher
    participant TMI as TapeMetadataIndex
    participant SS as SegmentSearcher
    participant Tape as tape.jsonl

    Agent->>SR: retrieve(query)
    SR->>QP: parse(query)
    QP-->>SR: StructuredQuery

    SR->>SR: 判断 scope
    alt current_session
        SR->>SR: 从 ContextManager 获取
    else cross_session
        SR->>TLS: search(query)
        TLS->>TMI: search_tape_metadata()<br/>Level 1 搜索
        TMI-->>TLS: matching_entries[]

        par 并行搜索多个 tape
            TLS->>SS: search_segments()<br/>Level 2 搜索
            SS->>Tape: 读取 tape.jsonl
            Tape-->>SS: events[]
            SS->>SS: 分段并评分
        end

        SS-->>TLS: TapeSegment[]
        TLS-->>SR: 排序后的 segments
    end

    SR->>SR: 根据 depth 格式化结果
    SR-->>Agent: RetrievalResult
```

### 5. 增量加载流程 (从 tape 加载到 ContextManager)

```mermaid
flowchart TB
    A[ContextManager 初始化] --> B[读取 tape_meta.jsonl]
    B --> C{entry 存在?}
    C -->|是| D[加载 window_offset<br/>和 cumulative_summary]
    C -->|否| E[使用默认值<br/>offset=0, summary=""]

    D --> F{tape_repository<br/>已注入?}
    E --> F
    
    F -->|是| G[V4.2 DB-first]
    F -->|否| H[传统 JSONL 读取]
    
    subgraph "V4.2 DB-first 读取"
        G --> G1[query_by_session]
        G1 --> G2{成功?}
        G2 -->|是| I[使用 DB 数据]
        G2 -->|否| H[降级到 JSONL]
    end
    
    subgraph "JSONL 读取"
        H --> H1[从 window_offset<br/>读取 tape.jsonl]
        H1 --> I
    end
    
    I --> J[计算事件 tokens]
    J --> K{token > 阈值?}
    K -->|是| L[触发自动 compact]
    K -->|否| M[加载完成]

    L --> N[生成 dropped 摘要]
    N --> O[更新 segment_index]
    O --> P[前移 window_offset]
    P --> Q[写入 tape_meta.jsonl]
    Q --> M

    M --> R[返回 LLM messages]

    style D fill:#e1f5fe
    style G fill:#e3f2fd
    style H fill:#fff3e0
    style L fill:#ffcdd2
    style O fill:#c8e6c9
    style P fill:#c8e6c9
```

### 6. 两级搜索流程 (TwoLevelSearcher)

```mermaid
flowchart TB
    subgraph "Level 1: 元数据搜索"
        A1[读取 tape_meta.jsonl]
        A2[计算 entry 评分]
        A3[匹配 title]
        A4[匹配 summary]
        A5[匹配 segment_index]
    end

    subgraph "Level 2: 段搜索"
        B1[并发读取多个 tape.jsonl]
        B2[按 SEGMENT_SIZE 分段]
        B3[计算 segment 评分]
        B4[合并并排序]
    end

    subgraph "评分权重"
        C1[Title match: 0.4]
        C2[Summary match: 0.2]
        C3[Segment match: 0.1]
    end

    A1 --> A2
    A3 --> A2
    A4 --> A2
    A5 --> A2
    A2 --> D{评分 > 0?}
    D -->|是| E[返回 matching_entries]
    D -->|否| F[返回空列表]

    E --> B1
    B1 --> B2
    B2 --> B3
    B3 --> B4
    B4 --> G[返回 top N segments]

    C1 -.-> A3
    C2 -.-> A4
    C3 -.-> A5

    style A2 fill:#fff9c4
    style B3 fill:#fff9c4
    style E fill:#c8e6c9
```

## Tape 文件格式

### tape.jsonl 结构

```mermaid
graph LR
    subgraph "tape.jsonl (事件日志)"
        E0["Line 0: Event 0<br/>event_id: evt_xxx<br/>type: user_query"]
        E1["Line 1: Event 1<br/>event_id: evt_yyy<br/>type: assistant_response"]
        E2["Line 2: Event 2<br/>event_id: evt_zzz<br/>type: tool_result"]
        E3["Line 3: Event 3<br/>..."]
        EN["Line N: Event N<br/>..."]
    end

    subgraph "位置索引"
        P0["Position 0"]
        P1["Position 1"]
        P2["Position 2"]
        P3["Position 3"]
        PN["Position N"]
    end

    E0 --> P0
    E1 --> P1
    E2 --> P2
    E3 --> P3
    EN --> PN

    subgraph "window_offset"
        WO["当前加载起点<br/>跳过 0~offset-1"]
    end

    P0 -.->|已压缩| WO
    P1 -.->|已压缩| WO
    P2 -.->|已压缩| WO

    style E0 fill:#cfd8dc
    style E1 fill:#cfd8dc
    style E2 fill:#cfd8dc
    style E3 fill:#a5d6a7
    style EN fill:#a5d6a7
```

### tape.jsonl 事件格式

```json
{
  "event_id": "evt_20260314120000_a1b2c3d4",
  "src": "agent:governor_fujian",
  "dst": ["player"],
  "type": "command",
  "payload": {...},
  "timestamp": "2026-03-14T12:00:00.123456Z",
  "session_id": "session:web:governor_fujian:...",
  "tick": 42
}
```

### tape_meta.jsonl 结构

```mermaid
graph TB
    subgraph "tape_meta.jsonl (元数据索引)"
        direction TB
        M1["Entry 1: session_A<br/>title: 福建赈灾<br/>window_offset: 10"]
        M2["Entry 2: session_B<br/>title: 税收调整<br/>window_offset: 5"]
        M3["Entry 3: session_C<br/>title: 人事任免<br/>window_offset: 0"]
    end

    subgraph "Entry 详细结构"
        MT["title: LLM 生成标题"]
        ME["event_count: 事件总数"]
        MO["window_offset: 增量加载锚点"]
        MS["summary: 累积摘要"]
        MI["segment_index: 压缩段列表"]
    end

    M1 --> MT
    M1 --> ME
    M1 --> MO
    M1 --> MS
    M1 --> MI

    subgraph "segment_index 结构"
        SI1["Segment 1: start=0, end=9<br/>summary: 初始对话"]
        SI2["Segment 2: start=10, end=19<br/>summary: 拨款流程"]
        SI3["Segment 3: start=20, end=29<br/>summary: 完成确认"]
    end

    MI --> SI1
    MI --> SI2
    MI --> SI3

    style M1 fill:#e1f5fe
    style MI fill:#f3e5f5
    style SI1 fill:#fff9c4
    style SI2 fill:#fff9c4
    style SI3 fill:#fff9c4
```

### tape_meta.jsonl 条目格式

```json
{
  "session_id": "session:web:...",
  "title": "福建赈灾拨款",
  "created_tick": 42,
  "created_time": "2026-03-14T12:00:00Z",
  "last_updated_tick": 45,
  "last_updated_time": "2026-03-14T15:30:00Z",
  "event_count": 15,
  "window_offset": 10,
  "summary": "处理福建赈灾事宜，完成三次拨款申请",
  "segment_index": [
    {"start": 0, "end": 9, "summary": "福建赈灾申请", "tick": 42}
  ]
}
```

### 索引结构映射关系

```mermaid
graph LR
    subgraph "tape.jsonl"
        T0["Pos 0-9: 10 events"]
        T1["Pos 10-19: 10 events"]
        T2["Pos 20-29: 10 events"]
    end

    subgraph "segment_index"
        S0["start: 0, end: 9<br/>summary: 段摘要 1"]
        S1["start: 10, end: 19<br/>summary: 段摘要 2"]
        S2["start: 20, end: 29<br/>summary: 段摘要 3"]
    end

    subgraph "window_offset 状态"
        WO["window_offset: 20<br/>只加载 Pos 20+ 的数据"]
    end

    T0 -.->|已压缩| S0
    T1 -.->|已压缩| S1
    T2 -->|在内存中| WO
    S2 -.->|对应| WO

    style T0 fill:#cfd8dc
    style T1 fill:#cfd8dc
    style T2 fill:#a5d6a7
    style S0 fill:#fff9c4
    style S1 fill:#fff9c4
    style S2 fill:#a5d6a7
```

### manifest.json 结构 (V3 遗留，V4 已弃用)

> **注意**: V4 中 `ManifestIndex` 已弃用，请使用 `TapeMetadataManager` 和 `SessionManager`。

```mermaid
graph TB
    subgraph "manifest.json (V3, 已弃用)"
        VER["version: 1.0"]
        LU["last_updated: timestamp"]
        SS["sessions: {}"]
    end

    subgraph "session 结构"
        SID["session_id"]
        AG["agents: {}"]
    end

    subgraph "agent_session 数据"
        ST["start_time"]
        ET["end_time"]
        TS["turn_start / turn_end"]
        KT["key_topics: []"]
        SM["summary: string"]
        EC["event_count: int"]
    end

    VER --> SS
    LU --> SS
    SS --> SID
    SID --> AG
    AG --> ST
    AG --> ET
    AG --> TS
    AG --> KT
    AG --> SM
    AG --> EC

    style VER fill:#ffcdd2
    style SS fill:#ffcdd2
```

## 开发约束

### 1. 并发安全
- 原子写入：所有文件操作使用 temp file + rename 模式
- 幂等操作：更新操作设计为幂等

### 2. 性能优化
- 增量加载：基于 `window_offset` 的增量 tape 读取
- 并发搜索：使用 `asyncio.gather` 并行搜索多个 tapes
- **V4.2**: DB-first 读取策略，SQLite 索引优化查询性能

### 3. 错误处理
- 静默失败：索引搜索失败不应阻塞主要流程
- 降级策略：LLM 调用失败时使用简单摘要
- **V4.2**: DB 查询失败时自动降级到 JSONL 读取

### 4. V4.2 兼容性约束
- **向后兼容**：`tape_repository` 为 `None` 时完全兼容 V4.1 行为
- **双写不阻塞**：DB 写入失败不影响 JSONL 写入成功
- **优雅降级**：DB 不可用时自动回退到 JSONL，不抛出异常
