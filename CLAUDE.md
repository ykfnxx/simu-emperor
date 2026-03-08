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

**V3: Event-Driven Multi-Agent Architecture with Memory System**

Turn-based emperor simulation game. The player is the emperor; AI agents play officials who may lie in reports and slack off when executing commands. All communication happens through an event bus — no direct function calls between modules.

### Core Principles

| Principle | Description |
|-----------|-------------|
| **Event-Driven** | All interactions via EventBus (src/dst routing) |
| **Fully Async** | asyncio-based, fire-and-forget by default |
| **Shared Data Reads** | Modules read directly from persistence (per permissions) |
| **Unified Writes** | Only Calculator can modify game state |
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
│   ├── event_types.py                # EventType constants
│   └── logger.py                     # EventLogger (JSONL format)
│
├── core/                             # Module: Calculator (game state manager)
│   ├── calculator.py                 # Calculator class (turn coordination)
│   ├── turn_coordinator.py           # Turn resolution logic
│   └── event_handlers.py             # Event handlers for game actions
│
├── agents/                           # Module: AI officials
│   ├── agent.py                      # Agent base class
│   ├── manager.py                    # Agent lifecycle (init/add/remove)
│   ├── skills/                       # Sub-module: File-driven skill system
│   │   ├── models.py                 # Skill data models (SkillMetadata, Skill)
│   │   ├── exceptions.py             # Skill exception classes
│   │   ├── config.py                 # Skill configuration
│   │   ├── parser.py                 # YAML Frontmatter + Markdown parser
│   │   ├── validator.py              # Skill validation logic
│   │   ├── loader.py                 # Three-tier caching loader
│   │   ├── registry.py               # Event-to-skill mapping registry
│   │   └── watcher.py                # File watcher for hot-reload (TODO)
│   ├── tools/                        # Sub-module: Tool handlers for function calling
│   │   ├── query_tools.py            # Query handlers (return data to LLM)
│   │   ├── action_tools.py           # Action handlers (execute side effects)
│   │   └── memory_tools.py           # Memory handlers (V3: retrieve_memory)
│   ├── context_builder.py            # LLM context assembly (data_scope parsing)
│   ├── memory_manager.py             # V2 Memory: short-term (3 turns) + long-term
│   ├── file_manager.py               # File I/O for agent files
│   └── response_parser.py            # Parse LLM structured output
│
├── memory/                           # Module: V3 Memory System (NEW)
│   ├── models.py                     # Memory data models
│   │   ├── StructuredQuery           # Parsed query (intent, entities, scope, depth)
│   │   ├── ParseResult               # Query parsing result
│   │   └── RetrievalResult           # Memory retrieval result
│   ├── exceptions.py                 # Memory exceptions (ParseError, RetrievalError)
│   ├── tape_writer.py                # Event logging to tape.jsonl
│   ├── manifest_index.py             # Session metadata management (manifest.json)
│   ├── context_manager.py            # Sliding window context with summarization
│   ├── query_parser.py               # LLM-based natural language query parsing
│   ├── tape_searcher.py              # Cross-session event search
│   └── structured_retriever.py       # Retrieval coordinator (routes scope/depth)
│
├── cli/                              # Module: Player interface
│   ├── app.py                        # EmperorCLI main class
│   ├── ui.py                         # TUI components (rich/textual)
│   ├── commands.py                   # Command handlers (/help, /chat, /end_turn)
│   └── intent_parser.py              # LLM-based natural language parsing
│
├── persistence/                      # Module: Data persistence
│   ├── database.py                   # SQLite connection (aiosqlite)
│   ├── repositories.py               # Repository pattern CRUD
│   └── serialization.py              # GameState ↔ DB conversion
│
├── llm/                              # Module: LLM providers
│   ├── base.py                       # LLMProvider interface
│   ├── anthropic.py                  # Anthropic Claude implementation
│   ├── openai.py                     # OpenAI GPT implementation
│   └── mock.py                       # Mock provider (testing)
│
├── interfaces/                       # Module: Interface definitions
│   ├── events.py                     # Event-related interfaces
│   ├── repositories.py               # Repository interfaces
│   └── llm.py                        # LLM interfaces
│
└── engine/                           # Module: Economic formulas (reused from V1)
    ├── models/                       # Pydantic data models
    │   ├── base_data.py              # ProvinceBaseData, NationalBaseData
    │   ├── metrics.py                # ProvinceTurnMetrics, NationalTurnMetrics
    │   ├── events.py                 # EventEffect (target path + add/multiply)
    │   └── state.py                  # GameState, TurnRecord
    ├── formulas.py                   # 13 pure economic functions
    └── calculator.py                 # resolve_turn() engine

