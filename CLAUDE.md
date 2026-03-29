# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/                    # All tests
uv run pytest tests/unit/               # Unit tests only
uv run pytest tests/unit/event_bus/     # Single test directory
uv run pytest tests/unit/event_bus/test_core.py  # Single file
uv run pytest tests/unit/event_bus/test_core.py::test_name -v  # Single test

# Lint and format
uv run ruff check .
uv run ruff format .

# Run CLI game
uv run simu-emperor
```

## Architecture

**V4.2: Tick-Based Real-Time Multi-Agent Architecture**

Tick-based emperor simulation game. The player is the emperor; AI agents play officials who may lie in reports and slack off when executing commands. All communication happens through an event bus — no direct function calls between modules. The game advances automatically via periodic ticks (1 tick = 1 week).

### Core Principles

| Principle | Description |
|-----------|-------------|
| **Event-Driven** | All interactions via EventBus (src/dst routing) |
| **Fully Async** | asyncio-based, fire-and-forget by default |
| **Tick-Based Timing** | Automatic tick progression (configurable interval, default 5s) |
| **Shared Data Reads** | Modules read directly from persistence (per permissions) |
| **Unified Writes** | Only Engine can modify game state |
| **Passive Agents** | Agents only respond to events, never initiate |

### Directory Structure

```
src/simu_emperor/
├── __init__.py
├── main.py                           # CLI entry point
├── config.py                         # pydantic-settings global config
│
├── event_bus/                        # Module: Event routing infrastructure
│   ├── core.py                       # EventBus implementation
│   ├── event.py                      # Event dataclass (src/dst/type/payload)
│   ├── event_types.py                # EventType constants (includes TICK_COMPLETED)
│   └── logger.py                     # EventLogger (JSONL format)
│
├── engine/                           # Module: Game engine (V4 refactored)
│   ├── models/                       # Pydantic data models (simplified)
│   │   ├── base_data.py              # ProvinceData (4 fields), NationData
│   │   └── incident.py               # Incident, Effect (time-limited game events)
│   ├── engine.py                     # Core Engine class (apply_tick, Incident management)
│   └── tick_coordinator.py           # Tick timer coordinator (async loop)
│
├── agents/                           # Module: AI officials
│   ├── agent.py                      # Agent base class (V4.2: event queue with backpressure)
│   ├── manager.py                    # Agent lifecycle (init/add/remove)
│   ├── agent_generator.py            # NEW V4.2: Agent creation/factory
│   ├── memory_initializer.py         # NEW V4.2: ContextManager + TapeRepository setup
│   ├── system_prompts.py             # NEW V4.2: System prompt assembly
│   ├── response_parser.py            # Parse LLM structured output
│   ├── skills/                       # Sub-module: File-driven skill system
│   │   ├── models.py                 # Skill data models (SkillMetadata, Skill)
│   │   ├── parser.py                 # YAML Frontmatter + Markdown parser
│   │   ├── validator.py              # Skill validation logic
│   │   ├── loader.py                 # Three-tier caching loader
│   │   ├── registry.py               # Event-to-skill mapping registry
│   │   ├── watcher.py                # File watcher for hot-reload (TODO)
│   │   ├── config.py                 # Skill configuration
│   │   └── exceptions.py             # Skill exception classes
│   └── tools/                        # Sub-module: Tool handlers for function calling
│       ├── tool_registry.py          # NEW V4.2: Tool/ToolRegistry classes
│       ├── query_tools.py            # Query handlers (return data to LLM)
│       ├── action_tools.py           # Action handlers (send_message, write_memory, etc.)
│       ├── memory_tools.py           # Memory handlers (retrieve_memory, summarize_segment)
│       ├── task_session_tools.py     # NEW V4.2: Task session management
│       └── role_map_parser.py        # Parse role_map.md for agent info
│
├── memory/                           # Module: V4.2 Memory System
│   ├── models.py                     # Memory data models
│   │   ├── StructuredQuery           # Parsed query (intent, entities, scope, depth)
│   │   ├── ParseResult               # Query parsing result
│   │   ├── RetrievalResult           # Memory retrieval result
│   │   ├── TapeMetadataEntry         # Session metadata entry
│   │   └── TapeSegment               # Event segment for retrieval
│   ├── exceptions.py                 # Memory exceptions (ParseError, RetrievalError)
│   ├── config.py                     # MemoryConfig, SearchWeights
│   ├── tape_writer.py                # V4.2 DUAL-WRITE: JSONL + tape_events SQLite
│   ├── tape_metadata.py              # TapeMetadataManager (generates titles via LLM)
│   ├── context_manager.py            # V4.2 DB-first reads via tape_repository
│   ├── vector_searcher.py            # ChromaDB semantic search
│   ├── vector_store.py               # NEW V4.2: VectorSearcher wrapper with retry
│   ├── two_level_searcher.py         # L1 metadata + L1.5 vector + L2 segment search
│   ├── tape_metadata_index.py        # Level 1 keyword search
│   ├── segment_searcher.py           # Level 2 event segment search
│   ├── structured_retriever.py       # Retrieval coordinator
│   └── query_parser.py               # NL → StructuredQuery
│
├── application/                      # Application Layer (V4.1+)
│   ├── services.py                   # ApplicationServices container (DI, creates TapeRepository)
│   ├── game_service.py               # GameService - game lifecycle
│   ├── session_service.py            # SessionService - session management
│   ├── agent_service.py              # AgentService (V4.2: accepts tape_repository)
│   ├── group_chat_service.py         # GroupChatService - group chat
│   ├── message_service.py            # MessageService - message routing
│   ├── tape_service.py               # TapeService - tape queries
│   └── task_tracker.py               # NEW V4.2: Task tracking
│
├── persistence/                      # Module: Data persistence
│   ├── database.py                   # Module-level SQLite singleton (aiosqlite)
│   ├── tape_repository.py            # NEW V4.2: Own connection, tape_events + failed_embeddings
│   ├── repositories.py               # Repository pattern CRUD (Game, Agent, Incident)
│   └── serialization.py              # GameState ↔ DB conversion
│
├── llm/                              # Module: LLM providers
│   ├── base.py                       # LLMProvider interface
│   ├── anthropic.py                  # Anthropic Claude implementation
│   ├── openai.py                     # OpenAI GPT implementation
│   └── mock.py                       # Mock provider (testing)
│
├── adapters/web/                     # Module: Web adapter
│   ├── server.py                     # FastAPI server
│   ├── game_instance.py              # Game instance management
│   ├── connection_manager.py         # WebSocket connection manager
│   └── message_converter.py          # Message format conversion
│
├── session/                          # Module: Session management
│   ├── models.py                     # Session data models
│   ├── manager.py                    # Session manager
│   ├── group_chat.py                 # Group chat logic
│   ├── task_monitor.py               # Task monitoring
│   └── constants.py                  # Session constants
│
└── common/                           # Module: Common utilities
    └── ...

