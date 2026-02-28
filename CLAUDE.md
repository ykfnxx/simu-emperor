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

**V2: Event-Driven Multi-Agent Architecture**

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
│   ├── context_builder.py            # LLM context assembly (data_scope parsing)
│   ├── memory_manager.py             # Memory: short-term (3 turns) + long-term
│   ├── file_manager.py               # File I/O for agent files
│   └── response_parser.py            # Parse LLM structured output
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
├── skills/                           # Universal skill templates (all agents share)
│   ├── query_data.md
│   ├── write_report.md
│   └── execute_command.md
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
│       ├── memory/
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
├── logs/                             # Log directory
│   ├── events/                       # JSONL event logs
│   │   ├── events_20260226.jsonl
│   │   └── events_20260227.jsonl
│   ├── errors/                       # Error logs
│   └── debug/                        # Debug logs
│
└── saves/                            # Save games
    └── game-001/
        ├── turn_005/
        └── turn_010/

tests/
├── conftest.py                       # Shared fixtures + factories
├── unit/                             # Unit tests (no I/O, no LLM)
│   ├── test_event_bus/
│   ├── test_core/
│   ├── test_agents/
│   ├── test_cli/
│   ├── test_persistence/
│   └── test_llm/
├── integration/                      # Integration tests (multi-module)
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

**Agents** (`agents/`) — File-driven AI officials. Defined by markdown files, not Python classes. `soul.md` defines personality/behavior, `data_scope.yaml` defines data access (per-skill field whitelist). Deception emerges from LLM reading soul.md. Universal skill templates in `data/skills/`. Three-phase workflow: summarize (write memory) → respond (answer queries) → execute (carry out commands). All phases triggered by events.

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
- **Memory management:** Dual-layer — long-term (summary.md, agent-maintained) + short-term (recent/, 3-turn sliding window)
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

**V1 Architecture (deprecated, reference for engine reuse):**
- `.plan/rewrite_plan_v1.1.md` — Full system architecture
- `.plan/eco_system_design.md` — Economic system formulas + data model
- `.plan/agent_design_v1.1.md` — Agent module design
- `.review/` — Design reviews

## Development Workflow

V2 implementation follows the phases defined in `.prd/V2_PRD.md` (§8.1):

**Phase 1: EventBus** — Event routing, async handling, logging
**Phase 2: Calculator** — Reuse V1 engine, turn coordination, persistence
**Phase 3: Agents** — File-driven agents, LLM integration, memory
**Phase 4: CLI** — Rich TUI, natural language parsing
**Phase 5: Integration** — E2E testing, performance optimization

When implementing features:
1. Read the relevant design docs (`.prd/V2_PRD.md`, `.design/V2_TDD.md`)
2. Check existing tests for patterns
3. Write unit tests before implementation
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
- Memory management (summary.md + recent/)
- Deception via LLM emergence
