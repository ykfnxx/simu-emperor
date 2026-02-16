# 测试文档

## 目录结构

```
tests/
├── conftest.py                          # 共享工厂函数和 fixtures
├── unit/
│   └── engine/                          # 引擎模块单元测试（5 个文件，145 个测试）
│       ├── test_base_data.py            # Pydantic 模型验证
│       ├── test_events.py               # 事件与状态模型
│       ├── test_formulas.py             # 经济公式
│       ├── test_calculator.py           # 回合结算引擎
│       └── test_event_generator.py      # 随机事件生成器
│   └── agents/                          # Agent 模块单元测试（待实现）
│   └── persistence/                     # 持久化模块单元测试（待实现）
├── integration/                         # 集成测试（待实现）
└── e2e/                                 # 端到端测试（待实现）
```

## 运行测试

```bash
# 全部测试
uv run pytest tests/

# 仅单元测试
uv run pytest tests/unit/

# 单个目录
uv run pytest tests/unit/engine/

# 单个文件
uv run pytest tests/unit/engine/test_formulas.py

# 单个测试（带详细输出）
uv run pytest tests/unit/engine/test_formulas.py::TestFoodProduction::test_zhili_default -v

# 覆盖率报告
uv run pytest --cov
```

## 各测试文件说明

| 文件 | 测试数 | 覆盖内容 |
|---|---|---|
| `test_base_data.py` | 51 | Pydantic 模型验证、序列化往返、边界条件、指标模型 |
| `test_events.py` | 24 | 事件层级、discriminated union、GameState 序列化 |
| `test_formulas.py` | 40 | 13 个经济公式的默认值/边界/极端场景 |
| `test_calculator.py` | 10 | resolve_turn 集成测试（事件效果、多回合、多省份） |
| `test_event_generator.py` | 20 | 随机事件生成器（模板加载、种子复现、权重选择、省份一致性） |

### test_base_data.py（51 个测试）

基础数据模型的创建、验证、序列化测试。

| TestClass | 测试点 |
|---|---|
| `TestCropType` | 枚举值、字符串构造 |
| `TestPopulationData` | 创建、负数拒绝、happiness 范围、labor_ratio 边界、负增长率 |
| `TestCropData` | 创建、负面积拒绝 |
| `TestAgricultureData` | 空作物列表、多作物、灌溉范围验证 |
| `TestCommerceData` | 创建、边界值、确认 tax_rate 已迁移至 TaxationData |
| `TestTradeData` | 创建、确认 tariff_rate 已迁移至 TaxationData |
| `TestMilitaryData` | 创建、显式 upkeep、morale 范围验证 |
| `TestTaxationData` | 默认值、自定义税率、范围验证、负值拒绝、序列化往返 |
| `TestConsumptionData` | 默认值、自定义值、负值拒绝、序列化往返 |
| `TestAdministrationData` | 默认值、自定义值、维护率范围、负值拒绝、序列化往返 |
| `TestProvinceBaseData` | 工厂创建、override 覆盖、default_factory 字段、JSON/dict 序列化往返 |
| `TestNationalBaseData` | 工厂创建、多省份、序列化往返、负国库拒绝、默认税率修正、默认贡赋率、贡赋率范围 |
| `TestZhiliProvince` | 直隶工厂数据验证、序列化往返 |
| `TestMetricsModels` | ProvinceTurnMetrics 创建、NationalTurnMetrics 创建、序列化往返 |

### test_events.py（24 个测试）

事件效果模型、三种事件类型、discriminated union 序列化、游戏状态模型。

| TestClass | 测试点 |
|---|---|
| `TestEffectOperation` | 枚举值（add/multiply） |
| `TestEffectScope` | 默认空范围、国家级范围、省份级范围 |
| `TestEventEffect` | 加法效果、乘法效果、序列化往返 |
| `TestPlayerEvent` | 创建（含 effects）、自动 event_id、默认 duration |
| `TestAgentEvent` | 创建（含 fidelity）、fidelity 范围验证 |
| `TestRandomEvent` | 创建（含 severity/duration/effects） |
| `TestGameEventDiscriminatedUnion` | Player/Agent/Random 三种类型的 discriminated union 序列化与反序列化、混合列表 |
| `TestGamePhase` | 四阶段枚举值 |
| `TestTurnRecord` | 创建、序列化往返（含事件类型恢复） |
| `TestGameState` | 创建、自动 game_id、活跃事件、完整序列化往返 |

### test_formulas.py（40 个测试）

13 个经济公式的纯函数测试，以直隶初始数据为基准。

| TestClass | 公式 | 测试点 |
|---|---|---|
| `TestFoodProduction` | 粮食生产 | 直隶默认值、空作物、劳动力不足、满灌溉、零灌溉 |
| `TestFoodDemand` | 粮食需求 | 直隶默认（civilian/military/total）、零人口 |
| `TestFoodSurplusAndGranary` | 粮食盈余与粮仓 | 直隶默认、赤字消耗粮仓、粮仓下限为零 |
| `TestLandTaxRevenue` | 田赋 | 直隶默认（249,480 两）、税率修正系数 |
| `TestCommercialTaxRevenue` | 商税 | 直隶默认（10,500 两）、零繁荣度 |
| `TestTradeTariffRevenue` | 关税 | 直隶默认（2,600 两）、零贸易量 |
| `TestMilitaryUpkeep` | 军费 | 直隶默认（225,000 两）、零驻军、满装备 |
| `TestHappinessChange` | 幸福度变化 | 直隶默认、饥荒负影响、零需求、高税率负影响 |
| `TestPopulationChange` | 人口变化 | 直隶默认（+7,280）、完全断粮、中度饥荒、轻微短缺、零需求、增长率上限 |
| `TestMoraleChange` | 士气变化 | 盈余+好装备、赤字+差装备、零军费 |
| `TestCommerceDynamics` | 商业动态 | 直隶默认（商户+9.8, 繁荣+0.005）、高税率抑制、低幸福外流 |
| `TestFiscalBalance` | 财政收支 | 直隶默认（支出=247,000, 盈余=15,580）、赤字场景 |
| `TestTreasuryDistribution` | 国库分配 | 直隶默认（地方=10,906, 贡赋=4,674）、亏损无贡赋、收支平衡 |