data/
├── skills/                           # Universal skill templates (v2.0 format)
│   ├── chat.md                       # Chat with emperor (role-play)
│   ├── create_incident.md            # Create time-limited game events
│   ├── on_tick_completed.md          # Handle tick completed events
│   ├── query_data.md                 # Query data within permissions
│   ├── receive_message.md            # Receive inter-agent messages
│   └── write_report.md               # Write reports to emperor
│
├── initial_state_v4.json             # V4 initial game state configuration
│
├── default_agents/                   # Agent templates (version-controlled)
│   └── {agent_id}/
│       ├── soul.md                   # Role definition (personality, behavior)
│       └── data_scope.yaml           # Data access permissions (per-skill whitelist)
│
├── agent/                            # Active agent workspace (runtime)
│   └── {agent_id}/
│       ├── soul.md                   # Copied from template (mutable during game)
│       ├── data_scope.yaml           # Copied from template
│       ├── memory/                   # V2 Memory: agent-maintained summaries
│       │   ├── MEMORY.md             # Long-term memory (write_long_term_memory tool)
│       │   ├── summary.md            # Legacy long-term memory
│       │   └── recent/               # Short-term memory (last 3 turns)
│       │       ├── turn_005.md
│       │       ├── turn_006.md
│       │       └── turn_007.md
│       └── workspace/                # Player-visible documents
│           ├── 005_report.md
│           ├── 006_exec_adjust_tax.md
│           └── 007_report.md
│
├── memory/                           # V4.2 Memory System: Dual-write storage
│   ├── tape_meta.jsonl               # Session metadata (title, event_count, etc.)
│   └── agents/                       # Per-agent session storage
│       └── {agent_id}/
│           └── sessions/
│               └── {session_id}/
│                   └── tape.jsonl    # Event log (JSONL format, also in SQLite)
│
├── logs/                             # Log directory
│   ├── events/                       # JSONL event logs
│   │   ├── events_20260226.jsonl
│   │   └── events_20260227.jsonl
│   ├── agents/                       # Agent-specific logs
│   │   ├── {agent_id}.log            # Agent activity logs
│   │   └── {agent_id}_llm.jsonl      # LLM call audit logs
│   ├── errors/                       # Error logs
│   └── debug/                        # Debug logs
│
└── saves/                            # Save games
    └── game-001/
        ├── turn_005/
        └── turn_010/

