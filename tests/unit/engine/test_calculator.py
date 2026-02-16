"""回合结算引擎集成测试：resolve_turn 完整场景验证。"""

from decimal import Decimal

from simu_emperor.engine.calculator import resolve_turn
from simu_emperor.engine.models.base_data import NationalBaseData
from simu_emperor.engine.models.effects import EffectOperation, EffectScope, EventEffect
from simu_emperor.engine.models.events import AgentEvent, PlayerEvent, RandomEvent

from tests.conftest import make_national_data, make_province, make_zhili_province


class TestResolveTurnNoEvents:
    """无事件时的基准结算。"""

    def test_zhili_one_turn(self):
        """直隶默认数据结算一回合，验证关键指标。"""
        zhili = make_zhili_province()
        national = NationalBaseData(
            turn=0,
            imperial_treasury=Decimal("500000"),
            national_tax_modifier=Decimal("1.0"),
            tribute_rate=Decimal("0.30"),
            provinces=[zhili],
        )

        new_data, metrics = resolve_turn(national, [])

        # 回合递增
        assert new_data.turn == 1

        # 国家级指标
        assert metrics.turn == 1
        assert len(metrics.province_metrics) == 1

        pm = metrics.province_metrics[0]
        assert pm.province_id == "zhili"

        # 粮食
        assert pm.food_production == Decimal("8316000")
        assert pm.food_demand_total == Decimal("7950000")
        assert pm.food_surplus == Decimal("366000")

        # 财政
        assert pm.land_tax_revenue == Decimal("249480.00")
        assert pm.commercial_tax_revenue == Decimal("10500.00")
        assert pm.trade_tariff_revenue == Decimal("2600.00")
        assert pm.total_revenue == Decimal("262580.00")
        assert pm.military_upkeep == Decimal("225000.0")
        assert pm.total_expenditure == Decimal("247000.00")
        assert pm.fiscal_surplus == Decimal("15580.00")

        # 国库分配
        assert pm.treasury_change == Decimal("10906.0")
        assert metrics.tribute_total == Decimal("4674.0")

        # 人口变化
        assert pm.population_change == Decimal("7280.0")

    def test_original_data_unchanged(self):
        """resolve_turn 不修改原始数据。"""
        zhili = make_zhili_province()
        national = NationalBaseData(
            turn=0,
            imperial_treasury=Decimal("500000"),
            provinces=[zhili],
        )
        original_pop = national.provinces[0].population.total

        new_data, _ = resolve_turn(national, [])

        # 原始数据未变
        assert national.turn == 0
        assert national.provinces[0].population.total == original_pop
        assert national.imperial_treasury == Decimal("500000")

        # 新数据已变
        assert new_data.turn == 1
        assert new_data.provinces[0].population.total != original_pop

    def test_state_updates(self):
        """验证结算后基础数据的关键状态回写。"""
        zhili = make_zhili_province()
        national = NationalBaseData(
            turn=0,
            imperial_treasury=Decimal("500000"),
            tribute_rate=Decimal("0.30"),
            provinces=[zhili],
        )

        new_data, _ = resolve_turn(national, [])
        p = new_data.provinces[0]

        # 粮仓增加
        assert p.granary_stock == Decimal("1566000")

        # 地方财政增加
        assert p.local_treasury == Decimal("90906.0")

        # 国库增加
        assert new_data.imperial_treasury == Decimal("504674.0")

        # 人口增加
        assert p.population.total == Decimal("2607280.0")

        # 军费回写
        assert p.military.upkeep == Decimal("225000.0")

        # 幸福度上升
        assert p.population.happiness > Decimal("0.70")

        # 士气上升
        assert p.military.morale > Decimal("0.70")