data/
├── skills/                           # Universal skill templates (all agents share, v2.0 format)
│   ├── execute_command.md            # Execute imperial commands
│   ├── query_data.md                 # Query data within permissions
│   ├── chat.md                       # Chat with emperor (role-play)
│   ├── receive_message.md            # Receive inter-agent messages
│   ├── prepare_turn.md               # Prepare for turn end (send ready)
│   ├── summarize_turn.md             # Summarize turn results (write memory)
│   └── write_report.md               # Write reports to emperor
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
│       │   ├── summary.md            # Long-term memory
│       │   └── recent/               # Short-term memory (last 3 turns)
│       │       ├── turn_005.md
│       │       ├── turn_006.md
│       │       └── turn_007.md
│       └── workspace/                # Player-visible documents
│           ├── 005_report.md
│           ├── 006_exec_adjust_tax.md
│           └── 007_report.md
│
├── memory/                           # V3 Memory System: Event-based memory storage
│   ├── manifest.json                 # Global session index (metadata)
│   └── agents/                       # Per-agent session storage
│       └── {agent_id}/
│           └── sessions/
│               └── {session_id}/
│                   └── tape.jsonl    # Event log (JSONL format)
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
│   │   ├── test_skills/              # Skill module tests (73 tests, 100% passing)
│   │   ├── test_agent.py             # Agent lifecycle tests (44 tests)
│   │   └── test_manager.py
│   ├── test_memory/                  # V3 Memory module tests (24 tests, 92% coverage)
│   │   ├── test_models.py            # Data model tests
│   │   ├── test_tape_writer.py       # Event logging tests
│   │   ├── test_manifest_index.py    # Session management tests
│   │   ├── test_context_manager.py   # Sliding window tests
│   │   ├── test_query_parser.py      # Query parsing tests (mock LLM)
│   │   ├── test_tape_searcher.py     # Tape search tests
│   │   └── test_structured_retriever.py  # Retrieval coordinator tests
│   ├── test_cli/
│   ├── test_persistence/
│   └── test_llm/
├── integration/                      # Integration tests (multi-module)
│   └── test_memory/                  # V3 Memory integration tests (4 tests)
│       └── test_memory_integration.py  # End-to-end memory workflows
└── e2e/                              # End-to-end tests (full game flow)
```

### Module Dependencies

```
CLI
  ↓
EventBus ← (subscribe) ← Calculator
  ↓                      ↓
Agent  ───────────────→ Repository
  ↓                      ↓