tests/
├── conftest.py                       # Shared fixtures + factories
├── fixtures/                         # Test fixtures and data
│   └── skills/                       # Skill file test fixtures
├── unit/                             # Unit tests (no I/O, no LLM)
│   ├── test_event_bus/
│   ├── test_core/
│   ├── test_agents/
│   │   ├── test_skills/              # Skill module tests
│   │   ├── test_agent.py             # Agent lifecycle tests
│   │   └── test_manager.py
│   ├── test_memory/                  # V4.2 Memory module tests
│   │   ├── test_models.py            # Data model tests
│   │   ├── test_tape_writer.py       # Dual-write tests
│   │   ├── test_tape_metadata.py     # Metadata management tests
│   │   ├── test_context_manager.py   # DB-first read tests
│   │   ├── test_query_parser.py      # Query parsing tests (mock LLM)
│   │   ├── test_vector_store.py      # VectorStore with retry tests
│   │   ├── test_two_level_searcher.py # Two-level search tests
│   │   └── test_structured_retriever.py  # Retrieval coordinator tests
│   ├── test_cli/
│   ├── test_persistence/
│   │   └── test_tape_repository.py   # TapeRepository CRUD tests
│   ├── test_llm/
│   └── test_application/             # Application Layer tests
│       ├── test_services.py          # ApplicationServices container
│       ├── test_game_service.py      # GameService tests
│       ├── test_session_service.py   # SessionService tests
│       ├── test_agent_service.py     # AgentService tests
│       ├── test_group_chat_service.py # GroupChatService tests
│       ├── test_message_service.py   # MessageService tests
│       └── test_tape_service.py      # TapeService tests
├── integration/                      # Integration tests (multi-module)
│   └── test_memory/                  # Memory integration tests
│       └── test_memory_integration.py  # End-to-end memory workflows
└── e2e/                              # End-to-end tests (full game flow)
```

### Module Dependencies (V4.2 - Clean Architecture)

```
┌─────────────────────────────────────────────────────────────┐
│                     Adapter Layer                           │
│                     ┌──────────────┐                         │
│                     │     Web      │                         │
│                     │   Adapter    │                         │
│                     └──────┬───────┘                         │
│                            │                                 │
└────────────────────────────┼─────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   Application Layer (V4.2)                   │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │
│  │ GameService   │  │ SessionService│  │ AgentService  │   │
│  └───────────────┘  └───────────────┘  └───────┬───────┘   │
│  ┌───────────────┐  ┌───────────────┐          │           │
│  │ GroupChatSvc  │  │ MessageService│          │           │
│  └───────────────┘  └───────────────┘          │           │
│                              ▲                 │           │
│                              │                 ▼           │
│                    ┌─────────────────────────────────┐     │
│                    │      TapeRepository (NEW)       │     │
│                    │   (own aiosqlite connection)    │     │
│                    └─────────────────────────────────┘     │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                       Core Layer                            │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌──────────────┐ │
│  │  Engine │  │ Agents  │  │ EventBus │  │ Repository   │ │
│  └─────────┘  └────┬────┘  └──────────┘  └──────────────┘ │
│                    │                                        │
│                    ▼                                        │
│           ┌─────────────────┐                              │
│           │ Memory System   │                              │
│           │ (TapeWriter,    │                              │
│           │ ContextManager) │                              │
│           └─────────────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

**Dependency Rules:**
- Adapter Layer ONLY depends on Application Layer (protocol conversion)
- Application Layer depends on Core Layer (business logic)
- Core Layer has NO dependencies on upper layers
- No circular dependencies
- TapeRepository is created in ApplicationServices and shared across layers

### Core Modules

**Application Layer** (`application/`) — Business logic services (NEW in V4.1)

The Application Layer separates business logic from protocol handling, following Clean Architecture principles.

- **GameService** (`game_service.py`) — Game lifecycle management
  - `initialize()` - Initialize engine and tick coordinator
  - `shutdown()` - Stop tick coordinator
  - `get_state()` - Get current game state
  - `get_overview()` - Get empire summary (treasury, population, etc.)

- **SessionService** (`session_service.py`) — Session management
  - `create_session()` - Create new session for agent
  - `select_session()` - Switch to existing session
  - `list_sessions()` - List all sessions
  - `get_session_for_agent()` - Get agent's current session

- **AgentService** (`agent_service.py`) — Agent lifecycle
  - `initialize_agents()` - Initialize and start agents
  - `get_available_agents()` - List active agents
  - `is_agent_available()` - Check if agent exists
  - `stop_all()` - Stop all agents

- **GroupChatService** (`group_chat_service.py`) — Multi-agent chat
  - `create_group_chat()` - Create group chat
  - `list_group_chats()` - List all groups
  - `send_to_group_chat()` - Broadcast to group members
  - `add_agent_to_group()` / `remove_agent_from_group()` - Manage members

- **MessageService** (`message_service.py`) — Message routing
  - `send_command()` - Send command to agent
  - `send_chat()` - Send chat to agent
  - `broadcast()` - Broadcast to multiple agents

- **TapeService** (`tape_service.py`) — Event tape queries
  - `get_current_tape()` - Get tape events
  - `get_tape_with_subs()` - Include sub-sessions
  - `get_sub_sessions()` - List task sessions

- **ApplicationServices** (`services.py`) — Dependency injection container
  - `create()` - Initialize all services in dependency order
  - `shutdown()` - Clean shutdown

**EventBus** (`event_bus/`) — Event routing infrastructure. Routes events by src/dst matching, supports broadcast via `"*"`, fully async via `asyncio.create_task()`. Events logged to JSONL format. No business logic.

**Engine** (`engine/engine.py`) — Game state manager (V4). Applies fixed growth rates and Effects, calculates tax/treasury, manages Incident lifecycle. Methods: `apply_tick()`, `add_incident()`, `remove_incident()`, `get_state()`, `get_active_incidents()`.

**TickCoordinator** (`engine/tick_coordinator.py`) — Timer coordinator (V4). Maintains tick timer, calls `Engine.apply_tick()` at configurable interval (default 5s), publishes `tick_completed` events via EventBus. Methods: `start()`, `stop()`, `_tick_loop()`.

**Agents** (`agents/`) — File-driven AI officials with V4.2 enhancements. Defined by markdown files, not Python classes. `soul.md` defines personality/behavior, `data_scope.yaml` defines data access (per-skill field whitelist).

