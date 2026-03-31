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

Tick-based emperor simulation game. The player is the emperor; AI agents play officials who may lie in reports and slack off when executing commands. All communication happens through an event bus — no direct function calls between modules. The game advances automatically via periodic ticks (1 tick = 1 week, 4 ticks = 1 month, 48 ticks = 1 year).

### Core Principles

| Principle | Description |
|-----------|-------------|
| **Event-Driven** | All interactions via EventBus (src/dst routing) |
| **Fully Async** | asyncio-based, fire-and-forget by default |
| **Tick-Based Timing** | Automatic tick progression (configurable interval, default 5s) |
| **Unified Writes** | Only Engine can modify game state |
| **Passive Agents** | Agents only respond to events, never initiate |
| **Clean Architecture** | Adapter → Application → Core (no upward dependencies) |

### Directory Structure

```
src/simu_emperor/
├── event_bus/          # Event routing (EventBus, Event, EventType)
├── engine/             # Game engine (Engine, TickCoordinator, ProvinceData/NationData, Incident/Effect)
├── agents/             # AI officials
│   ├── agent.py        # Agent base (event queue with backpressure)
│   ├── react_loop.py   # ReAct loop for LLM tool-calling
│   ├── system_prompts.py # System prompt assembly
│   ├── skills/         # File-driven skill system (YAML frontmatter + markdown)
│   └── tools/          # ToolRegistry, query/action/memory/task_session tools
├── memory/             # Memory system (dual-write, DB-first reads, two-level search)
├── application/        # Application layer (GameService, SessionService, AgentService, etc.)
├── persistence/        # SQLite via aiosqlite (repositories + TapeRepository)
├── llm/                # LLM providers (Anthropic, OpenAI, Mock)
├── adapters/web/       # FastAPI server, WebSocket, message converter
├── session/            # Session management, group chat
└── common/             # Utilities

data/
├── skills/             # Universal skill templates (v2.0 format)
├── default_agents/     # Agent templates (soul.md + data_scope.yaml)
├── agent/              # Active agent workspace (runtime, mutable)
├── memory/             # Dual-write storage (tape_meta.jsonl + per-agent sessions)
└── initial_state_v4.json

tests/
├── unit/               # Mock all I/O and LLM
├── integration/        # Real DB (in-memory), mock LLM
└── e2e/                # Full game loop, mock LLM
```

### Agent System

Agents are file-driven AI officials. `soul.md` defines personality/behavior, `data_scope.yaml` defines data access permissions (per-skill field whitelist). Deception emerges from LLM reading soul.md — no hardcoded logic.

**Available Tools:**

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

**Skill System** — Each skill is a markdown file with YAML frontmatter. Three-tier caching (Memory LRU → mtime → FS). Event-to-skill mapping: `CHAT → chat.md`, `AGENT_MESSAGE → receive_message.md`, `TICK_COMPLETED → on_tick_completed.md`. Supports `{{agent_id}}`, `{{turn}}`, `{{timestamp}}` placeholders.

**Autonomous Memory** — Agents self-reflect every N ticks (default 4 = monthly). On reflection tick: `retrieve_memory → write_long_term_memory → (optional) update_soul`. Config: `AutonomousMemoryConfig` in `config.py`.

### Memory System

Dual-write event-based memory with DB-first retrieval.

**Write Path:** `Agent event → TapeWriter → tape.jsonl + TapeRepository (SQLite tape_events)`

**Read Path:** `ContextManager → TapeRepository (DB-first) → JSONL fallback`

**Search Path (cross-session):**
- L1: TapeMetadataIndex — keyword search on session titles
- L1.5: VectorStore (ChromaDB) — semantic search with retry
- L2: SegmentSearcher — event content retrieval

**Context Management:** Sliding window with auto-summarization (8000 token threshold, keeps 20 recent events after compaction).

### Event System

```json
{
    "event_id": "evt_20260226120000_a1b2c3d4",
    "src": "player",
    "dst": ["agent:revenue_minister"],
    "type": "command",
    "payload": {"intent": "adjust_tax", "province": "zhili", "rate": 0.05}
}
```

