# V5 Architecture: PydanticAI + ZeroMQ + SeekDB Full Rewrite

> Date: 2026-03-28
> Status: Draft
> Scope: Complete rewrite of agent module using PydanticAI, ZeroMQ IPC, SeekDB Server

## 1. Background & Motivation

### Current System (V4)

V4 uses a single-process asyncio architecture with:
- In-process EventBus (pub/sub with 3-tier routing)
- JSONL file-based tape storage + ChromaDB vector search
- File-driven agent configuration (soul.md + data_scope.yaml)
- Custom ReAct loop in a 1457-line Agent class
- 14 tools across 4 categories (query, action, memory, session)
- Three-tier skill caching (LRU + mtime + filesystem)

### Problems Addressed

1. **No concurrency isolation**: All agents share one asyncio event loop; a blocking agent affects all others
2. **Tape storage limitations**: JSONL files cannot be queried; `tape_meta.jsonl` rewrites the entire file on every update (O(n) write amplification); ChromaDB is a separate vector store requiring index synchronization
3. **No horizontal scaling**: Single-process architecture cannot scale beyond one machine
4. **Limited observability**: No structured metrics on LLM call latency, token usage, or tool call frequency
5. **Tight coupling**: Agent lifecycle, LLM calling, tool dispatch, memory management, and event handling are intertwined in one large class

### Non-Goals

- Backward compatibility with V4 (this is a complete rewrite)
- Preserving the current JSONL file format
- Supporting the current CLI interface (will be replaced by API Gateway)

## 2. Architecture Overview

### 2.1 Process Model: Three Processes

Three process types communicating via ZeroMQ IPC:

```
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │ API Gateway  │      │    Engine    │      │   Workers    │  │
│  │ (FastAPI/WS) │      │ (Tick/State) │      │ (PydanticAI) │  │
│  └──────┬───────┘      └──────┬───────┘      └──────┬───────┘  │
│         │                     │                     │          │
│         │    ┌────────────────┼────────────────┐    │          │
│         │    │   ZeroMQ IPC   │                │    │          │
│         └────┼────────────────┼────────────────┼────┘          │
│              │                │                │               │
│              │  ROUTER/DEALER │   PUB/SUB      │               │
│              │  ipc://@simu   │  ipc://@simu   │               │
│              │  _router       │  _broadcast    │               │
│              │                │                │               │
│              └────────────────┼────────────────┘               │
│                               │                                │
│                        ┌──────┴──────┐                         │
│                        │   SeekDB    │                         │
│                        │  (Docker)   │                         │
│                        └─────────────┘                         │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

| Process | Count | Responsibility | Key Dependencies |
|---------|-------|----------------|------------------|
| **API Gateway** | 1 | HTTP/WS request handling, message conversion | FastAPI, ZeroMQ DEALER |
| **Engine** | 1 | Tick loop, game state, incident management | ZeroMQ PUB, SQLite, SeekDB |
| **Agent Workers** | 1-N | Stateless agent execution, event processing | ZeroMQ DEALER+SUB, PydanticAI, SeekDB |

**Key Difference from V4**: No Orchestrator process. Workers are stateless and build agents on-demand per event.

### 2.2 Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Agent framework** | PydanticAI | Agent definition, tool calling, typed context, history management |
| **Message queue** | ZeroMQ IPC (ROUTER/DEALER + PUB/SUB) | Inter-process event routing, no external broker |
| **Tape storage** | SeekDB Server (Docker) | Event logs with full-text + vector + structured queries |
| **Permissions** | SeekDB GRANT/REVOKE | Table/column-level access control for agent isolation |
| **Game state** | SQLite | Engine-internal game state (unchanged from V4) |
| **LLM provider** | OpenAI-compatible API | Via PydanticAI's `Agent('openai:gpt-4o', ...)` |
| **Monitoring** | Prometheus + custom metrics | LLM latency, token usage, tool frequency, worker health |

## 3. ZeroMQ Topology

### 3.1 Socket Types & Addresses

```
Point-to-Point Communication:
  ROUTER (Gateway binds)     → ipc://@simu_router
  DEALER (Workers connect)   → ipc://@simu_router

Broadcast Communication:
  PUB (Engine binds)         → ipc://@simu_broadcast
  SUB (Workers connect)      → ipc://@simu_broadcast
```

### 3.2 ROUTER/DEALER Pattern

The ROUTER/DEALER pattern provides fair-queued load balancing:

```
Gateway (ROUTER):
  - Binds ipc://@simu_router
  - Receives events from WebSocket/HTTP
  - Routes events to workers by fair queue (ZeroMQ built-in)
  - No identity-based routing needed (workers are stateless)

Workers (DEALER):
  - Connect to ipc://@simu_router
  - Receive events, fair-queued by ZeroMQ
  - Process event → build agent → run → save → respond
  - Worker can process ANY agent's event (stateless design)