**V4.2 Features:**
- **Event queue with backpressure**: asyncio.Queue with configurable max_size (default: 100)
- **ToolRegistry**: Tool system uses ToolRegistry class (not _function_handlers dict)
- **MemoryInitializer**: Creates ContextManager with tape_repository injection
- **Unified send_message**: ActionTools.send_message handles both agent-to-agent and respond-to-player

**Available Tools (V4.2):**
| Tool | Type | Description |
|------|------|-------------|
| `query_province` | Query | Query province data |
| `query_nation` | Query | Query nation data |
| `query_incidents` | Query | Query active incidents |
| `send_message` | Action | Unified message sending (to agents or player) |
| `write_memory` | Action | Short-term memory (recent/turn_*.md) |
| `write_long_term_memory` | Action | Long-term memory (MEMORY.md) |
| `update_soul` | Action | Personality evolution (soul.md append) |
| `summarize_segment` | Action | Summarize memory segments via VectorStore |
| `create_incident` | Action | Create time-limited game events |
| `start_task_session` | Action | Create sub-session for tasks |
| `end_task_session` | Action | End sub-session with summary |

**Skill System** (`agents/skills/`) — File-driven skill system (v2.0). Each skill is a markdown file with YAML Frontmatter (metadata: name, description, version, tags, priority, required_tools) and Markdown Body (task instructions, examples, constraints).

- **Three-tier caching**: Memory (LRU, size=50) → mtime (file change detection) → File system
- **Dynamic loading**: `_get_system_prompt_for_event()` loads skills on-demand based on event type
- **Event mapping**: Hardcoded registry (EventType.CHAT → chat, EventType.AGENT_MESSAGE → receive_message, EventType.TICK_COMPLETED → on_tick_completed)
- **Variable injection**: Supports `{{agent_id}}`, `{{turn}}`, `{{timestamp}}` placeholders
- **Fallback mechanism**: Hardcoded instructions used when skill loading fails

Deception emerges from LLM reading soul.md. Three-phase workflow: summarize (write memory) → respond (answer queries) → execute (carry out commands). All phases triggered by events.

**V4.2 Memory System** (`memory/`) — Event-based memory with dual-write persistence and DB-first retrieval. Enables agents to remember and retrieve historical information across sessions.

### Core Components:

**TapeWriter** (`memory/tape_writer.py`) — Dual-write event logging (V4.2).
- Writes events to BOTH `tape.jsonl` AND `tape_events` SQLite table (via TapeRepository)
- First-event detection triggers TapeMetadataManager to generate title via LLM
- Increment event count in `tape_meta.jsonl`
- Token counting using tiktoken (GPT-4 encoding: cl100k_base)
- Async file operations via aiofiles

**TapeRepository** (`persistence/tape_repository.py`) — SQLite persistence layer (V4.2).
- Own aiosqlite connection (separate from module-level singleton)
- Tables: `tape_events` (7 indexes for fast queries), `failed_embeddings`
- Key methods: `insert_event()`, `query_by_session()` (ASC order), `count_by_session()`, `record_failed_embedding()`
- Used by both TapeWriter (write path) and ContextManager (read path)

**TapeMetadataManager** (`memory/tape_metadata.py`) — Session metadata management (V4.2).
- Maintains `data/memory/tape_meta.jsonl` with session metadata
- Generates session title via LLM on first event
- Tracks: session_id, title, event_count, created_at, updated_at
- Replaces V3 ManifestIndex (simpler, JSONL-based)

**ContextManager** (`memory/context_manager.py`) — Sliding window with DB-first reads (V4.2).
- `_load_session_events()` → `tape_repository.query_by_session()` (DB-first, JSONL fallback)
- `_read_events_from_offset()` → `tape_repository.query_by_session(offset=N)`
- `_count_all_events()` → `tape_repository.count_by_session()`
- Configurable token threshold (default: 8000 tokens, 95% trigger)
- Automatic summarization when threshold exceeded
- Sliding window: keeps recent events (default: 20) after compaction

**VectorStore** (`memory/vector_store.py`) — Semantic search with retry (V4.2).
- Wraps VectorSearcher (ChromaDB) with exponential backoff retry
- Tracks failed embeddings in `failed_embeddings` table via TapeRepository
- Used by TwoLevelSearcher for L1.5 semantic matching
- Async interface compatible with Agent event loop

**TwoLevelSearcher** (`memory/two_level_searcher.py`) — Two-level retrieval (V4.2).
- **L1 (Metadata)**: TapeMetadataIndex keyword search on session titles
- **L1.5 (Vector)**: VectorStore semantic search on event embeddings
- **L2 (Segment)**: SegmentSearcher retrieves actual event content
- Combines results with configurable weights

**TapeMetadataIndex** (`memory/tape_metadata_index.py`) — Level 1 keyword search.
- Keyword matching on session titles from tape_meta.jsonl
- Returns candidate session IDs for L2 retrieval

**SegmentSearcher** (`memory/segment_searcher.py`) — Level 2 event segment search.
- Reads events from tape_repository (DB-first) or JSONL (fallback)
- Entity matching scoring (action +0.4, target +0.3, time +0.2)
- Returns formatted event segments