class TestResolveTurnWithEvents:
    """带事件效果的结算。"""

    def test_drought_event(self):
        """旱灾事件 irrigation×0.7 → 粮食产量下降。"""
        zhili = make_zhili_province()
        national = NationalBaseData(
            turn=0,
            imperial_treasury=Decimal("500000"),
            provinces=[zhili],
        )

        drought = RandomEvent(
            turn_created=0,
            description="华北大旱",
            category="disaster",
            severity=Decimal("0.7"),
            duration=1,
            effects=[
                EventEffect(
                    target="agriculture.irrigation_level",
                    operation=EffectOperation.MULTIPLY,
                    value=Decimal("0.7"),
                    scope=EffectScope(province_ids=["zhili"]),
                ),
            ],
        )

        new_data, metrics = resolve_turn(national, [drought])
        pm = metrics.province_metrics[0]

        # 灌溉从 0.60 × 0.7 = 0.42
        # irrigation_modifier = 0.6 + 0.4 × 0.42 = 0.768
        # food_production = 9900000 × 0.768 = 7,603,200
        assert pm.food_production == Decimal("7603200.0")

        # 粮食变为赤字
        assert pm.food_surplus < Decimal("0")

    def test_add_effect(self):
        """加法效果：增加驻军。"""
        zhili = make_zhili_province()
        national = NationalBaseData(
            turn=0,
            imperial_treasury=Decimal("500000"),
            provinces=[zhili],
        )

        reinforcement = RandomEvent(
            turn_created=0,
            description="朝廷增兵",
            category="military",
            severity=Decimal("0.3"),
            duration=1,
            effects=[
                EventEffect(
                    target="military.garrison_size",
                    operation=EffectOperation.ADD,
                    value=Decimal("5000"),
                    scope=EffectScope(province_ids=["zhili"]),
                ),
            ],
        )

        new_data, metrics = resolve_turn(national, [reinforcement])
        pm = metrics.province_metrics[0]

        # 军费增加：35000 × 6 × 1.25 = 262500
        assert pm.military_upkeep == Decimal("262500.0")

        # 粮食需求增加：军粮 35000×5 = 175000
        assert pm.food_demand_military == Decimal("175000")

    def test_national_effect(self):
        """国家级效果：修改税率修正。"""
        zhili = make_zhili_province()
        national = NationalBaseData(
            turn=0,
            imperial_treasury=Decimal("500000"),
            national_tax_modifier=Decimal("1.0"),
            provinces=[zhili],
        )

        tax_reform = RandomEvent(
            turn_created=0,
            description="税制改革",
            category="policy",
            severity=Decimal("0.5"),
            duration=1,
            effects=[
                EventEffect(
                    target="national_tax_modifier",
                    operation=EffectOperation.MULTIPLY,
                    value=Decimal("1.2"),
                    scope=EffectScope(is_national=True),
                ),
            ],
        )

        _, metrics = resolve_turn(national, [tax_reform])
        pm = metrics.province_metrics[0]

        # 田赋: 8316000 × 0.03 × 1.0 × 1.2 = 299,376
        assert pm.land_tax_revenue == Decimal("299376.000")


class TestMultiTurnStability:
    """多回合稳定性验证。"""

    def test_ten_turns_no_explosion(self):
        """无事件 10 回合：各指标缓慢增长但不爆发。"""
        zhili = make_zhili_province()
        national = NationalBaseData(
            turn=0,
            imperial_treasury=Decimal("500000"),
            tribute_rate=Decimal("0.30"),
            provinces=[zhili],
        )

        data = national
        for _ in range(10):
            data, metrics = resolve_turn(data, [])

        assert data.turn == 10

        p = data.provinces[0]
        # 人口缓慢增长（约 +2.8%/10年 ≈ 2,673,000 左右）
        assert p.population.total > Decimal("2600000")
        assert p.population.total < Decimal("3000000")

        # 幸福度仍在合理范围
        assert Decimal("0.05") <= p.population.happiness <= Decimal("0.95")

        # 国库在增长
        assert data.imperial_treasury > Decimal("500000")

        # 士气稳定
        assert Decimal("0.1") <= p.military.morale <= Decimal("0.95")

        # 繁荣度稳定
        assert Decimal("0.1") <= p.commerce.market_prosperity <= Decimal("0.9")

    def test_famine_spiral(self):
        """连续旱灾 → 粮食危机 → 人口下降。"""
        zhili = make_zhili_province()
        national = NationalBaseData(
            turn=0,
            imperial_treasury=Decimal("500000"),
            provinces=[zhili],
        )

        drought = RandomEvent(
            turn_created=0,
            description="连年大旱",
            category="disaster",
            severity=Decimal("0.9"),
            duration=100,  # 持续很多回合
            effects=[
                EventEffect(
                    target="agriculture.irrigation_level",
                    operation=EffectOperation.MULTIPLY,
                    value=Decimal("0.5"),
                    scope=EffectScope(province_ids=["zhili"]),
                ),
            ],
        )

        data = national
        for _ in range(5):
            data, _ = resolve_turn(data, [drought])

        p = data.provinces[0]
        # 人口应该在下降（旱灾导致粮食赤字→饥荒死亡）
        assert p.population.total < Decimal("2600000")
        # 粮仓被耗尽
        assert p.granary_stock == Decimal("0")


