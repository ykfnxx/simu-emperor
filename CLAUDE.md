# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (uv workspace)
uv sync

# Run tests
uv run pytest tests/                    # All tests
uv run pytest tests/ -k "not MemoryStore and not MemoryRetriever"  # Skip ChromaDB tests
uv run pytest tests/unit/               # Unit tests only

# Lint and format
uv run ruff check .
uv run ruff format .

# Start server
uv run python -m simu_server

# Start a single agent (usually done by server's ProcessManager)
SIMU_SERVER_URL=http://localhost:8000 SIMU_AGENT_ID=governor_zhili \
  SIMU_AGENT_TOKEN=xxx SIMU_CONFIG_PATH=data/agents/governor_zhili \
  uv run python -m simu_sdk
```

## Architecture

**V5: Process-Per-Agent Multi-Agent Architecture**

Emperor simulation game. The player is the emperor; AI agents play court officials (governors, ministers). Each agent runs as an independent subprocess communicating with the central Server via SSE (events) and HTTP callbacks (actions).

### Core Principles

| Principle | Description |
|-----------|-------------|
| **Process-per-Agent** | Each agent is an independent Python subprocess |
| **SSE + HTTP Callback** | Server pushes events via SSE; agents call back via HTTP |
| **Serial Dispatch** | QueueController ensures one invocation at a time per agent |
| **ReAct Loop** | Agents use reason-act-observe cycles with LLM + tool calls |
| **File-Driven Personality** | `soul.md` + `data_scope.yaml` define each agent |
| **Tape-Based History** | Append-only JSONL + SQLite event logs per agent |

### Package Structure

```
packages/
├── shared/         # Pydantic models (TapeEvent, NationData, Effect, etc.)
│   └── simu_shared/
│       ├── models.py       # All data models
│       └── constants.py    # EventType enum
│
├── server/         # FastAPI backend — orchestration, state, routing
│   └── simu_server/
│       ├── app.py          # Startup, dependency wiring, dispatch function
│       ├── routes/
│       │   ├── client.py   # Frontend API (/api/command, /api/state, /ws, etc.)
│       │   └── callback.py # Agent API (/api/callback/*, SSE, incidents)
│       ├── services/
│       │   ├── event_router.py       # Per-agent asyncio.Queue, SSE delivery
│       │   ├── queue_controller.py   # Per-agent FIFO, serial dispatch
│       │   ├── process_manager.py    # Subprocess spawn/terminate
│       │   ├── session_manager.py    # Session CRUD (SQLite)
│       │   ├── message_store.py      # Message persistence (SQLite + JSONL)
│       │   ├── invocation_manager.py # Invocation lifecycle tracking
│       │   └── group_store.py        # Agent groups
│       ├── engine/
│       │   ├── game_engine.py  # Facade: GameState + TickCoordinator + IncidentSystem
│       │   ├── state.py        # NationData + ProvinceData (Decimal precision)
│       │   ├── tick.py         # Turn advancement, growth, tax calculation
│       │   └── incidents.py    # Time-limited economic effects (add/factor)
│       └── stores/
│           └── database.py     # SQLite + WAL mode
│
├── sdk/            # Agent runtime SDK
│   └── simu_sdk/
│       ├── agent.py        # BaseAgent: lifecycle, event dispatch, ReAct, prompts
│       ├── client.py       # ServerClient: HTTP + SSE communication
│       ├── config.py       # AgentConfig from environment variables
│       ├── react.py        # ReActLoop: LLM → tool calls → observations
│       ├── tools/
│       │   ├── registry.py   # @tool decorator, ToolRegistry
│       │   ├── standard.py   # send_message, query_state, create_incident, task sessions
│       │   └── memory.py     # search_memory tool
│       ├── tape/
│       │   ├── manager.py    # TapeManager: JSONL + SQLite dual-write
│       │   └── context.py    # ContextManager: sliding window, summaries, views
│       ├── memory/
│       │   ├── store.py      # MemoryStore (ChromaDB vector DB)
│       │   ├── retriever.py  # MemoryRetriever (L1 session, L2 view search)
│       │   └── metadata.py   # TapeMetadataManager (SQLite)
│       └── llm/
│           ├── base.py       # LLMProvider interface
│           ├── anthropic.py  # Claude integration
│           └── openai.py     # OpenAI/compatible integration
│
└── agents/         # Concrete agent configs (soul.md + data_scope.yaml per agent)

web/                # React + Vite + TypeScript + Tailwind frontend
├── src/App.tsx     # Main component, WebSocket, chat UI
└── src/api/        # GameClient (REST + WebSocket)

data/
├── default_agents/     # Agent templates (soul.md + data_scope.yaml)
├── agent_templates/    # For dynamic agent generation
└── memory/             # Runtime mirror (tape_meta.jsonl, per-agent sessions)
```

### Communication Flow

**Player → Agent:**
```
Frontend POST /api/command
  → TapeEvent(src=player, type=CHAT)
  → QueueController.enqueue(agent_id, event)
  → InvocationManager.create() → EventRouter.route()
  → Agent receives via SSE /api/callback/events
  → BaseAgent.on_event() → react(event)
  → ReActLoop: LLM + tool calls
  → RESPONSE → push_tape_event → post_message → WebSocket → Frontend
