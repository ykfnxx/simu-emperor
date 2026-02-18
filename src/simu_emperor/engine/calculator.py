"""回合结算引擎：resolve_turn() 编排器。

计算顺序：
1. 深拷贝 current_data
2. 收集所有活跃事件的 EventEffect
3. 按 target 分组，乘法效果先合并（连乘），加法效果后合并（累加）
4. 应用效果到基础数据
5. 对每个省份运行经济公式，计算 ProvinceTurnMetrics
6. 将反馈效果回写基础数据（人口、幸福度、士气、商户、粮仓、国库等）
7. 约束校验（clamp 所有有界值）
8. 事件 duration 递减，移除过期事件
9. 返回 (new_data, metrics)
"""

from collections import defaultdict
from decimal import Decimal

from simu_emperor.engine.formulas import (
    HAPPINESS_MAX,
    HAPPINESS_MIN,
    MORALE_MAX,
    MORALE_MIN,
    PROSPERITY_MAX,
    PROSPERITY_MIN,
    _clamp,
    calculate_commercial_tax_revenue,
    calculate_commerce_dynamics,
    calculate_fiscal_balance,
    calculate_food_demand,
    calculate_food_production,
    calculate_food_surplus_and_granary,
    calculate_happiness_change,
    calculate_land_tax_revenue,
    calculate_military_upkeep,
    calculate_morale_change,
    calculate_population_change,
    calculate_trade_tariff_revenue,
    calculate_treasury_distribution,
)
from simu_emperor.engine.models.base_data import NationalBaseData, ProvinceBaseData
from simu_emperor.engine.models.effects import EventEffect
from simu_emperor.engine.models.events import EventSource, GameEvent
from simu_emperor.engine.models.metrics import NationalTurnMetrics, ProvinceTurnMetrics

_ZERO = Decimal("0")
_ONE = Decimal("1")


def _sort_events_by_priority(events: list[GameEvent]) -> list[GameEvent]:
    """按应用优先级排序：RandomEvent → AgentEvent → PlayerEvent。

    后应用的覆盖先应用的（同一字段），皇帝直接命令优先级最高。
    """
    order = {EventSource.RANDOM: 0, EventSource.AGENT: 1, EventSource.PLAYER: 2}
    return sorted(events, key=lambda e: order.get(e.source, 0))


def _collect_effects(active_events: list[GameEvent]) -> list[EventEffect]:
    """从所有活跃事件中收集效果列表。"""
    effects: list[EventEffect] = []
    for event in active_events:
        effects.extend(event.effects)
    return effects


def _apply_effects(
    data: NationalBaseData,
    effects: list[EventEffect],
) -> None:
    """将效果应用到基础数据（原地修改）。

    按 target 分组：
    - 乘法效果先合并（连乘）
    - 加法效果后合并（累加）
    """
    # 按 (province_id, target) 分组
    grouped: dict[tuple[str | None, str], dict[str, list[Decimal]]] = defaultdict(
        lambda: {"multiply": [], "add": []}
    )

    for effect in effects:
        if effect.scope.is_national:
            # 国家级效果，target 作用于 NationalBaseData 的直接字段
            key = (None, effect.target)
            grouped[key][effect.operation.value].append(effect.value)
        else:
            province_ids = effect.scope.province_ids
            if not province_ids:
                # 无指定省份且非国家级 → 应用到所有省份
                province_ids = [p.province_id for p in data.provinces]
            for pid in province_ids:
                key = (pid, effect.target)
                grouped[key][effect.operation.value].append(effect.value)

    # 应用效果
    for (province_id, target), ops in grouped.items():
        if province_id is None:
            # 国家级字段
            _apply_field_effects(data, target, ops)
        else:
            province = _find_province(data, province_id)
            if province is not None:
                _apply_field_effects(province, target, ops)


def _find_province(data: NationalBaseData, province_id: str) -> ProvinceBaseData | None:
    """按 ID 查找省份。"""
    for province in data.provinces:
        if province.province_id == province_id:
            return province
    return None


def _apply_field_effects(
    obj: object,
    target: str,
    ops: dict[str, list[Decimal]],
) -> None:
    """对对象的嵌套字段应用乘法和加法效果。

    target 使用点分路径，如 "population.total" 或 "agriculture.irrigation_level"。
    """
    parts = target.split(".")
    # 导航到倒数第二级
    current = obj
    for part in parts[:-1]:
        current = getattr(current, part, None)
        if current is None:
            return

    field_name = parts[-1]
    value = getattr(current, field_name, None)
    if value is None:
        return

    # 先应用乘法（连乘）
    for multiplier in ops.get("multiply", []):
        value = value * multiplier

    # 再应用加法（累加）
    for addend in ops.get("add", []):
        value = value + addend

    setattr(current, field_name, value)