**QueryParser** (`memory/query_parser.py`) — Natural language query parsing.
- LLM-based parsing with few-shot prompting
- Extracts: intent (query_history/query_status/query_data)
- Extracts: entities {action: [], target: [], time: ""}
- Determines: scope (current_session/cross_session), depth (overview/tape)
- Retry logic (3 attempts) with fallback to safe defaults

**StructuredRetriever** (`memory/structured_retriever.py`) — Retrieval coordinator.
- Routes based on scope:
  - `current_session`: ContextManager.get_messages()
  - `cross_session`: TwoLevelSearcher.search()
- Routes based on depth:
  - `overview`: Returns session summaries only
  - `tape`: Returns full event details
- Coordinates all memory components

**MemoryTools** (`agents/tools/memory_tools.py`) — Agent integration (V4.2).
- Implements `retrieve_memory(args, event) -> str` tool handler
- NEW: `summarize_segment(args, event) -> str` for VectorStore integration
- Follows QueryTools pattern (returns formatted string to LLM)
- Uses ToolRegistry (not _function_handlers dict)

### Event Types in Tape:

```python
USER_QUERY      # Player queries (from CHAT events)
TOOL_CALL       # Function invocations
TOOL_RESULT     # Function results
RESPONSE        # Final agent responses (sent to player and written to tape)
GAME_EVENT      # Game state changes (create_incident, etc.)
```

### Data Flow (V4.2):

**Write Path (TapeWriter dual-write):**
```
Agent event → TapeWriter.write_event()
              ├─→ tape.jsonl (append)
              └─→ TapeRepository.insert_event() → tape_events table
                  └─→ (first event) TapeMetadataManager.generate_title()
```

**Read Path (ContextManager DB-first):**
```
ContextManager.get_messages()
  └─→ _load_session_events()
      └─→ tape_repository.query_by_session()  # DB-first
          └─→ (fallback) _read_events_from_jsonl()  # JSONL fallback
```

**Search Path (TwoLevelSearcher):**
```
TwoLevelSearcher.search(query)
  ├─→ L1: TapeMetadataIndex.keyword_search()  # Title matching
  ├─→ L1.5: VectorStore.search()              # Semantic search
  └─→ L2: SegmentSearcher.retrieve()          # Event content
```

### Memory System Configuration:

```yaml
memory:
  enabled: true
  context:
    max_tokens: 8000
    threshold_ratio: 0.95
    keep_recent_events: 20
  retrieval:
    default_max_results: 5
    cross_session_enabled: true
  vector:
    collection_name: "agent_memory"
    embedding_model: "text-embedding-3-small"
  memory_dir: "data/memory"
  db_path: "data/memory/memory.db"
```

### Design Principles:

| Principle | Implementation |
|-----------|----------------|
| **Dual-Write** | TapeWriter writes to both JSONL and SQLite |
| **DB-First Reads** | ContextManager reads from tape_events, falls back to JSONL |
| **Event Sourcing** | All events logged to tape.jsonl (immutable append-only) |
| **Session Isolation** | Each session has separate tape file and DB rows |
| **Two-Level Search** | L1 metadata + L1.5 vector + L2 segment retrieval |
| **Vector Retry** | VectorStore exponential backoff for embedding failures |
| **Separate Connection** | TapeRepository uses own aiosqlite connection |

### Injection Chain (V4.2):

```
ApplicationServices.create()
  → TapeRepository(db_path) → TapeWriter (write path)
                            → AgentService → AgentManager → Agent → MemoryInitializer → ContextManager (read path)
```

### Autonomous Memory System

Agent 自主记忆系统，让 Agent 在 tick 推进过程中定期反思，记录长期记忆并演化性格。

**配置** (`config.py` → `AutonomousMemoryConfig`):

```yaml
autonomous_memory:
  enabled: true                # 是否启用自主记忆反思
  check_interval_ticks: 4      # 每隔多少 tick 反思一次（4 = 每月）
  soul_evolution_enabled: true  # 是否允许 soul.md 性格演化
```

**触发机制**:
- `agent.py` 中 `_memory_tick_counter` 每收到 TICK_COMPLETED 事件递增
- 当 `counter % check_interval_ticks == 0` 时触发 LLM 反思（复用 `_process_event_with_llm`）
- 反思由 TICK_COMPLETED 系统 prompt 引导，流程：retrieve_memory → query → write_long_term_memory → (可选) update_soul → finish_loop

**工具** (`action_tools.py`):

| 工具 | 功能 | 存储位置 |
|------|------|----------|
| `write_memory` | 短期记忆（保留最近3回合） | `data/agent/{id}/memory/recent/turn_*.md` |
| `write_long_term_memory` | 长期记忆（永久保存） | `data/agent/{id}/memory/MEMORY.md` |
| `update_soul` | 性格演化（追加式，不破坏原始人设） | `data/agent/{id}/soul.md` → `## 性格变化记录` 段 |

**Soul 演化机制**:
- `update_soul` 在 `soul.md` 末尾追加 `## 性格变化记录` 段落
- 每次追加 `### Tick {n}` 子段落，记录性格变化原因和结果
- 写入后触发 `on_soul_updated` 回调，Agent 自动重新加载 soul
- 系统 prompt 强调仅在重大事件（被斥责、重大灾难、重大成就）时使用