```

**Fair Queue Load Balancing**:
- ZeroMQ automatically distributes messages across connected workers
- If 3 workers are connected, messages rotate: W1 → W2 → W3 → W1 → ...
- No manual assignment needed (unlike RabbitMQ with Orchestrator)

### 3.3 PUB/SUB Pattern

The PUB/SUB pattern handles broadcast events:

```
Engine (PUB):
  - Binds ipc://@simu_broadcast
  - Publishes tick events, state changes, system notifications
  - Topics: tick.*, system.*, state.*

Workers (SUB):
  - Connects to ipc://@simu_broadcast
  - Subscribes to tick.*, system.*
  - Handles tick events (e.g., periodic agent actions)
```

### 3.4 Message Protocol

```python
# Serialized as MessagePack (binary, efficient)
@dataclass
class Event:
    event_id: str              # UUID
    event_type: str            # CHAT, TICK, AGENT_MESSAGE, etc.
    src: str                   # "player:web:client_001"
    dst: list[str]             # ["agent:governor_zhili"]
    session_id: str            # "session:web:xxx"
    role: str | None           # Target agent role (for multi-agent)
    payload: dict              # Event-specific data
    timestamp: str             # ISO 8601
    parent_event_id: str | None
    root_event_id: str | None
```

### 3.5 No Redis Required

ZeroMQ eliminates the need for Redis:
- **No config caching**: Workers load config directly from SeekDB per event
- **No cross-process state**: Workers are stateless, no shared state needed
- **No pub/sub broker**: ZeroMQ handles all IPC without external dependencies

## 4. PydanticAI Agent Implementation

### 4.1 Why PydanticAI (Not OpenAI Agent SDK)

| Aspect | OpenAI Agent SDK | PydanticAI |
|--------|------------------|------------|
| Lock-in | OpenAI-only | Multi-provider (OpenAI, Anthropic, etc.) |
| Python-native | API follows JS patterns | Built for Python idioms |
| Type safety | Basic type hints | Full Pydantic validation |
| Context model | dict-based | Typed BaseModel with validation |
| History control | Automatic (SDK manages) | Explicit (you control) |
| Tool definition | @function_tool | @agent.tool with typed context |

### 4.2 Agent with Typed Context

```python
from pydantic_ai import Agent, RunContext
from pydantic import BaseModel

class AgentContext(BaseModel):
    """Typed context injected into every tool call."""
    agent_id: str
    session_id: str
    permissions: list[str]
    mq_publisher: MQPublisher
    game_state_reader: GameStateReader
    seekdb_client: SeekDBClient

    def has_permission(self, tool_name: str, resource: str = "*") -> bool:
        """Check GRANT-based permissions from SeekDB."""
        return f"{tool_name}:{resource}" in self.permissions

# Agent definition
agent = Agent(
    'openai:gpt-4o',
    deps_type=AgentContext,
    output_type=str,
)
```

### 4.3 Dynamic System Prompt

```python
@agent.system_prompt
async def build_system_prompt(ctx: RunContext[AgentContext]) -> str:
    """Load soul + skills dynamically from SeekDB."""
    soul = await ctx.deps.seekdb_client.load_soul(ctx.deps.agent_id)
    skills = await ctx.deps.seekdb_client.load_skills(ctx.deps.agent_id)
    return f"{soul}\n\n# Skills\n{skills}"
```

### 4.4 Tool Definition with Permissions

```python
@agent.tool
async def query_province_data(
    ctx: RunContext[AgentContext],
    province_id: str,
    field: str | None = None,
) -> str:
    """查询指定省份的经济数据。

    Args:
        province_id: 省份ID，如 'zhili', 'jiangnan'
        field: 可选，查询特定字段。不填则返回全部。
    """
    # Check GRANT-based permissions
    if not ctx.deps.has_permission("query_province_data", province_id):
        return "你没有查询该省份数据的权限"

    data = await ctx.deps.game_state_reader.get_province(province_id)
    if not data:
        return f"省份 {province_id} 不存在"

    if field:
        return f"{province_id}.{field} = {data.get(field, '未知')}"
    return format_province_data(data)

@agent.tool
async def send_message(
    ctx: RunContext[AgentContext],
    target_role: str,
    message: str,
) -> str:
    """向其他官员发送消息。

    Args:
        target_role: 目标官员角色ID，如 'governor_jiangnan'
        message: 消息内容
    """
    # Publish new event for target agent
    await ctx.deps.mq_publisher.publish(
        event_type="AGENT_MESSAGE",
        role=target_role,
        payload={
            "message": message,
            "from": ctx.deps.agent_id,
            "session_id": ctx.deps.session_id,
        },
    )
    return f"消息已发送至 {target_role}"