def _resolve_province(
    province: ProvinceBaseData,
    national_tax_modifier: Decimal,
    tribute_rate: Decimal,
) -> tuple[ProvinceTurnMetrics, Decimal]:
    """对单个省份运行全部经济公式。

    Returns:
        (province_metrics, imperial_tribute)
    """
    # 5.1 粮食产量
    food_production = calculate_food_production(province.agriculture, province.population)

    # 5.2 粮食需求
    food_demand_civilian, food_demand_military, food_demand_total = calculate_food_demand(
        province.population,
        province.consumption,
        province.military,
    )

    # 5.3 粮食平衡与粮仓
    food_surplus, new_granary, granary_change = calculate_food_surplus_and_granary(
        food_production,
        food_demand_total,
        province.granary_stock,
    )

    # 5.4 田赋收入
    land_tax_revenue = calculate_land_tax_revenue(
        food_production,
        province.taxation,
        national_tax_modifier,
    )

    # 5.5 商税收入
    commercial_tax_revenue = calculate_commercial_tax_revenue(
        province.commerce,
        province.taxation,
        national_tax_modifier,
    )

    # 5.6 关税收入
    trade_tariff_revenue = calculate_trade_tariff_revenue(
        province.trade,
        province.taxation,
    )

    total_revenue = land_tax_revenue + commercial_tax_revenue + trade_tariff_revenue

    # 5.7 军事维持费
    military_upkeep = calculate_military_upkeep(province.military)

    # 5.12 财政平衡（需要 military_upkeep 和 total_revenue）
    (
        official_salary_cost,
        infrastructure_cost,
        court_levy_cost,
        total_expenditure,
        fiscal_surplus,
    ) = calculate_fiscal_balance(province.administration, military_upkeep, total_revenue)

    # 5.8 幸福度变化
    happiness_change = calculate_happiness_change(
        food_production,
        food_demand_total,
        province.taxation,
        province.military,
        fiscal_surplus,
        total_revenue,
    )

    # 5.9 人口变化
    population_change = calculate_population_change(
        province.population,
        food_production,
        food_demand_total,
    )

    # 5.10 士气变化
    morale_change = calculate_morale_change(
        province.military,
        fiscal_surplus,
        military_upkeep,
    )

    # 5.11 商业动态
    merchant_change, prosperity_change = calculate_commerce_dynamics(
        province.commerce,
        province.taxation,
        province.population.happiness,
    )

    # 5.13 国库分配
    local_change, imperial_tribute = calculate_treasury_distribution(
        fiscal_surplus,
        tribute_rate,
    )

    # --- 回写反馈到基础数据 ---
    province.granary_stock = new_granary
    province.local_treasury = max(_ZERO, province.local_treasury + local_change)
    province.military.upkeep = military_upkeep
    province.population.total = max(_ZERO, province.population.total + population_change)
    province.population.happiness = _clamp(
        province.population.happiness + happiness_change,
        HAPPINESS_MIN,
        HAPPINESS_MAX,
    )
    province.military.morale = _clamp(
        province.military.morale + morale_change,
        MORALE_MIN,
        MORALE_MAX,
    )
    province.commerce.merchant_households = max(
        _ZERO,
        province.commerce.merchant_households + merchant_change,
    )
    province.commerce.market_prosperity = _clamp(
        province.commerce.market_prosperity + prosperity_change,
        PROSPERITY_MIN,
        PROSPERITY_MAX,
    )

    metrics = ProvinceTurnMetrics(
        province_id=province.province_id,
        food_production=food_production,
        food_demand_civilian=food_demand_civilian,
        food_demand_military=food_demand_military,
        food_demand_total=food_demand_total,
        food_surplus=food_surplus,
        granary_change=granary_change,
        land_tax_revenue=land_tax_revenue,
        commercial_tax_revenue=commercial_tax_revenue,
        trade_tariff_revenue=trade_tariff_revenue,
        total_revenue=total_revenue,
        military_upkeep=military_upkeep,
        official_salary_cost=official_salary_cost,
        infrastructure_cost=infrastructure_cost,
        court_levy_cost=court_levy_cost,
        total_expenditure=total_expenditure,
        fiscal_surplus=fiscal_surplus,
        population_change=population_change,
        happiness_change=happiness_change,
        treasury_change=local_change,
    )

    return metrics, imperial_tribute


def resolve_turn(
    current_data: NationalBaseData,
    active_events: list[GameEvent],
) -> tuple[NationalBaseData, NationalTurnMetrics]:
    """回合结算主入口。

    1. 深拷贝数据
    2. 收集并应用事件效果
    3. 对每个省份运行经济公式
    4. 汇总国家级指标
    5. 返回更新后的数据和指标
    """
    # 1. 深拷贝
    new_data = current_data.model_copy(deep=True)

    # 2-4. 按优先级排序事件，收集并应用效果
    sorted_events = _sort_events_by_priority(active_events)
    effects = _collect_effects(sorted_events)
    if effects:
        _apply_effects(new_data, effects)

    # 5. 对每个省份运行经济公式
    province_metrics_list: list[ProvinceTurnMetrics] = []
    total_tribute = _ZERO

    for province in new_data.provinces:
        metrics, tribute = _resolve_province(
            province,
            new_data.national_tax_modifier,
            new_data.tribute_rate,
        )
        province_metrics_list.append(metrics)
        total_tribute += tribute

    # 6. 更新国库
    new_data.imperial_treasury = max(_ZERO, new_data.imperial_treasury + total_tribute)

    # 7. 回合数递增
    new_data.turn += 1

    # 8. 构建国家级指标
    national_metrics = NationalTurnMetrics(
        turn=new_data.turn,
        province_metrics=province_metrics_list,
        imperial_treasury_change=total_tribute,
        tribute_total=total_tribute,
    )

    return new_data, national_metrics