class TestMultiProvince:
    """多省份结算。"""

    def test_two_provinces(self):
        """两省份独立计算。"""
        province1 = make_zhili_province()
        province2 = make_zhili_province()
        province2.province_id = "jiangnan"
        province2.name = "江南"
        national = NationalBaseData(
            turn=0,
            imperial_treasury=Decimal("500000"),
            tribute_rate=Decimal("0.30"),
            provinces=[province1, province2],
        )

        new_data, metrics = resolve_turn(national, [])

        assert len(metrics.province_metrics) == 2
        assert metrics.province_metrics[0].province_id == "zhili"
        assert metrics.province_metrics[1].province_id == "jiangnan"

        # 两个省份的 tribute 都汇入国库
        assert metrics.tribute_total > Decimal("0")
        assert new_data.imperial_treasury > national.imperial_treasury

    def test_targeted_event_only_affects_target(self):
        """定向事件只影响目标省份。"""
        province1 = make_province("jiangnan", "江南")
        province2 = make_province("xibei", "西北")
        national = make_national_data(provinces=[province1, province2])

        event = RandomEvent(
            turn_created=0,
            description="江南水灾",
            category="disaster",
            severity=Decimal("0.5"),
            duration=1,
            effects=[
                EventEffect(
                    target="agriculture.irrigation_level",
                    operation=EffectOperation.MULTIPLY,
                    value=Decimal("0.5"),
                    scope=EffectScope(province_ids=["jiangnan"]),
                ),
            ],
        )

        new_data, metrics = resolve_turn(national, [event])

        # 江南灌溉被影响
        pm_jn = metrics.province_metrics[0]
        pm_xb = metrics.province_metrics[1]

        # 两省产量不同（西北未受影响）
        assert pm_jn.food_production != pm_xb.food_production