```

### 4.5 Running Agent with Full History Control

```python
class AgentRunner:
    def __init__(self, seekdb_client: SeekDBClient):
        self.seekdb = seekdb_client

    async def run(self, event: Event, context: AgentContext) -> str:
        # Load history from SeekDB (you control this)
        history = await self.seekdb.load_history(context.session_id)

        # Run agent with full control
        result = await agent.run(
            user_prompt=event.payload.get("message", ""),
            message_history=history,
            deps=context,
        )

        # Save new messages to SeekDB
        await self.seekdb.save_messages(context.session_id, result.new_messages())

        return result.output
```

### 4.6 V4 → V5 Concept Mapping

| V4 Concept | V5 (PydanticAI) Equivalent | Notes |
|-----------|---------------------------|-------|
| `Agent.__init__()` reads soul.md | `@agent.system_prompt` async function | Dynamic load from SeekDB |
| `data_scope.yaml` permissions | SeekDB GRANT/REVOKE | Database-enforced isolation |
| `SkillLoader` dynamic loading | Load from SeekDB in system_prompt | No filesystem dependency |
| `ToolRegistry` + 14 tools | `@agent.tool` decorator | Type-annotated, auto-validated |
| `_process_event_with_llm()` ReAct | `agent.run()` | Built-in ReAct loop |
| `ContextManager` sliding window | `message_history` parameter | Explicit control in SeekDB |
| `MemoryTools.retrieve_memory` | `@agent.tool` + SeekDB vector search | Tool queries SeekDB |
| `ActionTools.send_message` | `@agent.tool` + ZeroMQ publish | Event-driven multi-agent |
| Agent state (ACTIVE/WAITING_REPLY) | Not needed (stateless workers) | Each event is independent |
| `TapeWriter` JSONL append | SeekDB INSERT | Direct database write |

## 5. Event-Driven Multi-Agent Communication

### 5.1 No Blocking Waits

Multi-agent collaboration happens via events, not blocking RPC:

```
# Agent A (minister_revenue) needs to orchestrate with Agent B (governor_jiangnan)

Step 1: Worker receives event for minister_revenue
        → Builds agent with minister_revenue soul
        → Agent calls send_message tool targeting governor_jiangnan
        → Tool publishes event to ZeroMQ (role=governor_jiangnan)
        → Worker saves to SeekDB, responds to player

Step 2: Worker (same or different) picks up new event
        → Builds agent with governor_jiangnan soul
        → Processes message, takes action
        → Governor sends reply via send_message tool
        → Tool publishes event (role=minister_revenue)

Step 3: Worker picks up reply event
        → Builds agent with minister_revenue soul again
        → Processes reply, continues workflow
        → Responds to player

NO BLOCKING WAITS - all communication via events
NO DEADLOCKS - each event is independently processed
```

### 5.2 Event Flow Example

```python
# Event 1: Player asks minister about taxes
{
    "event_id": "evt_001",
    "event_type": "CHAT",
    "role": "minister_revenue",
    "payload": {"message": "今年税收如何？"}
}

# Event 2: Minister asks governor (via send_message tool)
{
    "event_id": "evt_002",
    "event_type": "AGENT_MESSAGE",
    "role": "governor_jiangnan",
    "payload": {
        "message": "请上报江南税收情况",
        "from": "minister_revenue",
        "session_id": "session_001"
    },
    "parent_event_id": "evt_001"
}

# Event 3: Governor replies
{
    "event_id": "evt_003",
    "event_type": "AGENT_MESSAGE",
    "role": "minister_revenue",
    "payload": {
        "message": "江南税收已收缴八成...",
        "from": "governor_jiangnan"
    },
    "parent_event_id": "evt_002"
}
```

### 5.3 Stateless Workers Enable Parallelism

```
Timeline with 3 workers:

T0: Worker1 processes evt_001 (minister)
T1: Worker2 processes evt_002 (governor)  [parallel]
T2: Worker3 processes evt_003 (minister reply)  [parallel]
T3: All workers available for next events

No state synchronization needed between workers.
Each event is self-contained with role_id in event.
```

## 6. SeekDB Server Deployment

### 6.1 Docker Compose Configuration

```yaml
# docker-compose.yml
version: '3.8'

services:
  seekdb:
    image: oceanbase/seekdb:latest
    container_name: simu-emperor-seekdb
    ports:
      - "2881:2881"
    environment:
      - SEEKDB_MODE=server
      - SEEKDB_PASSWORD=seekdb123
      - SEEKDB_DATABASE=simu_emperor
    volumes:
      - seekdb-data:/var/lib/oceanbase
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  seekdb-data:
```

### 6.2 Connection Configuration

```python
# src/simu_emperor/common/config.py
from pydantic import BaseSettings