**CLI** (`cli/`) — Player interface. Rich/textual-based TUI. Natural language commands parsed by LLM. Sends events to EventBus, subscribes to `player` ID for responses. Modes: command mode (single commands), chat mode (conversational).

**Persistence** (`persistence/`) — Data access layer (V4.2). Async SQLite via aiosqlite, repository pattern. Tables: game_state, turn_metrics, agent_state, events, incidents, tape_events (V4.2), failed_embeddings (V4.2). Shared by all modules for reads, exclusive writes by Engine. TapeRepository uses separate connection for memory events.

**LLM** (`llm/`) — LLM provider abstraction. Supports Anthropic Claude, OpenAI GPT, and Mock (testing). Single interface: `async call(prompt, system_prompt, temperature, max_tokens) -> str`.

**Engine** (`engine/`) — Economic formulas (reused from V1). 13 pure functions: grain production/demand/balance, taxes, military upkeep, happiness, population, morale, commerce, treasury. No I/O, no side effects.

### Event Format

All events use this JSON structure:

```json
{
    "event_id": "evt_20260226120000_a1b2c3d4",
    "src": "player",
    "dst": ["agent:revenue_minister"],
    "type": "command",
    "payload": {"intent": "adjust_tax", "province": "zhili", "rate": 0.05},
    "timestamp": "2026-02-26T12:00:00.123456Z"
}
```

**ID Naming:**
- Player: `"player"`
- Agent: `"agent:{agent_id}"` (e.g., `"agent:revenue_minister"`)
- TickCoordinator: `"system:tick_coordinator"`
- Broadcast: `"*"`

**Event Types:**
- `command` — Player → Agent (execute command)
- `query` — Player → Agent (query information)
- `chat` — Player → Agent (enter conversation)
- `response` — Agent → Player (narrative response)
- `agent_message` — Agent → Agent (inter-agent communication)
- `tick_completed` — TickCoordinator → * (tick calculation complete, V4)
- `session_state` — System → Client (session state sync)

### Tick Flow (V4)

```
1. TickCoordinator timer triggers (every N seconds, default 5s)

2. TickCoordinator calls Engine.apply_tick()
   - Apply base growth rates (production_value *= 1.01, population *= 1.005)
   - Apply all active Effects (add once, factor every tick)
   - Calculate tax and treasury updates
   - Refresh Incidents (decrement remaining_ticks, remove expired)

3. TickCoordinator → {"type": "tick_completed", "dst": ["*"], "payload": {"tick": 42}}

4. All Agents receive "tick_completed" → Respond if needed
```

**Time Units:**
- 1 tick = 1 week
- 4 ticks = 1 month
- 48 ticks = 1 year

**Effect Types:**
- `add`: One-time numeric change (e.g., stockpile += 1000, only applied once)
- `factor`: Continuous percentage multiplier (e.g., production_value *= 1.1, every tick)

### Game Action Flow (V4)

**Current State:**
- Agents respond to player commands by querying data and replying in character
- Game state changes occur via Engine's automatic tick progression
- Initial state loaded from `data/initial_state_v4.json` (simplified 4-field model)

**Planned Development:**
- Agents will be able to create Incident objects to influence game state
- Incidents can have time-limited Effects that modify province/nation data
- This allows agents to take actions with persistent, trackable consequences

```
Future flow:
Player → Agent (via command event)
Agent → creates Incident → Engine.add_incident()
Engine → apply_tick() → applies active Effects
Game state updates → tick_completed event → Agents notified
```

### Key Patterns

- **Pydantic v2** models with `Decimal` precision for all game data
- **Event sourcing:** All state changes logged as events (JSONL format)
- **File-driven agents:** Personality/permissions defined by markdown/YAML, not code
- **V2 Memory:** Dual-layer — long-term (summary.md, agent-maintained) + short-term (recent/, 3-turn sliding window)
- **V4.2 Memory:** Dual-write persistence (JSONL + SQLite), DB-first reads, two-level search (L1 metadata + L1.5 vector + L2 segment)
- **Autonomous Memory:** Tick-interval self-reflection with long-term memory (MEMORY.md) and soul evolution (soul.md append)
- **Context Management:** Sliding window with automatic summarization (Tiktoken token counting)
- **Natural Language Queries:** LLM-based query parsing with entity extraction
- **V4.2 Patterns:**
  - **Dual-write:** TapeWriter writes to both JSONL and SQLite tape_events table
  - **DB-first reads:** ContextManager reads from tape_repository, falls back to JSONL
  - **Event queue backpressure:** Agent processes events via asyncio.Queue with configurable max_size
  - **VectorStore retry:** Exponential backoff for embedding failures, tracks in failed_embeddings table
  - **TapeRepository own connection:** Separate aiosqlite connection from module-level DB singleton
  - **ToolRegistry:** Tool system uses ToolRegistry class, not _function_handlers dict
- **LLM emergence:** Deception/slacking emerges from soul.md personality, no hardcoded numbers
- **Repository pattern:** All data access through Repository interface
- **Async everywhere:** asyncio, aiosqlite, aiofiles
- **Deterministic engine:** Random functions accept seeded `random.Random` for reproducibility

### Data Models (V4)

