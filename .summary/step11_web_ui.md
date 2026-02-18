# Step 11: Web UI — FastAPI 路由 + 模板 + schemas + e2e 测试

## 完成内容

### 1. 新增文件：`player/schemas.py`

API 请求/响应 Pydantic 模型，共 9 个 schema。

| 类型 | Schema | 用途 |
|---|---|---|
| 请求 | `ChatRequest` | Agent 对话（message 字段） |
| 请求 | `CommandRequest` | 玩家命令（command_type/description/target_province_id/parameters/direct） |
| 请求 | `AdvanceRequest` | 阶段推进（空 body） |
| 响应 | `StateResponse` | 游戏状态摘要（game_id/turn/phase/provinces/treasury/events_count） |
| 响应 | `ChatResponse` | 对话回复（agent_id/response） |
| 响应 | `ReportResponse` | Agent 报告（agent_id/turn/markdown） |
| 响应 | `AdvanceResponse` | 阶段推进结果（phase/turn/message + 可选 reports/events） |
| 响应 | `CommandResponse` | 命令确认（status/command_type/direct） |
| 响应 | `ErrorResponse` | 错误信息（error/detail） |

### 2. 新增文件：`player/web/app.py`（应用工厂）

#### `create_app(game_loop=None)` 工厂函数

- 接受可选 `GameLoop` 参数实现依赖注入（测试用），不传则使用 `lifespan` 自动初始化
- GameLoop 存储在 `app.state.game_loop`，路由通过 `request.app.state.game_loop` 获取
- 注册 `PhaseError` → 400 + `ErrorResponse` 异常处理器
- 注册通用 `Exception` → 500 异常处理器
- 挂载 Jinja2 模板 + 静态文件
- 首页路由 `GET /` 渲染 `index.html`

#### `lifespan()` 生命周期管理

初始化流程：`GameConfig` → `init_database` → `MockProvider` → `GameState` → `GameLoop` → `initialize_agents`

#### `main()` CLI 入口

`uvicorn.run` 以 factory 模式启动，对应 `pyproject.toml` 中的 `simu-emperor` 入口点。

### 3. 路由文件（3 个）

**`player/web/routes/game.py`**：

| 路由 | 方法 | 响应 | 说明 |
|---|---|---|---|
| `/api/state` | GET | `StateResponse` | 游戏状态摘要（省份 id/name/population/treasury） |
| `/api/turn/advance` | POST | `AdvanceResponse` | 自动推进到下一阶段 |
| `/api/history` | GET | `list[dict]` | 历史回合记录（turn/events_count/has_metrics） |
| `/api/debug/real-data` | GET | `dict` | 完整 NationalBaseData JSON |

advance 逻辑根据当前 phase 自动选择：
- RESOLUTION → `advance_to_resolution()` → SUMMARY
- SUMMARY → `advance_to_summary()` → INTERACTION（返回 reports）
- INTERACTION → `advance_to_execution()` → EXECUTION（返回 events）
- EXECUTION → `advance_to_resolution()` → SUMMARY（下一回合）

**`player/web/routes/agents.py`**：

| 路由 | 方法 | 响应 | 说明 |
|---|---|---|---|
| `/api/agents` | GET | `list[str]` | 活跃 Agent 列表 |
| `/api/agents/{agent_id}/chat` | POST | `ChatResponse` | 发送消息（INTERACTION 阶段） |
| `/api/agents/{agent_id}/chat` | GET | `list[dict]` | 对话历史 |

**`player/web/routes/reports.py`**：

| 路由 | 方法 | 响应 | 说明 |
|---|---|---|---|
| `/api/reports` | GET | `list[ReportResponse]` | 当前回合 Agent 报告 |
| `/api/provinces` | GET | `list[dict]` | 省份概览（含 happiness/granary/garrison） |
| `/api/commands` | POST | `CommandResponse` | 提交命令（构造 PlayerEvent → submit_command） |
| `/api/commands` | GET | `list[dict]` | 当前回合已提交命令 |