LLM                   SQLite + filesystem
```

**Dependency Rules:**
- Upper layers can call lower layers
- Same-layer modules communicate via EventBus only
- Lower layers NEVER call upper layers
- No circular dependencies

### Core Modules

**EventBus** (`event_bus/`) — Event routing infrastructure. Routes events by src/dst matching, supports broadcast via `"*"`, fully async via `asyncio.create_task()`. Events logged to JSONL format. No business logic.

**Calculator** (`core/`) — Game state manager. Special EventBus subscriber that coordinates turn resolution (waits for all `ready` events), executes economic formulas (reused from V1 engine), modifies database exclusively. Publishes `turn_resolved` events.

**Agents** (`agents/`) — File-driven AI officials. Defined by markdown files, not Python classes. `soul.md` defines personality/behavior, `data_scope.yaml` defines data access (per-skill field whitelist).

**Skill System** (`agents/skills/`) — File-driven skill system (v2.0). Each skill is a markdown file with YAML Frontmatter (metadata: name, description, version, tags, priority, required_tools) and Markdown Body (task instructions, examples, constraints).

- **Three-tier caching**: Memory (LRU, size=50) → mtime (file change detection) → File system
- **Dynamic loading**: `_get_system_prompt_for_event()` loads skills on-demand based on event type
- **Event mapping**: Hardcoded registry (EventType.COMMAND → execute_command, etc.)
- **Variable injection**: Supports `{{agent_id}}`, `{{turn}}`, `{{timestamp}}` placeholders
- **Fallback mechanism**: Hardcoded instructions used when skill loading fails

Deception emerges from LLM reading soul.md. Three-phase workflow: summarize (write memory) → respond (answer queries) → execute (carry out commands). All phases triggered by events.

**V3 Memory System** (`memory/`) — Event-based memory retrieval and context management. Enables agents to remember and retrieve historical information across sessions.

### Core Components:

**TapeWriter** (`memory/tape_writer.py`) — Event logging to JSONL format.
- Writes events to `data/memory/agents/{agent_id}/sessions/{session_id}/tape.jsonl`
- Tracks event_id, timestamp, event_type, content, tokens, agent_id
- Token counting using tiktoken (GPT-4 encoding: cl100k_base)
- Async file operations via aiofiles

**ManifestIndex** (`memory/manifest_index.py`) — Session metadata management.
- Maintains `data/memory/manifest.json` with session summaries
- Tracks: start_time, end_time, turn_start/end, key_topics, summary, event_count
- Entity matching for candidate session selection (action: 0.4, target: 0.3, time: 0.2)
- Supports session registration, updates, and candidate retrieval

**ContextManager** (`memory/context_manager.py`) — Sliding window context management.
- Configurable token threshold (default: 8000 tokens, 95% trigger)
- Automatic summarization when threshold exceeded
- LLM-based summarization (2-3 sentences, 200 max tokens)
- Sliding window: keeps recent events (default: 20) after compaction
- Returns messages in LLM-friendly format (role: user/assistant)

**QueryParser** (`memory/query_parser.py`) — Natural language query parsing.
- LLM-based parsing with few-shot prompting
- Extracts: intent (query_history/query_status/query_data)
- Extracts: entities {action: [], target: [], time: ""}
- Determines: scope (current_session/cross_session), depth (overview/tape)
- Retry logic (3 attempts) with fallback to safe defaults

**TapeSearcher** (`memory/tape_searcher.py`) — Cross-session event search.
- Concurrent tape reading via asyncio.gather
- Entity matching scoring (action +0.4, target +0.3, time +0.2)
- Returns sorted events by relevance score
- Supports max_results limiting

**StructuredRetriever** (`memory/structured_retriever.py`) — Retrieval coordinator.
- Routes based on scope:
  - `current_session`: ContextManager.get_messages()
  - `cross_session`: ManifestIndex → TapeSearcher
- Routes based on depth:
  - `overview`: Returns session summaries only
  - `tape`: Returns full event details
- Coordinates all memory components

**MemoryTools** (`agents/tools/memory_tools.py`) — Agent integration.
- Implements `retrieve_memory(args, event) -> str` tool handler
- Follows QueryTools pattern (returns formatted string to LLM)
- Lazy initialization of memory components
- Formats retrieval results as markdown for LLM consumption

### Event Types in Tape:

```python
USER_QUERY      # Player commands/queries (from COMMAND/QUERY events)
TOOL_CALL       # Function invocations
TOOL_RESULT     # Function results
RESPONSE        # Final agent responses (sent to player and written to tape)
GAME_EVENT      # Game state changes (allocate_funds, adjust_tax, etc.)
```

### Query Flow Example:

```python
# Player asks: "我之前给直隶拨过款吗？"

# 1. Agent receives query event
# 2. TapeWriter writes USER_QUERY event
# 3. LLM calls retrieve_memory tool
# 4. QueryParser parses query:
#    - intent: query_history
#    - entities: {action: ["拨款"], target: ["直隶"], time: "history"}
#    - scope: cross_session
#    - depth: tape
# 5. StructuredRetriever routes to cross_session:
#    a. ManifestIndex.get_candidate_sessions() → finds matching sessions
#    b. TapeSearcher.search() → searches tape.jsonl files
#    c. Returns formatted events with relevance scores
# 6. MemoryTools formats results as markdown
# 7. LLM receives context and responds
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
    entity_match_weights:
      action: 0.4
      target: 0.3
      time: 0.2
  memory_dir: "data/memory"
