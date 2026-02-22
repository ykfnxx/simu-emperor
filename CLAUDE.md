# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/                    # All tests
uv run pytest tests/unit/               # Unit tests only
uv run pytest tests/unit/engine/        # Single test directory
uv run pytest tests/unit/engine/test_formulas.py  # Single file
uv run pytest tests/unit/engine/test_formulas.py::test_name -v  # Single test

# Lint and format
uv run ruff check .
uv run ruff format .

# Run web UI
uv run simu-emperor
```

## Architecture

Turn-based emperor simulation game. The player is the emperor; AI agents play officials who may lie in reports and slack off when executing commands.

### Directory Structure

```
src/simu_emperor/
├── __init__.py
├── config.py                          # pydantic-settings 全局配置
├── game.py                            # 游戏循环编排器（阶段推进）
├── engine/                            # 模块一：计算逻辑（纯函数，无 I/O）
│   ├── models/
│   │   ├── base_data.py               # 基础数据：Population/Agriculture/Commerce/Trade/Military/Consumption/Administration/Taxation/Province/NationalBaseData
│   │   ├── metrics.py                 # 回合计算指标：ProvinceTurnMetrics, NationalTurnMetrics
│   │   ├── events.py                  # 事件层级：PlayerEvent/AgentEvent/RandomEvent（discriminated union）
│   │   ├── state.py                   # GameState, TurnRecord
│   │   ├── effects.py                 # EventEffect（target 字段路径 + add/multiply 操作）
│   │   └── event_templates.py         # 随机事件模板池定义
│   ├── calculator.py                  # resolve_turn()：应用事件效果→计算指标→回写反馈→约束校验
│   ├── formulas.py                    # 经济公式（13个纯函数）：粮食生产/需求/田赋/商税/关税/军费/幸福度/人口/士气/商业/财政
│   └── event_generator.py            # 随机事件生成（接受 seeded Random）
├── agents/                            # 模块二：文件驱动 AI 官员系统
│   ├── models/
│   │   └── roles.py                   # 角色枚举（系统层面标识 agent 类型）
│   ├── runtime.py                     # AgentRuntime：三阶段生命周期（summarize/respond/execute）
│   ├── file_manager.py                # 读写 agent 目录的文件操作
│   ├── context_builder.py             # 组装 LLM 调用上下文（含 data_scope 解析和数据提取）
│   ├── memory_manager.py              # 记忆管理：短期写入/清理（保留 3 回合）+ 长期读取
│   ├── agent_manager.py               # 动态管理：初始化/增删/存档/恢复
│   └── llm/
│       ├── providers.py               # LLMProvider 抽象 + 实现（Anthropic/OpenAI/Mock）
│       └── client.py                  # LLM 调用封装
├── player/                            # 模块三：玩家交互
│   ├── schemas.py                     # API 请求/响应 schema
│   └── web/
│       ├── app.py                     # FastAPI 应用工厂 + main() 入口
│       ├── routes/
│       │   ├── game.py                # /api/state, /api/turn/advance, /api/history
│       │   ├── agents.py              # /api/agents/{id}/chat
│       │   └── reports.py             # /api/reports, /api/provinces
│       ├── templates/                 # Jinja2 模板
│       └── static/                    # CSS/JS
└── persistence/                       # 持久化层
    ├── database.py                    # SQLite 连接与 schema 初始化（aiosqlite）
    ├── repositories.py                # Repository 模式 CRUD
    └── serialization.py               # GameState ↔ DB 序列化

data/
├── skills/                            # 通用 skill 模板（所有 Agent 共享）
│   ├── query_data.md
│   ├── write_report.md
│   └── execute_command.md
├── default_agents/                    # Agent 模板（随代码版本管理）
│   └── {agent_id}/
│       ├── soul.md                    # 角色定义
│       └── data_scope.yaml            # 数据权限声明（per-skill 白名单）
├── initial_provinces.json             # 初始省份配置
└── event_templates.json               # 随机事件模板池