**ID Naming:** Player: `"player"`, Agent: `"agent:{agent_id}"`, TickCoordinator: `"system:tick_coordinator"`, Broadcast: `"*"`

**Event Types:** `command` (Player→Agent), `query` (Player→Agent), `chat` (Player→Agent), `response` (Agent→Player), `agent_message` (Agent→Agent), `tick_completed` (TickCoordinator→*)

**Tape Event Types:** `USER_QUERY`, `TOOL_CALL`, `TOOL_RESULT`, `RESPONSE`, `GAME_EVENT`

### Engine & Tick Flow

```
TickCoordinator timer → Engine.apply_tick()
  → Apply growth rates (production ×1.01, population ×1.005)
  → Apply active Effects (add: one-time, factor: per-tick multiplier)
  → Calculate tax/treasury
  → Refresh Incidents (decrement remaining_ticks, remove expired)
  → Publish tick_completed event to all agents
```

### Session State Isolation

Every agent maintains independent state per session. All state checks/mutations scoped to calling agent.

- `agent_states: dict[str, str]` — per-agent (`ACTIVE` / `WAITING_REPLY` / `FINISHED` / `FAILED`)
- `pending_async_replies: dict[str, int]` — per-agent async reply counter
- Cross-session messages: only the sender's counter increments, receiver processes normally

### Import Rules

```python
# ✅ Upper imports lower
from simu_emperor.event_bus.core import EventBus
from simu_emperor.agents.agent import Agent

# ❌ Lower must NOT import upper
from simu_emperor.cli.app import EmperorCLI  # core must not import cli
```

### Key Patterns

- **Pydantic v2** with `Decimal` precision for game data
- **Event sourcing:** Immutable append-only JSONL logs
- **Dual-write:** TapeWriter writes to both JSONL and SQLite
- **DB-first reads:** ContextManager reads from SQLite, falls back to JSONL
- **ToolRegistry class** (not _function_handlers dict)
- **Event queue backpressure:** asyncio.Queue with configurable max_size
- **Deterministic engine:** Random functions accept seeded `random.Random`
- **Repository pattern:** All data access through Repository interface

## Coding Standards

### Error Handling

**FORBIDDEN: Silent failures with hardcoded fallbacks.** Do NOT return fake data when operations fail.

```python
# ❌ WRONG
if not role_map_path.exists():
    return """朝廷现任官员：- 直隶巡抚 李卫: ..."""  # Hardcoded!

# ✅ CORRECT
if not role_map_path.exists():
    return "❌ 无法查询官员信息：role_map.md 文件不存在"
```

Acceptable fallbacks: testing/mock mode, feature flags with consent, cached data with staleness warning.

### Logging

- Structured logging with `request_id` / `event_id` for traceability
- Levels: DEBUG (dev), INFO (normal), WARNING (recoverable), ERROR (failures)

## Development Workflow

1. Read relevant design docs in `.prd/` and `.design/`
2. Check existing tests for patterns
3. Write unit tests before implementation (TDD)
4. Run `uv run ruff check .` and `uv run pytest` before committing
5. Update this CLAUDE.md if architecture changes

### Design Documents

- `.prd/V2_PRD.md` — Product requirements
- `.design/V2_TDD.md` — Technical design
- `.design/V2_SKILL_TOOL_REFACTOR_DESIGN.md` — Skill system design
- `.design/V3_MEMORY_SYSTEM_SPEC.md` — Memory system spec
- `.design/V4.2_PERSISTENCE_ENHANCEMENT.md` — Dual-write, DB-first patterns

## Testing Strategy

- **Unit tests:** Mock all I/O and LLM calls. Test pure logic.
- **Integration tests:** Real database (in-memory), mock LLM. Test event flows.
- **E2E tests:** Full game loop, mock LLM. Test multi-turn scenarios.
- **No external dependencies:** All tests runnable without API keys.