```

### Design Principles:

| Principle | Implementation |
|-----------|----------------|
| **Event Sourcing** | All events logged to tape.jsonl (immutable append-only) |
| **Session Isolation** | Each session has separate tape file |
| **Metadata Indexing** | manifest.json provides fast session lookup |
| **Sliding Window** | ContextManager keeps token count under threshold |
| **Natural Language** | QueryParser uses LLM for flexible query understanding |
| **Lazy Loading** | Memory components initialized on-demand (session_id required) |
| **Backward Compatible** | V2 memory_manager.py still works, V3 is additive |

### Integration Points:

**Agent initialization** (`agents/agent.py`):
```python
# Lazy initialization in _ensure_memory_components()
self._tape_writer = TapeWriter(memory_dir)
self._manifest_index = ManifestIndex(memory_dir)
self._context_manager = None  # Initialized when session_id available
self._memory_tools = None  # Initialized when session_id available
```

**Tool registration** (`agents/agent.py`):
```python
self._function_handlers["retrieve_memory"] = self._retrieve_memory_wrapper
```

**TapeWriter hooks** (`agents/agent.py`):
```python
# In _on_event(), for COMMAND/QUERY events:
await self._tape_writer.write_event(
    session_id=event.session_id,
    agent_id=self.agent_id,
    event_type="USER_QUERY",
    content={"query": event.payload.get("query", "")},
    tokens=self._count_tokens(event)
)
```

**CLI** (`cli/`) — Player interface. Rich/textual-based TUI. Natural language commands parsed by LLM. Sends events to EventBus, subscribes to `player` ID for responses. Modes: command mode (single commands), chat mode (conversational).

**Persistence** (`persistence/`) — Data access layer. Async SQLite via aiosqlite, repository pattern. Tables: game_state, turn_metrics, agent_state, event_log. Shared by all modules for reads, exclusive writes by Calculator.

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
- Calculator: `"system:calculator"`
- Broadcast: `"*"`

**Event Types:**
- `command` — Player → Agent (execute command)
- `query` — Player → Agent (query information)
- `chat` — Player → Agent (enter conversation)
- `response` — Agent → Player (narrative response)
- `agent_message` — Agent → Agent (inter-agent communication)
- `adjust_tax` / `build_irrigation` / `recruit_troops` — Agent → Calculator (game actions)
- `ready` — Agent → Calculator (turn preparation complete)
- `turn_resolved` — Calculator → * (turn calculation complete)
- `end_turn` — Player → * (advance to next turn)

### Turn Resolution Flow

```
1. Player → {"type": "end_turn", "dst": ["*"]}

2. All Agents receive "end_turn"
   ├─ Agent A → {"type": "ready", "dst": ["system:calculator"]}
   ├─ Agent B → {"type": "ready", "dst": ["system:calculator"]}
   └─ Agent C → {"type": "ready", "dst": ["system:calculator"]}

3. Calculator receives all "ready" → resolve_turn()
   - Load current state
   - Run 13 economic formulas
   - Save new state
   - Save turn metrics

4. Calculator → {"type": "turn_resolved", "dst": ["*"], "payload": {"turn": 5}}

5. All Agents receive "turn_resolved" → write summary to memory/
```

**Synchronization:** Calculator manages `pending_ready` set with 5s timeout. Missing agents trigger warning but don't block turn resolution.

### Key Patterns

- **Pydantic v2** models with `Decimal` precision for all game data
- **Event sourcing:** All state changes logged as events (JSONL format)
- **File-driven agents:** Personality/permissions defined by markdown/YAML, not code
- **V2 Memory:** Dual-layer — long-term (summary.md, agent-maintained) + short-term (recent/, 3-turn sliding window)
- **V3 Memory:** Event-based retrieval with tape.jsonl logs + manifest.json index
- **Context Management:** Sliding window with automatic summarization (Tiktoken token counting)
- **Natural Language Queries:** LLM-based query parsing with entity extraction
- **Cross-Session Retrieval:** Manifest-based candidate selection + tape-based search
- **LLM emergence:** Deception/slacking emerges from soul.md personality, no hardcoded numbers
- **Repository pattern:** All data access through Repository interface
- **Async everywhere:** asyncio, aiosqlite, aiofiles
- **Deterministic engine:** Random functions accept seeded `random.Random` for reproducibility

### Data Models

**Province Hierarchy:**
```
ProvinceBaseData
├── province_id, name
├── population: PopulationData (total, happiness, growth_rate)
├── agriculture: AgricultureData (crops[], irrigation_level)
├── commerce: CommerceData (merchant_households, market_prosperity)
├── trade: TradeData (trade_volume, trade_route_quality)
├── military: MilitaryData (soldiers, morale, upkeep_per_soldier)
├── taxation: TaxationData (land_tax_rate, commercial_tax_rate, tariff_rate)
├── consumption: ConsumptionData (civilian_grain_per_capita, military_grain_per_soldier)
├── administration: AdministrationData (official_count, official_salary, infrastructure_value)
└── granary_stock, local_treasury
```

**National Aggregation:**
```
NationalBaseData
├── turn (current turn number)
├── provinces: list[ProvinceBaseData]
├── imperial_treasury
├── national_tax_modifier
└── tribute_rate
```

**Turn Metrics (not stored in base data):**
```
NationalTurnMetrics
├── total_food_production
├── total_food_consumption
├── total_tax_revenue
├── total_expenditure
├── net_treasury_change
├── total_population_change
└── ... (13 formula outputs)
```

### Import Rules

```python
# ✅ Correct: upper imports lower
from simu_emperor.event_bus.core import EventBus
from simu_emperor.core.calculator import Calculator
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