### test_calculator.py（10 个测试）

`resolve_turn()` 的集成测试，验证完整结算流程。

| TestClass | 测试点 |
|---|---|
| `TestResolveTurnNoEvents` | 直隶一回合基准结算（全指标验证）、原始数据不可变性、状态回写（粮仓/财政/国库/人口/军费/幸福度/士气） |
| `TestResolveTurnWithEvents` | 旱灾事件（irrigation×0.7→产量下降）、加法效果（增兵→军费上升）、国家级效果（税率修正×1.2→田赋增加） |
| `TestMultiTurnStability` | 10 回合无事件稳定性（人口/幸福度/国库/士气/繁荣度在合理区间）、连续旱灾螺旋（人口下降+粮仓耗尽） |
| `TestMultiProvince` | 两省份独立计算、定向事件只影响目标省份 |

### test_event_generator.py（20 个测试）

随机事件生成器的模板加载、事件生成、种子复现测试。

| TestClass | 测试点 |
|---|---|
| `TestLoadEventTemplates` | 从 JSON 文件加载模板、无效路径异常 |
| `TestGenerateSingleEvent` | 生成事件字段正确性、描述占位符填充 |
| `TestSeededReproducibility` | 相同种子生成相同事件、不同种子生成不同事件 |
| `TestScopeTypes` | province 范围（单省份）、all_provinces 范围（所有省份）、national 范围（国家级） |
| `TestWeightedSelection` | 权重分布统计测试、零权重模板不被选中 |
| `TestValueRange` | 乘法效果值在范围内、加法效果值在范围内 |
| `TestDescriptionEffectProvinceConsistency` | 描述中省份与效果影响省份一致、多效果模板所有省份效果影响同一省份 |
| `TestEdgeCases` | 空模板列表、空省份列表、max_events=0、单省份、持续时间范围 |

## conftest.py 工厂函数

所有工厂函数采用 `**overrides` 模式：提供完整的默认值，调用时可按需覆盖任意字段。

### 工厂函数

| 函数 | 返回类型 | 说明 |
|---|---|---|
| `make_population(**overrides)` | `PopulationData` | 默认：total=100,000, growth_rate=0.02, labor_ratio=0.6, happiness=0.7 |
| `make_agriculture(**overrides)` | `AgricultureData` | 默认：单作物（水稻 50,000 亩, 亩产 3）, irrigation=0.6 |
| `make_commerce(**overrides)` | `CommerceData` | 默认：merchant_households=500, market_prosperity=0.7 |
| `make_trade(**overrides)` | `TradeData` | 默认：trade_volume=10,000, trade_route_quality=0.8 |
| `make_military(**overrides)` | `MilitaryData` | 默认：garrison=5,000, equipment=0.6, morale=0.8 |
| `make_taxation(**overrides)` | `TaxationData` | 默认：land_tax=0.03, commercial_tax=0.10, tariff=0.05 |
| `make_consumption(**overrides)` | `ConsumptionData` | 默认：civilian_grain=3.0, military_grain=5.0 |
| `make_administration(**overrides)` | `AdministrationData` | 默认：officials=200, salary=60, infra_rate=0.02 |
| `make_province(province_id, name, **overrides)` | `ProvinceBaseData` | 组合以上所有子模型，默认 id="jiangnan" |
| `make_national_data(**overrides)` | `NationalBaseData` | 默认：turn=1, imperial_treasury=500,000, 单省份 |
| `make_zhili_province(**overrides)` | `ProvinceBaseData` | 直隶初始数据，使用 eco_system_design.md 定义的均衡值 |

### pytest fixtures

| Fixture | 工厂 | 说明 |
|---|---|---|
| `sample_province` | `make_province()` | 默认江南省 |
| `sample_national_data` | `make_national_data()` | 默认国家数据 |
| `zhili_province` | `make_zhili_province()` | 直隶省初始数据 |

### 使用示例

```python
# 使用默认值
province = make_province()

# 覆盖部分字段
province = make_province(province_id="xibei", name="西北", granary_stock=Decimal("0"))

# 覆盖嵌套子模型
province = make_province(
    population=PopulationData(
        total=Decimal("500000"),
        growth_rate=Decimal("0.01"),
        labor_ratio=Decimal("0.5"),
        happiness=Decimal("0.5"),
    )
)
```

## 测试设计原则

- **纯函数测试**：引擎测试无 I/O、无 LLM 调用、无网络依赖，全部为确定性纯函数
- **Decimal 精确断言**：所有数值使用 `Decimal` 类型，避免浮点精度问题
- **工厂函数模式**：`默认值 + **overrides` 覆盖，测试间互不干扰
- **直隶基准场景**：以 `eco_system_design.md` 中定义的直隶均衡初始值作为基准验证，确保公式实现与设计文档一致
- **不可变性验证**：`resolve_turn()` 不修改输入数据，返回全新状态
- **边界覆盖**：每个公式测试零值、极端值、越界拒绝等边界条件
