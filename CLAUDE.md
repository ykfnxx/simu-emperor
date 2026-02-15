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
│   │   ├── base_data.py               # 基础数据：Population/Agriculture/Commerce/Trade/Military/Province/NationalBaseData
│   │   ├── events.py                  # 事件层级：PlayerEvent/AgentEvent/RandomEvent（discriminated union）
│   │   ├── state.py                   # GameState, TurnRecord
│   │   └── effects.py                 # EventEffect（target 字段路径 + add/multiply 操作）
│   ├── calculator.py                  # resolve_turn()：收集效果→分组→应用→公式计算→约束校验
│   ├── formulas.py                    # 经济公式：粮食产量/税收/贸易收入/军事开支/人口变化
│   └── event_generator.py            # 随机事件生成（接受 seeded Random）
├── agents/                            # 模块二：文件驱动 AI 官员系统
│   ├── models/
│   │   └── roles.py                   # 角色枚举（系统层面标识 agent 类型）
│   ├── runtime.py                     # AgentRuntime：三阶段生命周期（summarize/respond/execute）
│   ├── file_manager.py                # 读写 agent 目录的文件操作
│   ├── context_builder.py             # 组装 LLM 调用上下文（soul + skills + memory + data）
│   ├── data_accessor.py               # 解析 skill 中数据范围声明，从 NationalBaseData 提取子集
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
├── default_agents/                    # Agent 模板（随代码版本管理）
│   └── {agent_name}/
│       ├── soul.md                    # 角色定义（身份/性格/行为倾向/说话风格）
│       └── skills/                    # 能力定义（可访问数据范围）
├── initial_provinces.json             # 初始省份配置
└── event_templates.json               # 随机事件模板池

data/agent/                            # Agent 活跃工作区（运行时生成，存档时备份）
└── {agent_name}/
    ├── soul.md                        # 从模板拷贝，可被游戏修改
    ├── skills/
    ├── memory/
    │   ├── summary.md                 # 长期记忆（Agent/LLM 自行维护）
    │   └── recent/                    # 短期记忆（固定保留最近 3 回合）
    └── workspace/                     # 工作文档（奏折、报告等产出物）

tests/
├── conftest.py                        # 共享 fixtures + 工厂函数
├── unit/{engine,agents,persistence}/  # 单元测试（无 I/O、无 LLM）
├── integration/                       # 集成测试（多模块协作）
└── e2e/                               # 端到端测试（FastAPI TestClient）
```

### Three Modules

**Engine** (`engine/`) — Pure computation, no I/O. Province-level economic simulation with population, agriculture, commerce, trade, military subsystems. Turn resolution applies EventEffects (add/multiply operations) to NationalBaseData. All economic formulas are pure functions in `formulas.py`.

**Agents** (`agents/`) — File-driven AI officials. Each agent is defined by markdown files (`soul.md` for personality, `skills/` for data access ranges, `memory/` for context), not Python classes. Deception emerges from LLM reading soul.md personality descriptions. Templates live in `data/default_agents/`, active state in `data/agent/`. Three-phase lifecycle per turn: summarize (produce report) → interact (answer player questions) → execute (carry out commands, possibly poorly).

**Player** (`player/`) — FastAPI web UI. Routes in `web/routes/` for game state, agent chat, reports, commands. Phase-locked: API rejects operations invalid for the current game phase.

### Supporting Layers

- **Persistence** (`persistence/`) — async SQLite via aiosqlite, repository pattern. Tables: game_saves, event_log, agent_reports, chat_history, player_commands.
- **Game Loop** (`game.py`) — Orchestrator enforcing phase order: RESOLUTION → SUMMARY → INTERACTION → EXECUTION → repeat.
- **Config** (`config.py`) — pydantic-settings.

### Key Patterns

- Pydantic v2 models with `Decimal` precision and field constraints for all game data
- Discriminated union for events: `GameEvent = PlayerEvent | AgentEvent | RandomEvent` (discriminator: `source`)
- Province data hierarchy: `ProvinceBaseData` contains `PopulationData`, `AgricultureData`, `CommerceData`, `TradeData`, `MilitaryData` plus `granary_stock`/`local_treasury`
- `NationalBaseData` aggregates all provinces plus `imperial_treasury` and `national_tax_modifier`
- Agent execution output (free markdown) is converted to structured `AgentEvent` via a second LLM call
- Engine is deterministic: random functions take seeded `random.Random` for reproducibility

### Planning Docs

Architecture specs are in `.plan/rewrite_plan.md` (full system) and `.plan/agent_design.md` (agent module detail). Original proposals in `.proposal/`.

## Development Workflow

Implementation follows the step-by-step plan defined in `.plan/rewrite_plan.md` (实施顺序 section). After completing each step, write a summary to `.summary/stepNN_<name>.md` documenting what was implemented, key decisions made, and verification results. Existing summaries serve as context for subsequent steps — read them before continuing work.