**V3 Memory System:**
- `.design/V3_MEMORY_SYSTEM_SPEC.md` — Memory system specification (query parsing, retrieval, context management)

**V1 Architecture (deprecated, reference for engine reuse):**
- `.plan/rewrite_plan_v1.1.md` — Full system architecture
- `.plan/eco_system_design.md` — Economic system formulas + data model
- `.plan/agent_design_v1.1.md` — Agent module design
- `.review/` — Design reviews

## Development Workflow

V2 implementation follows the phases defined in `.prd/V2_PRD.md` (§8.1):

**Phase 1: EventBus** — Event routing, async handling, logging ✅
**Phase 2: Calculator** — Reuse V1 engine, turn coordination, persistence ✅
**Phase 3: Agents** — File-driven agents, LLM integration, memory ✅
**Phase 4: CLI** — Rich TUI, natural language parsing (TODO)
**Phase 5: Integration** — E2E testing, performance optimization (TODO)

**Skill System (Completed 2026-03-03):**
- ✅ Week 1: Infrastructure (models, parser, validator, loader, registry)
- ✅ Week 1.5-2: Agent integration (dynamic skill loading, variable injection)
- ✅ Week 2: Skill file migration (7 files rewritten to v2.0 format)
- ✅ 73 unit tests (100% passing)
- ✅ Code review and Important issues fixed

**V3 Memory System (Completed 2026-03-04):**
- ✅ Week 1: Infrastructure (models, exceptions, tape_writer, manifest_index)
- ✅ Week 1.5: Context management (ContextManager with sliding window)
- ✅ Week 2: Query and retrieval (QueryParser, TapeSearcher, StructuredRetriever)
- ✅ Week 2.5: Agent integration (MemoryTools, TapeWriter hooks, token counting)
- ✅ 28 tests (24 unit + 4 integration, 100% passing, 92% coverage)
- ✅ tiktoken dependency added
- ✅ `retrieve_memory` tool registered in function handlers

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

| Aspect | V1 (Phase-Driven) | V2 (Event-Driven) |
|--------|-------------------|-------------------|
| **Communication** | Direct function calls | EventBus (async) |
| **Game Loop** | GameLoop enforces phases | Calculator coordinates turns |
| **Phases** | RESOLUTION → SUMMARY → INTERACTION → EXECUTION | None (event-triggered) |
| **Player UI** | FastAPI + Vue.js | Rich CLI |
| **Agent Initiation** | None (passive) | None (passive) |
| **State Writes** | GameLoop → Repository | Calculator only |
| **Concurrency** | Phase-locked, agents parallel within phase | Fully async, event-driven |
| **Event Logging** | Database tables | JSONL files |

**Preserved from V1:**
- Economic formulas (engine/)
- Data models (ProvinceBaseData, NationalBaseData)
- Agent file-driven design (soul.md, data_scope.yaml)
- V2 Memory: summary.md + recent/ (agent-maintained)
- Deception via LLM emergence

**Added in V3:**
- V3 Memory: tape.jsonl event logs + manifest.json index
- Natural language query parsing (LLM-based)
- Cross-session memory retrieval
- Sliding window context management with automatic summarization
- Token counting (tiktoken) for accurate context tracking