class TestEventApplicationOrder:
    """事件按 RandomEvent → AgentEvent → PlayerEvent(direct=True) 顺序应用。"""

    def test_random_before_agent(self):
        """RandomEvent 先应用，AgentEvent 后应用；同字段时 Agent 覆盖 Random。"""
        zhili = make_zhili_province()
        national = NationalBaseData(
            turn=0,
            imperial_treasury=Decimal("500000"),
            national_tax_modifier=Decimal("1.0"),
            provinces=[zhili],
        )

        # Random: 灌溉 ×0.5
        random_event = RandomEvent(
            turn_created=0,
            description="旱灾",
            category="disaster",
            severity=Decimal("0.5"),
            effects=[
                EventEffect(
                    target="agriculture.irrigation_level",
                    operation=EffectOperation.MULTIPLY,
                    value=Decimal("0.5"),
                    scope=EffectScope(province_ids=["zhili"]),
                ),
            ],
        )

        # Agent: 灌溉 ×2.0（修复旱灾影响）
        agent_event = AgentEvent(
            turn_created=0,
            description="工部修缮水利",
            agent_event_type="repair_irrigation",
            agent_id="gongbu",
            fidelity=Decimal("1.0"),
            effects=[
                EventEffect(
                    target="agriculture.irrigation_level",
                    operation=EffectOperation.MULTIPLY,
                    value=Decimal("2.0"),
                    scope=EffectScope(province_ids=["zhili"]),
                ),
            ],
        )

        # 无论传入顺序如何，Random 应先于 Agent 应用
        # 效果：0.6 × 0.5 × 2.0 = 0.6（先乘0.5再乘2.0）
        _, metrics_agent_first = resolve_turn(national, [agent_event, random_event])
        _, metrics_random_first = resolve_turn(national, [random_event, agent_event])

        # 两种传入顺序应产生相同结果（因为内部会排序）
        assert metrics_agent_first.province_metrics[0].food_production == (
            metrics_random_first.province_metrics[0].food_production
        )

    def test_player_direct_last(self):
        """PlayerEvent(direct=True) 最后应用，优先级最高。"""
        zhili = make_zhili_province()
        national = NationalBaseData(
            turn=0,
            imperial_treasury=Decimal("500000"),
            national_tax_modifier=Decimal("1.0"),
            provinces=[zhili],
        )

        # Random: 国家税率 ×0.5
        random_event = RandomEvent(
            turn_created=0,
            description="民变减税",
            category="rebellion",
            severity=Decimal("0.3"),
            effects=[
                EventEffect(
                    target="national_tax_modifier",
                    operation=EffectOperation.MULTIPLY,
                    value=Decimal("0.5"),
                    scope=EffectScope(is_national=True),
                ),
            ],
        )

        # Player(direct): 国家税率 ×3.0（皇帝亲令加税）
        player_event = PlayerEvent(
            turn_created=0,
            description="皇帝亲令加税",
            command_type="tax_increase",
            direct=True,
            effects=[
                EventEffect(
                    target="national_tax_modifier",
                    operation=EffectOperation.MULTIPLY,
                    value=Decimal("3.0"),
                    scope=EffectScope(is_national=True),
                ),
            ],
        )

        # Player 排在 Random 之后：1.0 × 0.5 × 3.0 = 1.5
        # 无论传入顺序如何
        _, metrics1 = resolve_turn(national, [player_event, random_event])
        _, metrics2 = resolve_turn(national, [random_event, player_event])

        assert metrics1.province_metrics[0].land_tax_revenue == (
            metrics2.province_metrics[0].land_tax_revenue
        )

    def test_non_direct_player_event_treated_normally(self):
        """PlayerEvent(direct=False) 也按 PLAYER 顺序排（在 Agent 之后）。"""
        zhili = make_zhili_province()
        national = NationalBaseData(
            turn=0,
            imperial_treasury=Decimal("500000"),
            national_tax_modifier=Decimal("1.0"),
            provinces=[zhili],
        )

        agent_event = AgentEvent(
            turn_created=0,
            description="户部执行",
            agent_event_type="execute",
            agent_id="hubu",
            fidelity=Decimal("0.8"),
            effects=[
                EventEffect(
                    target="national_tax_modifier",
                    operation=EffectOperation.MULTIPLY,
                    value=Decimal("1.1"),
                    scope=EffectScope(is_national=True),
                ),
            ],
        )

        player_event = PlayerEvent(
            turn_created=0,
            description="下令调税",
            command_type="adjust_tax",
            direct=False,
            effects=[
                EventEffect(
                    target="national_tax_modifier",
                    operation=EffectOperation.MULTIPLY,
                    value=Decimal("1.2"),
                    scope=EffectScope(is_national=True),
                ),
            ],
        )

        # Agent 先于 Player 应用：1.0 × 1.1 × 1.2 = 1.32
        _, metrics1 = resolve_turn(national, [player_event, agent_event])
        _, metrics2 = resolve_turn(national, [agent_event, player_event])

        assert metrics1.province_metrics[0].land_tax_revenue == (
            metrics2.province_metrics[0].land_tax_revenue
        )