**ProvinceData (simplified from V3):**
```python
@dataclass
class ProvinceData:
    province_id: str
    name: str

    # Four core fields
    production_value: Decimal  # Economic output
    population: Decimal         # Population count
    fixed_expenditure: Decimal  # Fixed costs
    stockpile: Decimal          # Inventory/reserves

    # Growth rates (fixed)
    base_production_growth: Decimal = 0.01   # 1%/tick
    base_population_growth: Decimal = 0.005  # 0.5%/tick

    # Tax modifier (province-level adjustment)
    tax_modifier: Decimal = 0.0
```

**NationData:**
```python
@dataclass
class NationData:
    turn: int                           # Current tick number
    base_tax_rate: Decimal = 0.10       # National base tax rate 10%
    tribute_rate: Decimal = 0.8         # Remittance ratio 80%
    fixed_expenditure: Decimal = 0      # Imperial fixed costs
    imperial_treasury: Decimal = 0      # Imperial treasury
    provinces: Dict[str, ProvinceData]   # Province dictionary
```

**Incident (time-limited game event):**
```python
@dataclass
class Incident:
    incident_id: str
    title: str
    description: str
    effects: List[Effect]
    source: str
    remaining_ticks: int  # > 0, decrements each tick
    applied: bool = False  # Marks if add-effects were applied
```

**Effect (single modification):**
```python
@dataclass
class Effect:
    target_path: str  # e.g. "provinces.zhili.production_value"
    add: Optional[Decimal] = None      # One-time change
    factor: Optional[Decimal] = None   # Continuous multiplier
    # Exactly one of add or factor must be set
```

### Import Rules

```python
# ✅ Correct: upper imports lower
from simu_emperor.event_bus.core import EventBus
from simu_emperor.engine.engine import Engine
from simu_emperor.agents.agent import Agent

# ✅ Correct: same-level imports
from simu_emperor.agents.context_builder import build_context
from simu_emperor.agents.memory_manager import MemoryManager

# ❌ Wrong: lower imports upper
from simu_emperor.cli.app import EmperorCLI  # core must not import cli
```

### Documentation

**V2 Architecture:**
- `.prd/V2_PRD.md` — Product requirements (event-driven architecture)
- `.design/V2_TDD.md` — Technical design document (detailed specs)
- `.design/V2_SKILL_TOOL_REFACTOR_DESIGN.md` — Skill system design (v2.0)
- `.design/2026-03-01-skill-tool-refactor-implementation.md` — Skill system implementation plan

**V4.2 Memory System:**
- `.design/V3_MEMORY_SYSTEM_SPEC.md` — Memory system specification (query parsing, retrieval, context management)
- `.design/V4.2_PERSISTENCE_ENHANCEMENT.md` — V4.2 dual-write, DB-first, VectorStore patterns

**V1 Architecture (deprecated, reference for engine reuse):**
- `.plan/rewrite_plan_v1.1.md` — Full system architecture
- `.plan/eco_system_design.md` — Economic system formulas + data model
- `.plan/agent_design_v1.1.md` — Agent module design
- `.review/` — Design reviews

## Development Workflow

V4 implementation follows the design defined in `.plan/engine-refactor-v4-design.md`:

**Stage 1: Basic Models** — Incident, Effect, simplified ProvinceData/NationData ✅
**Stage 2: Engine Core** — apply_tick() with growth rates, Effects, tax calculation ✅
**Stage 3: TickCoordinator** — Timer-based tick progression with event publishing ✅
**Stage 4: Cleanup** — Removed core/, interfaces/, old engine files ✅
**Stage 5: Testing** — 45 unit tests for new engine module ✅
**Stage 6: Documentation** — Updated CLAUDE.md ✅

**V4 Engine (Completed 2026-03-09):**
- ✅ engine/models/incident.py: Effect and Incident dataclasses
- ✅ engine/models/base_data.py: Simplified to 4 core fields
- ✅ engine/engine.py: Engine class with apply_tick()
- ✅ engine/tick_coordinator.py: TickCoordinator with timer loop
- ✅ event_types.py: Added TICK_COMPLETED event type
- ✅ 45 unit tests (100% passing)
- ✅ Deleted old code: core/, interfaces/, formulas.py
- ✅ Updated CLAUDE.md with V4 architecture

**Skill System (Completed 2026-03-03):**
- ✅ Week 1: Infrastructure (models, parser, validator, loader, registry)
- ✅ Week 1.5-2: Agent integration (dynamic skill loading, variable injection)
- ✅ Week 2: Skill file migration (7 files rewritten to v2.0 format)
- ✅ 73 unit tests (100% passing)
- ✅ Code review and Important issues fixed

**Memory System:**
- ✅ Event-based retrieval with tape.jsonl logs + manifest.json index
- ✅ Sliding window context management with automatic summarization
- ✅ Natural language query parsing (LLM-based)
- ✅ tiktoken dependency added
- ✅ `retrieve_memory` tool registered in function handlers

**Autonomous Memory System (Completed 2026-03-18):**
- ✅ `AutonomousMemoryConfig` in config.py (enabled, check_interval_ticks, soul_evolution_enabled)
- ✅ `write_long_term_memory` tool (MEMORY.md persistent storage)
- ✅ `update_soul` tool (soul.md append-only personality evolution with reload callback)
- ✅ `write_memory` tool registered (previously implemented but unregistered)
- ✅ Tick-interval reflection logic (_memory_tick_counter, conditional LLM trigger)
- ✅ TICK_COMPLETED system prompt rewritten for reflection workflow
- ✅ on_tick_completed.md skill updated to v2.0
- ✅ 20 new tests (unit + integration), 610 total tests passing