```

**Agent → Agent:**
```
Agent A: send_message(recipients=["agent_b"], await_reply=true)
  → POST /api/callback/message → QueueController → EventRouter → Agent B SSE
  → Agent B react() → text output → RESPONSE auto-routed back to A
  → A's pending reply cleared → A continues processing
```

**Task Sessions:**
```
create_task_session(goal="...") → enters child session
  → send_message(await_reply=true) → waits
  → reply arrives → finish_task_session(result="...")
  → TASK_FINISHED routed to parent session → agent reports to player
```

### Agent System

Agents are file-driven AI officials. `soul.md` defines personality/behavior, `data_scope.yaml` defines data access permissions.

**Standard Tools:**

| Tool | Category | Description |
|------|----------|-------------|
| `send_message` | communication | Send to agents/player, optional `await_reply` |
| `query_state` | communication | Query game state (provinces, treasury) |
| `query_role_map` | communication | Look up agent IDs by official name |
| `create_incident` | action | Create economic effects (add/factor on fields) |
| `create_task_session` | session | Create sub-session for focused work |
| `finish_task_session` | session | Complete task, return result to parent |
| `fail_task_session` | session | Fail task with reason |
| `search_memory` | memory | Vector search across past sessions |

**System Prompt Construction** (`_build_system_prompt`):
1. `soul.md` content (personality)
2. `data_scope.yaml` (permissions)
3. Action execution instructions (when to use `create_incident`)
4. Task dispatch or task execution instructions (context-dependent)
5. Agent reply instructions (text reply vs send_message)

### Session State Management

`SessionStateManager` in each agent tracks:
- `pending_tasks`: unfinished task sub-sessions
- `pending_replies`: messages awaiting reply (from `await_reply=true`)
- `message_queue`: events queued while session is blocked
- Session hierarchy: parent/child relationships, nesting depth (max 5)

When a session is blocked (has pending tasks or replies), new events are queued. When unblocked, queued events are drained through the ReAct loop.

### Memory System

**Tape** (per-agent, per-session):
- JSONL + SQLite dual-write
- Optional mirror to `data/memory/` (via `SIMU_MEMORY_DIR`)

**Context Window**:
- Sliding window with auto-compression into ViewSegments
- Session summaries generated by LLM after each response
- Views stored in ChromaDB for cross-session retrieval

**Memory Retrieval** (two-level):
- L1: Search across sessions by title/summary
- L2: Search within sessions for specific views

### Engine & Economic Model

**Tick** (manual trigger via `POST /api/state/tick`):
```
TickCoordinator.tick()
  → Apply base growth (production, population)
  → Apply active Incident effects (add: one-time, factor: per-tick)
  → Calculate tax: production × (base_tax_rate + tax_modifier)
  → Calculate surplus, remittance, treasury
  → Decrement incident remaining_ticks, expire completed
```

**Key Fields:**
- Province: `production_value`, `population`, `fixed_expenditure`, `stockpile`, `tax_modifier`, `base_production_growth`, `base_population_growth`
- Nation: `imperial_treasury`, `base_tax_rate`, `tribute_rate`, `fixed_expenditure`
- `tax_modifier` is an additive offset (initial 0.0), not the tax rate itself

### Event Types

| Type | Direction | Description |
|------|-----------|-------------|
| `CHAT` | player → agent | Player command |
| `AGENT_MESSAGE` | agent → agent | Initiated communication |
| `RESPONSE` | agent → agent/player | Auto-routed reply |
| `TASK_CREATED` | agent → self | Synthetic event for new task |
| `TASK_FINISHED` | server → agent | Task completed |
| `TASK_FAILED` | server → agent | Task failed |
| `TOOL_CALL` | agent → tape | ReAct loop tool invocation |
| `TOOL_RESULT` | agent → tape | Tool execution result |
| `SHUTDOWN` | server → agent | Graceful shutdown |
| `RELOAD_CONFIG` | server → agent | Hot-reload personality |

## Coding Standards

### Error Handling

**FORBIDDEN: Silent failures with hardcoded fallbacks.** Do NOT return fake data when operations fail.

```python
# ❌ WRONG
if not role_map_path.exists():
    return """朝廷现任官员：- 直隶巡抚 李卫: ..."""  # Hardcoded!

# ✅ CORRECT
if not role_map_path.exists():
    return "无法查询官员信息：role_map 文件不存在"
```

### Key Patterns

- **Pydantic v2** with `Decimal` precision for game data
- **Event sourcing:** Append-only JSONL + SQLite tape
- **@tool decorator** for registering agent tools
- **ToolResult** with `ends_loop=True` for session-switching tools
- **Hot-reload:** `soul.md` / `data_scope.yaml` changes auto-detected
- **asyncio throughout:** All I/O is async

### Import Rules

Packages have strict dependency directions:
```
shared ← sdk ← agents
shared ← server
```
SDK and server do NOT depend on each other — they communicate via HTTP/SSE.

## Development Workflow

1. Check existing tests for patterns
2. Run `uv run ruff check .` and `uv run pytest` before committing
3. Use `develop-v5` as the primary development branch
4. Create feature/fix branches from `develop-v5`
5. PR review required before merge

### Design Documents

- `docs/architecture/ARCHITECTURE.md` — V5 architecture details
- `docs/research/v6-architecture-research.md` — Future architecture research