class Settings(BaseSettings):
    seekdb_host: str = "localhost"
    seekdb_port: int = 2881
    seekdb_user: str = "root"
    seekdb_password: str = "seekdb123"
    seekdb_database: str = "simu_emperor"

    @property
    def seekdb_dsn(self) -> str:
        return f"mysql+aiomysql://{self.seekdb_user}:{self.seekdb_password}@{self.seekdb_host}:{self.seekdb_port}/{self.seekdb_database}"
```

## 7. SeekDB Schema

### 7.1 Agent Configuration Tables

```sql
-- Agent roles (soul definitions)
CREATE TABLE agent_roles (
    agent_id  VARCHAR(64) PRIMARY KEY,
    role_name VARCHAR(64) NOT NULL,
    soul_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FULLTEXT INDEX idx_soul_ft (soul_text)
);

-- Agent skills
CREATE TABLE agent_skills (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    agent_id   VARCHAR(64) NOT NULL,
    skill_name VARCHAR(64) NOT NULL,
    skill_text TEXT NOT NULL,
    event_type VARCHAR(32),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_agent (agent_id),
    FULLTEXT INDEX idx_skill_ft (skill_text),
    UNIQUE KEY uk_agent_skill (agent_id, skill_name)
);
```

### 7.2 Permission System (GRANT/REVOKE)

```sql
-- Agent users (for GRANT/REVOKE)
-- Each agent gets a dedicated database user with restricted permissions

-- Permission mapping table
CREATE TABLE agent_permissions (
    id        BIGINT AUTO_INCREMENT PRIMARY KEY,
    agent_id  VARCHAR(64) NOT NULL,
    table_name VARCHAR(64) NOT NULL,
    column_list VARCHAR(256) DEFAULT '*',  -- '*' or 'col1,col2'
    permission ENUM('SELECT', 'INSERT', 'UPDATE', 'DELETE') NOT NULL,
    row_filter TEXT,  -- Optional: WHERE clause for row-level
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_agent_table (agent_id, table_name),
    UNIQUE KEY uk_permission (agent_id, table_name, permission)
);

-- Example: Governor can only see their province data
INSERT INTO agent_permissions VALUES
(1, 'governor_jiangnan', 'province_data', '*', 'SELECT', 'province_id = "jiangnan"');

-- Create database user per agent and apply GRANTs
-- (done at agent registration time via PermissionStore)
```

### 7.3 Tape Storage Tables

```sql
-- Main event table
CREATE TABLE tape_events (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_id        VARCHAR(64) NOT NULL,
    session_id      VARCHAR(128) NOT NULL,
    agent_id        VARCHAR(64) NOT NULL,
    root_event_id   VARCHAR(64),
    parent_event_id VARCHAR(64),
    event_type      VARCHAR(32) NOT NULL,
    src             VARCHAR(64) NOT NULL,
    dst             TEXT,
    role            VARCHAR(64),  -- Target agent role
    payload         JSON,
    tick            INT,
    tokens_in       INT DEFAULT 0,
    tokens_out      INT DEFAULT 0,
    latency_ms      INT DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_session_time (session_id, created_at),
    INDEX idx_agent_time (agent_id, created_at),
    INDEX idx_event_type (event_type),
    INDEX idx_root_event (root_event_id),
    INDEX idx_tick (tick),
    INDEX idx_role (role),
    FULLTEXT INDEX idx_payload_ft (payload)
);

-- Session metadata
CREATE TABLE tape_sessions (
    session_id        VARCHAR(128) PRIMARY KEY,
    agent_id          VARCHAR(64) NOT NULL,
    parent_session_id VARCHAR(128),
    title             VARCHAR(128),
    summary           TEXT,
    status            ENUM('active', 'finished', 'failed'),
    event_count       INT DEFAULT 0,
    window_offset     INT DEFAULT 0,
    created_tick      INT,
    last_updated_tick INT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_agent_status (agent_id, status),
    FULLTEXT INDEX idx_title_summary (title, summary)
);

-- Segment embeddings for vector search
CREATE TABLE tape_segments (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id    VARCHAR(128) NOT NULL,
    agent_id      VARCHAR(64) NOT NULL,
    start_pos     INT NOT NULL,
    end_pos       INT NOT NULL,
    summary       TEXT,
    tick_start    INT,
    tick_end      INT,
    embedding     VECTOR(384),  -- Sentence transformer dimension

    INDEX idx_session (session_id),
    INDEX idx_tick_range (tick_start, tick_end),
    VECTOR INDEX idx_embedding (embedding)
);