data/agent/                            # Agent 活跃工作区（运行时生成）
└── {agent_id}/
    ├── soul.md
    ├── data_scope.yaml
    ├── memory/
    │   ├── summary.md                 # 长期记忆
    │   └── recent/                    # 短期记忆（保留最近 3 回合）
    └── workspace/                     # 玩家可见的文档归档

tests/
├── conftest.py                        # 共享 fixtures + 工厂函数
├── unit/{engine,agents,persistence}/  # 单元测试（无 I/O、无 LLM）
├── integration/                       # 集成测试（多模块协作）
└── e2e/                               # 端到端测试（FastAPI TestClient）
```

### Three Modules

**Engine** (`engine/`) — Pure computation, no I/O. Province-level economic simulation with population, agriculture, commerce, trade, military, consumption, administration, taxation subsystems. Turn resolution: apply EventEffects → run 13 economic formulas → write back feedback (population/happiness/morale/commerce changes) → clamp bounded values. All formulas are pure functions in `formulas.py`; per-turn derived values stored in `ProvinceTurnMetrics`/`NationalTurnMetrics` (not in base data).

**Agents** (`agents/`) — File-driven AI officials. Each agent is defined by markdown files (`soul.md` for personality, `data_scope.yaml` for data access permissions, `memory/` for context), not Python classes. Shared skill templates live in `data/skills/`, per-agent data permissions in `data_scope.yaml`. Deception emerges from LLM reading soul.md personality descriptions. Templates live in `data/default_agents/`, active state in `data/agent/`. Three-phase lifecycle per turn: summarize (produce report) → interact (answer player questions) → execute (carry out commands, possibly poorly).

**Player** (`player/`) — FastAPI web UI. Routes in `web/routes/` for game state, agent chat, reports, commands. Phase-locked: API rejects operations invalid for the current game phase.

### Supporting Layers

- **Persistence** (`persistence/`) — async SQLite via aiosqlite, repository pattern. Tables: game_saves, event_log, agent_reports, chat_history, player_commands.
- **Game Loop** (`game.py`) — Orchestrator enforcing phase order: RESOLUTION → SUMMARY → INTERACTION → EXECUTION → repeat.
- **Config** (`config.py`) — pydantic-settings.

### Key Patterns

- Pydantic v2 models with `Decimal` precision and field constraints for all game data
- Discriminated union for events: `GameEvent = PlayerEvent | AgentEvent | RandomEvent` (discriminator: `source`)
- Province data hierarchy: `ProvinceBaseData` contains `PopulationData`, `AgricultureData`, `CommerceData`, `TradeData`, `MilitaryData`, `TaxationData`, `ConsumptionData`, `AdministrationData` plus `granary_stock`/`local_treasury`
- `NationalBaseData` aggregates all provinces plus `imperial_treasury`, `national_tax_modifier`, and `tribute_rate`
- Turn metrics separation: `ProvinceTurnMetrics`/`NationalTurnMetrics` hold per-turn derived values (food production, tax revenue, expenditure, population change etc.), computed by formulas but not stored in base data
- `resolve_turn()` returns `tuple[NationalBaseData, NationalTurnMetrics]`
- Agent execution uses single structured output (ExecutionResult: narrative + effects + fidelity)
- Engine is deterministic: random functions take seeded `random.Random` for reproducibility

### Planning Docs

Architecture specs are in `.plan/rewrite_plan_v1.1.md` (full system), `.plan/eco_system_design.md` (economic system formulas and data model), and `.plan/agent_design_v1.1.md` (agent module detail). Original proposals in `.proposal/`. Design reviews in `.review/`.

## Development Workflow

Implementation follows the step-by-step plan defined in `.plan/rewrite_plan_v1.1.md` (实施顺序 section). After completing each step, write a summary to `.summary/stepNN_<name>.md` documenting what was implemented, key decisions made, and verification results. Existing summaries serve as context for subsequent steps — read them before continuing work.