### 4. Jinja2 模板 + 静态文件

**`player/web/templates/index.html`**：
- 单页应用骨架：状态栏（回合/阶段/国库）、推进按钮、省份概览、Agent 报告、对话框、命令表单

**`player/web/static/style.css`**：
- 暗色主题（#1a1a2e 底色 + #c9a227 金色强调），CSS Grid 两列布局

**`player/web/static/app.js`**：
- fetch API 驱动：`refreshState()`, `advanceTurn()`, `loadAgents()`, `sendChat()`, `submitCommand()`, `loadReports()`, `loadCommands()`

### 5. e2e 测试：`tests/e2e/test_web_api.py`

使用 `httpx.AsyncClient` + `ASGITransport` + `MockProvider` + 临时 SQLite。

| 测试类 | 测试数 | 覆盖内容 |
|---|---|---|
| `TestStateQuery` | 1 | GET /api/state 结构正确性 |
| `TestPhaseAdvance` | 4 | RESOLUTION→SUMMARY、SUMMARY→INTERACTION、INTERACTION→EXECUTION、完整四阶段循环 |
| `TestAgentChat` | 2 | INTERACTION 阶段对话成功、错误阶段返回 400 |
| `TestReports` | 1 | SUMMARY 后报告查询 |
| `TestCommands` | 2 | INTERACTION 阶段命令提交成功、错误阶段返回 400 |
| `TestHistory` | 2 | 初始为空、advance 后有记录 |
| `TestDebug` | 1 | 完整数据返回 |
| `TestProvinces` | 1 | 省份概览字段完整性 |
| `TestAgentList` | 1 | Agent 列表非空 |

共计 15 个 e2e 测试。

## 文件清单

| 文件 | 操作 |
|---|---|
| `src/simu_emperor/player/schemas.py` | 新建 |
| `src/simu_emperor/player/web/app.py` | 新建 |
| `src/simu_emperor/player/web/routes/game.py` | 新建 |
| `src/simu_emperor/player/web/routes/agents.py` | 新建 |
| `src/simu_emperor/player/web/routes/reports.py` | 新建 |
| `src/simu_emperor/player/web/templates/index.html` | 新建 |
| `src/simu_emperor/player/web/static/style.css` | 新建 |
| `src/simu_emperor/player/web/static/app.js` | 新建 |
| `tests/e2e/__init__.py` | 新建 |
| `tests/e2e/test_web_api.py` | 新建 |

## 设计决策

1. **GameLoop 依赖注入** — `create_app(game_loop=...)` 接受预构建的 GameLoop 实例，跳过 lifespan 自动初始化，使 e2e 测试可以完全控制 GameLoop 的创建（临时 DB、MockProvider、自定义 seed）
2. **Phase 自动推进** — `POST /api/turn/advance` 检查当前 phase 并自动调用对应 GameLoop 方法，前端只需反复调用同一个接口即可驱动整个游戏循环
3. **PhaseError 透传** — GameLoop 的阶段校验异常直接通过 FastAPI 异常处理器转为 400 响应，路由层无需重复校验
4. **测试使用 ASGITransport** — `httpx.AsyncClient` + `ASGITransport(app=app)` 模式无需启动服务器进程，测试速度快（15 个测试 < 1.3s）
5. **静态文件容错** — `_STATIC_DIR.exists()` 检查后才挂载 StaticFiles，避免测试环境中路径不存在导致启动失败

## 验证结果

```bash
# e2e 测试
uv run pytest tests/e2e/test_web_api.py -v
# 15 passed in 1.27s

# 全部测试（unit + integration + e2e）
uv run pytest tests/ -v
# 343 passed in 0.73s

# Lint + 格式检查
uv run ruff check src/simu_emperor/player/ tests/e2e/
uv run ruff format --check src/simu_emperor/player/ tests/e2e/
# All checks passed! 10 files already formatted
```
