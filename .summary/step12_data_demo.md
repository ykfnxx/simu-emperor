# Step 12: 数据 + 打磨 — 初始省份配置 + 演示脚本

## 完成内容

### 1. 新增文件：`data/initial_provinces.json`

从 `.plan/eco_system_design.md` 第 6 节（直隶初始数据）提取的均衡初始配置。

| 字段 | 值 | 说明 |
|---|---|---|
| `imperial_treasury` | 500000 | 国库初始银两 |
| `national_tax_modifier` | 1.0 | 全国税率修正 |
| `tribute_rate` | 0.30 | 省份上缴比例 |
| `provinces[0].province_id` | zhili | 直隶省 |
| `provinces[0].population.total` | 2600000 | 260 万人口 |
| `provinces[0].population.growth_rate` | 0.002 | 0.2%/年增长 |
| `provinces[0].population.happiness` | 0.70 | 中等偏上幸福度 |
| `provinces[0].agriculture.crops` | wheat 550万亩 + millet 250万亩 | 两种主粮 |
| `provinces[0].agriculture.irrigation_level` | 0.60 | 灌溉水平 |
| `provinces[0].military.garrison_size` | 30000 | 驻军 3 万 |
| `provinces[0].granary_stock` | 1200000 | 粮仓 120 万石 |
| `provinces[0].local_treasury` | 80000 | 库银 8 万两 |

根据 eco_system_design 分析，此配置下：
- 粮食盈余率 ≈ 4.6%
- 财政盈余率 ≈ 6.3%
- 人口增长率 ≈ 0.28%/年

### 2. 修改文件：`src/simu_emperor/player/web/app.py`

新增 `load_initial_data(data_dir: Path) -> NationalBaseData` 函数，从 JSON 加载初始数据替换硬编码。

**之前**：`_make_initial_data()` 内部硬编码所有省份数据

**之后**：`load_initial_data(Path("data"))` 读取 `data/initial_provinces.json`

### 3. 新增文件：`scripts/run_demo.py`

无 LLM 演示脚本，使用 MockProvider 运行完整游戏流程。

```bash
uv run python scripts/run_demo.py
```

**流程**：
1. 初始化游戏（临时 DB + GameLoop + Agent 文件系统）
2. 运行 3 个完整回合（RESOLUTION → SUMMARY → INTERACTION → EXECUTION）
3. INTERACTION 阶段模拟玩家对话和命令提交
4. 输出每回合的关键数据变化（国库、人口、粮仓、库银）

**输出示例**：
```
============================================================
  第 1 回合
============================================================

[RESOLUTION] 回合结算...
回合: 1 | 阶段: summary
国库: 504674 两
  直隶: 人口 2607280 | 粮仓 1566000 | 库银 90906

[SUMMARY] Agent 汇总报告...
  governor_zhili: [MockProvider] agent=governor_zhili...
  minister_of_revenue: [MockProvider] agent=minister_of_revenue...

[INTERACTION] 玩家交互...
  玩家 → governor_zhili: 今年收成如何？
  governor_zhili → 玩家: [MockProvider]...
  提交命令: build_granary → zhili

[EXECUTION] 执行命令...
  事件: [MockProvider] 默认执行报告...
```

### 4. 新增文件：`scripts/seed_game.py`

游戏初始化脚本，创建新游戏存档。

```bash
uv run python scripts/seed_game.py [--db PATH] [--data-dir DIR] [--seed N]
```

**参数**：
- `--db`：数据库路径（默认 `game.db`）
- `--data-dir`：数据根目录（默认 `data`）
- `--seed`：随机种子（可选）

**功能**：
1. 从 `initial_provinces.json` 加载初始数据
2. 初始化 SQLite 数据库
3. 创建 `GameState` 并保存到 `game_saves` 表
4. 初始化 Agent 文件系统（从 `default_agents/` 拷贝到 `agent/`）

### 5. 数据文件状态

| 文件 | 状态 | 说明 |
|---|---|---|
| `data/initial_provinces.json` | **新建** | 直隶省均衡初始配置 |
| `data/event_templates.json` | 已存在 | 10 个随机事件模板（完整） |
| `data/default_agents/governor_zhili/` | 已存在 | 直隶巡抚李卫 |
| `data/default_agents/minister_of_revenue/` | 已存在 | 户部尚书张廷玉 |
| `data/skills/query_data.md` | 已存在 | 查阅数据技能 |
| `data/skills/write_report.md` | 已存在 | 撰写报告技能 |
| `data/skills/execute_command.md` | 已存在 | 执行命令技能 |

## 文件清单

| 文件 | 操作 |
|---|---|
| `data/initial_provinces.json` | 新建 |
| `src/simu_emperor/player/web/app.py` | 修改（新增 `load_initial_data` 函数） |
| `scripts/run_demo.py` | 新建 |
| `scripts/seed_game.py` | 新建 |

## 设计决策

1. **JSON 字符串数值** — `initial_provinces.json` 中的 Decimal 字段使用字符串（如 `"500000"`），Pydantic v2 自动解析为 Decimal，避免浮点精度问题
2. **数据加载器可复用** — `load_initial_data()` 导出为模块级函数，供 `run_demo.py` 和 `seed_game.py` 共用
3. **演示脚本使用临时目录** — `run_demo.py` 使用 `tempfile.TemporaryDirectory()` 创建临时 DB，运行完自动清理，不污染工作目录
4. **seed_game 保存初始状态** — 初始化后立即调用 `save_game()`，确保存档表有初始记录

## 验证结果

```bash
# 演示脚本
uv run python scripts/run_demo.py
# 输出 3 个回合的完整流程，数据变化正常

# 初始化脚本
uv run python scripts/seed_game.py --db /tmp/test_seed.db
# 游戏已保存到数据库

# 全部测试
uv run pytest tests/ -q
# 343 passed in 0.80s

# Lint + 格式检查
uv run ruff check src/simu_emperor/player/web/app.py scripts/
uv run ruff format --check src/simu_emperor/player/web/app.py scripts/
# All checks passed! 3 files already formatted
```