-- Conversation history (for PydanticAI message_history)
CREATE TABLE conversation_messages (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id   VARCHAR(128) NOT NULL,
    role         ENUM('user', 'assistant', 'system', 'tool') NOT NULL,
    content      TEXT NOT NULL,
    tool_name    VARCHAR(64),
    tool_args    JSON,
    tool_result  TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_session (session_id),
    INDEX idx_session_time (session_id, created_at)
);
```

### 7.4 Query Pattern Mapping

| V4 Implementation | V5 (SeekDB) |
|-------------------|-------------|
| `TapeWriter.write_event()` → JSONL append | `INSERT INTO tape_events` |
| `tape_meta.jsonl` full-file rewrite | `UPDATE tape_sessions SET ... WHERE session_id = ?` |
| `SegmentSearcher` reads JSONL + chunks | `SELECT ... WHERE id BETWEEN ? AND ?` |
| `TapeMetadataIndex` keyword matching | `FULLTEXT SEARCH ON tape_sessions(title, summary)` |
| ChromaDB vector search | `VECTOR SEARCH ON tape_segments(embedding)` |
| `ContextManager` sliding window | `SELECT ... WHERE session_id=? AND id > {window_offset}` |
| Cross-session search | Hybrid: FULLTEXT + VECTOR on `tape_segments` |

## 8. Permission Store (GRANT/REVOKE)

### 8.1 PermissionStore Class

```python
# src/simu_emperor/storage/seekdb/permission_store.py
from typing import Optional