**V4.2 Persistence Enhancement (Completed 2026-03-29):**
- ✅ Agent event queue with backpressure (asyncio.Queue, configurable max_size)
- ✅ DB schema: tape_events (7 indexes) + failed_embeddings tables
- ✅ TapeRepository with CRUD (insert_event, query_by_session, count_by_session, record_failed_embedding)
- ✅ VectorStore with retry + summarize_segment tool
- ✅ TapeWriter dual-write (JSONL + tape_events)
- ✅ ContextManager DB-first reads (tape_repository query, JSONL fallback)
- ✅ Full injection chain: ApplicationServices → AgentService → AgentManager → Agent → MemoryInitializer → ContextManager
- ✅ 645 tests passing

When implementing features:
1. Read the relevant design docs (`.prd/V2_PRD.md`, `.design/V2_TDD.md`, `.design/V2_SKILL_TOOL_REFACTOR_DESIGN.md`)
2. Check existing tests for patterns
3. Write unit tests before implementation (TDD)
4. Run `uv run ruff check .` and `uv run pytest` before committing
5. Update this CLAUDE.md if architecture changes

## Coding Standards

### Error Handling

**❌ FORBIDDEN: Silent Failures with Hardcoded Fallbacks**

Do NOT use hardcoded fallback values when data is missing or operations fail. This hides bugs and misleads users.

```python
# ❌ WRONG: Hardcoded fallback
async def get_user_info(user_id: str) -> str:
    try:
        return await database.fetch_user(user_id)
    except Exception:
        # Hardcoded fallback - misleading!
        return "John Doe (admin)"

# ❌ WRONG: Silent fallback with default data
if not role_map_path.exists():
    return """朝廷现任官员：
- 直隶巡抚 李卫: ...
- 户部尚书 张廷玉: ..."""
```

**✅ CORRECT: Explicit Error Messages**

```python
# ✅ GOOD: Explicit error
async def get_user_info(user_id: str) -> str:
    user = await database.fetch_user(user_id)
    if not user:
        return f"❌ 用户 {user_id} 不存在"
    return user.format_info()

# ✅ GOOD: Fail fast with clear message
if not role_map_path.exists():
    return "❌ 无法查询官员信息：role_map.md 文件不存在"

# ✅ GOOD: Parse failure with actionable message
if not agents_info:
    return "❌ role_map.md 解析失败：未找到任何官员信息，请检查文件格式"
```

**Rationale:**
- Hardcoded fallbacks mask data issues
- Users receive incorrect information without knowing it's an error
- Debugging becomes harder when errors are silently hidden
- Explicit errors force developers to fix root causes

**Exceptions:** The only acceptable fallback is:
1. Testing/Mock mode (explicitly enabled)
2. Feature flags with user consent
3. Cached data with explicit TTL and staleness warning

### Logging

- Use structured logging with clear context
- Include `request_id` / `event_id` for traceability
- Log levels: DEBUG (dev info), INFO (normal ops), WARNING (recoverable issues), ERROR (failures)

## Testing Strategy

- **Unit tests:** Mock all I/O and LLM calls. Test pure logic.
- **Integration tests:** Real database (in-memory), mock LLM. Test event flows.
- **E2E tests:** Full game loop, mock LLM. Test multi-turn scenarios.
- **No external dependencies:** All tests runnable without API keys.

## Key Differences from V1

| Aspect | V1 (Phase-Driven) | V4 (Tick-Based) |
|--------|-------------------|-------------------|
| **Communication** | Direct function calls | EventBus (async) |
| **Game Loop** | GameLoop enforces phases | TickCoordinator (timer-based) |
| **Timing** | Manual turn advancement | Automatic tick progression |
| **Time Unit** | 1 turn = 1 year | 1 tick = 1 week (48 ticks = 1 year) |
| **Player UI** | FastAPI + Vue.js | Rich CLI |
| **Agent Initiation** | None (passive) | None (passive) |
| **State Writes** | GameLoop → Repository | Engine only |
| **Data Model** | 8 nested data types | 4 core fields per province |
| **Events** | Hardcoded formulas | Incident/Effect system |
| **Concurrency** | Phase-locked, agents parallel within phase | Fully async, event-driven |
| **Event Logging** | Database tables | JSONL files + SQLite (dual-write) |

**Preserved from V1:**
- Agent file-driven design (soul.md, data_scope.yaml)
- Deception via LLM emergence
- Memory: summary.md + recent/ (agent-maintained)

**Added in V4:**
- Tick-based automatic progression (timer-driven)
- Simplified data models (4 core fields vs 8 nested types)
- Incident/Effect system (time-limited game events)
- Fixed growth rates with Effect-based modifications
- Unified tax rate system with province modifiers

**Added in V4.2:**
- Dual-write persistence (JSONL + SQLite tape_events)
- DB-first reads with JSONL fallback
- Agent event queue with backpressure
- VectorStore with retry for embedding failures
- Two-level search (L1 metadata + L1.5 vector + L2 segment)
- ToolRegistry replacing _function_handlers dict