class PermissionStore:
    """Manages agent permissions via SeekDB GRANT/REVOKE."""

    def __init__(self, db_pool: aiomysql.Pool):
        self._pool = db_pool

    async def grant_table_access(
        self,
        agent_id: str,
        table_name: str,
        permission: str,  # SELECT, INSERT, UPDATE, DELETE
        columns: list[str] | None = None,
        row_filter: str | None = None,
    ) -> None:
        """Grant table-level access to an agent."""
        column_list = ",".join(columns) if columns else "*"

        # Store permission metadata
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO agent_permissions
                (agent_id, table_name, column_list, permission, row_filter)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE row_filter = VALUES(row_filter)
            """, (agent_id, table_name, column_list, permission, row_filter))

            # Apply actual GRANT (if agent user exists)
            if columns:
                grant_sql = f"GRANT {permission}({column_list}) ON {table_name} TO '{agent_id}'@'%'"
            else:
                grant_sql = f"GRANT {permission} ON {table_name} TO '{agent_id}'@'%'"

            await conn.execute(grant_sql)

    async def check_permission(
        self,
        agent_id: str,
        table_name: str,
        permission: str,
    ) -> bool:
        """Check if agent has specific permission."""
        async with self._pool.acquire() as conn:
            result = await conn.execute("""
                SELECT 1 FROM agent_permissions
                WHERE agent_id = %s
                  AND table_name = %s
                  AND permission = %s
                LIMIT 1
            """, (agent_id, table_name, permission))
            return result.fetchone() is not None

    async def get_permissions(self, agent_id: str) -> list[str]:
        """Get all permissions for an agent as list of strings."""
        async with self._pool.acquire() as conn:
            result = await conn.execute("""
                SELECT table_name, permission, column_list
                FROM agent_permissions
                WHERE agent_id = %s
            """, (agent_id,))

            permissions = []
            for row in result.fetchall():
                table, perm, cols = row
                permissions.append(f"{perm}:{table}:{cols}")

            return permissions
```

### 8.2 Integration with AgentContext

```python
# src/simu_emperor/workers/agent_context.py
class AgentContext(BaseModel):
    agent_id: str
    session_id: str
    permissions: list[str]  # Loaded at event processing time
    mq_publisher: MQPublisher
    game_state_reader: GameStateReader
    seekdb_client: SeekDBClient

    def has_permission(self, tool_name: str, resource: str = "*") -> bool:
        """Check if agent has permission for tool+resource combination."""
        # Permissions are pre-loaded from SeekDB
        required = f"{tool_name}:{resource}"
        wildcard = f"{tool_name}:*"

        return required in self.permissions or wildcard in self.permissions
```

## 9. ZeroMQ Implementation

### 9.1 Router (Gateway)

```python
# src/simu_emperor/mq/router.py
import zmq.asyncio

class MQRouter:
    """ROUTER socket for Gateway - fair-queues events to workers."""

    def __init__(self):
        self._ctx = zmq.asyncio.Context()
        self._socket = self._ctx.socket(zmq.ROUTER)
        self._socket.bind("ipc://@simu_router")

    async def send_to_worker(self, event_bytes: bytes) -> None:
        """Send event to next available worker (fair queue)."""
        # ROUTER automatically selects next worker via fair queue
        await self._socket.send(event_bytes)

    async def receive_from_worker(self) -> bytes:
        """Receive response from worker."""
        return await self._socket.recv()

    async def close(self):
        self._socket.close()
        self._ctx.term()
```

### 9.2 Dealer (Worker)

```python
# src/simu_emperor/mq/dealer.py
import zmq.asyncio

class MQDealer:
    """DEALER socket for Workers - receives fair-queued events."""

    def __init__(self, worker_id: str):
        self._worker_id = worker_id
        self._ctx = zmq.asyncio.Context()
        self._socket = self._ctx.socket(zmq.DEALER)
        self._socket.setsockopt(zmq.IDENTITY, worker_id.encode())
        self._socket.connect("ipc://@simu_router")

    async def receive_event(self) -> bytes:
        """Receive event from Gateway (blocking)."""
        return await self._socket.recv()

    async def send_response(self, response_bytes: bytes) -> None:
        """Send response back to Gateway."""
        await self._socket.send(response_bytes)

    async def close(self):
        self._socket.close()
        self._ctx.term()
```

### 9.3 PubSub (Engine/Workers)

```python
# src/simu_emperor/mq/pubsub.py
import zmq.asyncio

class MQPublisher:
    """PUB socket for Engine - broadcasts tick and state events."""

    def __init__(self):
        self._ctx = zmq.asyncio.Context()
        self._socket = self._ctx.socket(zmq.PUB)
        self._socket.bind("ipc://@simu_broadcast")

    async def publish(self, topic: str, event_bytes: bytes) -> None:
        """Publish event with topic prefix."""
        await self._socket.send_multipart([topic.encode(), event_bytes])

    async def close(self):
        self._socket.close()
        self._ctx.term()


class MQSubscriber:
    """SUB socket for Workers - receives broadcast events."""

    def __init__(self, topics: list[str]):
        self._ctx = zmq.asyncio.Context()
        self._socket = self._ctx.socket(zmq.SUB)
        self._socket.connect("ipc://@simu_broadcast")

        for topic in topics:
            self._socket.setsockopt(zmq.SUBSCRIBE, topic.encode())

    async def receive(self) -> tuple[str, bytes]:
        """Receive (topic, event_bytes) tuple."""
        topic, event_bytes = await self._socket.recv_multipart()
        return topic.decode(), event_bytes

    async def close(self):
        self._socket.close()
        self._ctx.term()
```

### 9.4 Protocol (Serialization)

```python
# src/simu_emperor/mq/protocol.py
import msgpack
from dataclasses import dataclass
from typing import Any

@dataclass
class Event:
    event_id: str
    event_type: str
    src: str
    dst: list[str]
    session_id: str
    role: str | None
    payload: dict[str, Any]
    timestamp: str
    parent_event_id: str | None = None
    root_event_id: str | None = None

    def serialize(self) -> bytes:
        return msgpack.packb({
            "event_id": self.event_id,
            "event_type": self.event_type,
            "src": self.src,
            "dst": self.dst,
            "session_id": self.session_id,
            "role": self.role,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "parent_event_id": self.parent_event_id,
            "root_event_id": self.root_event_id,
        })

    @classmethod
    def deserialize(cls, data: bytes) -> "Event":
        obj = msgpack.unpackb(data, raw=False)
        return cls(**obj)
```

## 10. Worker Process Implementation

### 10.1 Worker Main Loop

```python
# src/simu_emperor/workers/worker.py
import asyncio
from mq.dealer import MQDealer
from mq.subscriber import MQSubscriber
from storage.seekdb.client import SeekDBClient
from agents.agent_builder import AgentBuilder

class AgentWorker:
    """Stateless worker that processes events for any agent."""

    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.dealer = MQDealer(worker_id)
        self.subscriber = MQSubscriber(["tick.", "system."])
        self.seekdb = SeekDBClient()
        self.agent_builder = AgentBuilder(self.seekdb)

    async def run(self):
        """Main worker loop."""
        await asyncio.gather(
            self._process_events(),
            self._process_broadcasts(),
        )

    async def _process_events(self):
        """Process events from Gateway via DEALER socket."""
        while True:
            event_bytes = await self.dealer.receive_event()
            event = Event.deserialize(event_bytes)

            try:
                result = await self._handle_event(event)
                response = {"status": "ok", "output": result}
            except Exception as e:
                response = {"status": "error", "error": str(e)}

            await self.dealer.send_response(msgpack.packb(response))

    async def _handle_event(self, event: Event) -> str:
        """Build agent on-demand and process event."""
        # Get role from event (determines which agent to build)
        role_id = event.role or self._extract_role(event)
        if not role_id:
            raise ValueError(f"No role specified in event {event.event_id}")

        # Load permissions from SeekDB
        permissions = await self.seekdb.get_permissions(role_id)

        # Build context
        context = AgentContext(
            agent_id=role_id,
            session_id=event.session_id,
            permissions=permissions,
            mq_publisher=self._mq_publisher,
            game_state_reader=self._game_state_reader,
            seekdb_client=self.seekdb,
        )

        # Build agent on-demand (stateless)
        agent_instance = await self.agent_builder.build(role_id)

        # Run agent
        result = await agent_instance.run(event, context)

        # Save to tape
        await self.seekdb.save_event(event, result)

        return result

    async def _process_broadcasts(self):
        """Process broadcast events (tick, system) via SUB socket."""
        while True:
            topic, event_bytes = await self.subscriber.receive()
            event = Event.deserialize(event_bytes)

            if topic.startswith("tick."):
                await self._handle_tick(event)
            elif topic.startswith("system."):
                await self._handle_system(event)
```

### 10.2 Agent Builder

```python
# src/simu_emperor/workers/agent_builder.py
from pydantic_ai import Agent
from storage.seekdb.client import SeekDBClient

class AgentBuilder:
    """Builds PydanticAI agents on-demand from SeekDB config."""

    def __init__(self, seekdb: SeekDBClient):
        self.seekdb = seekdb

    async def build(self, role_id: str) -> Agent:
        """Build a PydanticAI agent for the given role."""
        # Load soul from SeekDB
        soul = await self.seekdb.load_soul(role_id)

        # Create agent with dynamic system prompt
        agent = Agent(
            'openai:gpt-4o',
            deps_type=AgentContext,
            output_type=str,
        )

        # Register system prompt
        @agent.system_prompt
        async def system_prompt(ctx) -> str:
            skills = await self.seekdb.load_skills(role_id)
            return f"{soul}\n\n# Skills\n{skills}"

        # Register tools
        self._register_tools(agent)

        return agent

    def _register_tools(self, agent: Agent):
        """Register all 14 tools."""
        # Query tools
        agent.tool(query_province_data)
        agent.tool(query_treasury_data)
        agent.tool(query_army_data)

        # Action tools
        agent.tool(adjust_tax_rate)
        agent.tool(allocate_funds)
        agent.tool(send_message)

        # Memory tools
        agent.tool(recall_memory)
        agent.tool(summarize_session)

        # Session tools
        agent.tool(create_sub_session)
        agent.tool(list_sessions)
        # ... etc
```

## 11. Directory Structure

```
src/simu_emperor/
├── __init__.py
├── main.py                    # Entry point
│
├── gateway/                   # API Gateway process
│   ├── app.py                 # FastAPI
│   ├── websocket.py           # WebSocket
│   └── message_converter.py
│
├── engine/                    # Engine process
│   ├── engine.py              # Game state
│   ├── tick_coordinator.py    # Tick loop
│   └── models/
│
├── workers/                  # Agent Worker process
│   ├── worker.py              # Main loop
│   ├── agent_builder.py       # Build PydanticAI agents
│   └── agent_context.py       # AgentContext + tools
│
├── agents/                   # Agent definition layer
│   ├── tools/
│   │   ├── query_tools.py
│   │   ├── action_tools.py
│   │   ├── memory_tools.py
│   │   └── session_tools.py
│   └── instructions.py        # Dynamic prompts
│
├── mq/                        # ZeroMQ layer
│   ├── router.py              # ROUTER socket management
│   ├── dealer.py              # DEALER socket for workers
│   ├── pubsub.py              # PUB/SUB for broadcasts
│   └── protocol.py            # Message serialization
│
├── storage/                  # Storage layer
│   ├── seekdb/
│   │   ├── client.py          # SeekDB connection pool
│   │   ├── tape_store.py      # Tape CRUD + vector + fulltext
│   │   ├── session_store.py   # Session metadata
│   │   ├── permission_store.py # GRANT/REVOKE management
│   │   └── schema.sql          # Table definitions + grants
│   └── sqlite/
│       ├── database.py        # Game state
│       └── repositories.py    # Data access
│
├── monitoring/
│   ├── metrics.py             # Prometheus metrics
│   └── health.py              # Health checks
│
├── common/
│   ├── config.py
│   ├── models.py
│   └── logging.py
│
└── session/
    └── manager.py             # Session lifecycle
```

## 12. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Process model | 3 processes (no Orchestrator) | Workers are stateless, no coordination needed |
| MQ | ZeroMQ IPC (no broker) | Simpler deployment, no Redis needed |
| Agent framework | PydanticAI | Multi-provider, Python-native, full history control |
| Workers | Stateless, build on-demand | Any worker can handle any agent event |
| Permissions | SeekDB GRANT/REVOKE | Database-enforced, auditable, runtime-updatable |
| Tape storage | SeekDB Server (Docker) | Unified vector + fulltext + structured queries |
| Config cache | None (load from SeekDB) | No Redis, workers load fresh per event |
| Multi-agent | Event-driven via ZeroMQ | No blocking waits, no deadlocks |

## 13. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| PydanticAI version stability | Medium | Medium | Pin version, abstraction layer |
| SeekDB Python ecosystem maturity | Medium | High | PoC validation first |
| ZeroMQ learning curve | Low | Medium | Well-documented, simple patterns |
| No config caching performance | Low | Low | SeekDB is fast for small queries |
| Multi-agent event loops | Medium | Medium | Clear session_id tracking, timeout guards |

## 14. Success Criteria

- [ ] All 14 tools functional as `@agent.tool` with GRANT-based permissions — verified by integration test suite covering each tool with allow/deny scenarios
- [ ] Events routed via ZeroMQ ROUTER/DEALER with fair-queue load balancing — verified by multi-worker test showing even distribution
- [ ] Workers are stateless — any worker can process any agent's event — verified by stopping workers randomly and observing continued processing
- [ ] Tape events written to and queried from SeekDB (fulltext + vector) — verified by write-then-query round-trip test
- [ ] Multi-agent collaboration works via event-driven send_message — verified by end-to-end test with 3 agents coordinating
- [ ] LLM call latency, token usage, and tool frequency metrics exposed via Prometheus — verified by scraping `/metrics` endpoint
- [ ] SeekDB Server runs via Docker Compose with health checks — verified by `docker-compose ps` showing healthy status
- [ ] No Redis in architecture — verified by codebase grep confirming zero Redis imports/usage
- [ ] PydanticAI agents build on-demand from SeekDB config — verified by log analysis showing fresh builds per event

## 15. Recommended Implementation Sequence

```
Phase 1 (Validation — parallel):
  ├── Step 1: PoC — SeekDB Docker Server + SQL + Vector + Fulltext + GRANT
  └── Step 2: PoC — PydanticAI Agent with tools + message_history

Phase 2 (Core — parallel):
  ├── Step 3: ZeroMQ Layer — ROUTER/DEALER + PUB/SUB + message protocol
  ├── Step 4: SeekDB Storage — Schema, tape_store, session_store, permission_store
  └── Step 5: Permission Store — GRANT/REVOKE + PermissionStore class

Phase 3 (Agent — sequential):
  Step 6: Worker Process — Main loop + agent_builder + PydanticAI integration
  Step 7: Tool Migration — Port 14 tools to @agent.tool with GRANT checks

Phase 4 (Integration — parallel):
  ├── Step 8: Engine Process — Tick loop via ZeroMQ PUB, game state
  ├── Step 9: API Gateway — FastAPI + WebSocket + ROUTER bridge
  └── Step 10: Multi-Agent Events — Event-driven collaboration via ZeroMQ

Phase 5 (Hardening — sequential):
  Step 11: Monitoring — Prometheus metrics + health checks
  Step 12: E2E Testing — Full game flow validation
```

### Phase 1 Details

**Step 1: SeekDB PoC**
- Start SeekDB Server via Docker Compose
- Create tables with VECTOR and FULLTEXT indexes
- Test vector search (embedding → similarity)
- Test fulltext search (keyword → match)
- Test GRANT/REVOKE for table-level permissions

**Step 2: PydanticAI PoC**
- Create Agent with deps_type=AgentContext
- Implement @agent.system_prompt with dynamic load
- Implement @agent.tool with permission check
- Test agent.run() with message_history from SeekDB
- Verify new_messages() saved correctly

### Phase 2 Details

**Step 3: ZeroMQ Layer**
- Implement MQRouter (Gateway binds ROUTER)
- Implement MQDealer (Worker connects DEALER)
- Implement MQPublisher/MQSubscriber (PUB/SUB)
- Define Event dataclass with msgpack serialization
- Test fair-queue distribution with 3 workers

**Step 4: SeekDB Storage**
- Create schema.sql with all tables
- Implement tape_store.py (CRUD + vector + fulltext)
- Implement session_store.py (metadata CRUD)
- Test sliding window query for message_history

**Step 5: Permission Store**
- Implement permission_store.py
- Create GRANT automation for agent users
- Test permission check in tool calls

### Phase 3 Details

**Step 6: Worker Process**
- Implement worker.py main loop
- Implement agent_builder.py (build from SeekDB)
- Test event processing with mock LLM

**Step 7: Tool Migration**
- Port query_province_data
- Port query_treasury_data
- Port query_army_data
- Port adjust_tax_rate
- Port allocate_funds
- Port send_message (event-driven)
- Port recall_memory (SeekDB vector)
- Port summarize_session
- Port create_sub_session
- Port list_sessions
- ... (14 tools total)

### Phase 4 Details

**Step 8: Engine Process**
- Implement tick_coordinator.py (tick loop)
- Publish tick events via ZeroMQ PUB
- Maintain SQLite game state

**Step 9: API Gateway**
- Implement FastAPI endpoints
- Implement WebSocket handler
- Bridge HTTP/WS → ZeroMQ ROUTER

**Step 10: Multi-Agent Events**
- Implement send_message tool (publish to ZeroMQ)
- Test multi-agent coordination flow
- Verify no deadlocks with 5+ agents

### Phase 5 Details

**Step 11: Monitoring**
- Add Prometheus metrics to worker
- Add health check endpoints
- Add LLM latency tracking

**Step 12: E2E Testing**
- Full game flow: player → agent → multi-agent → response
- Load test with 10 concurrent players
- Verify tape persistence across worker restarts
