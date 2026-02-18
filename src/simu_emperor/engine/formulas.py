"""经济公式：13个纯函数，实现粮食/税收/支出/人口/幸福度/士气/商业计算。

所有函数为纯函数，无副作用，不修改传入对象。
"""

from decimal import Decimal

from simu_emperor.engine.models.base_data import (
    AdministrationData,
    AgricultureData,
    CommerceData,
    ConsumptionData,
    MilitaryData,
    PopulationData,
    TaxationData,
    TradeData,
)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# --- 粮食生产 ---
LABOR_PER_MU = Decimal("0.05")
# 每亩农田所需劳动力(人)。华北精耕细作，每人可耕约20亩。

IRRIGATION_BASE_FACTOR = Decimal("0.6")
# 无灌溉(纯雨养)时的产量系数。华北降水不稳定，无灌溉损失约40%。

IRRIGATION_BONUS_FACTOR = Decimal("0.4")
# 满灌溉时的额外产量系数。irrigation_modifier = 0.6 + 0.4 × level。

# --- 财政 ---
BASE_TAX_PER_HOUSEHOLD = Decimal("50")
# 每户商户年均基础应税额(两)。参考清代中期商铺年均营业额折算。

GRAIN_TO_SILVER_RATE = Decimal("1.0")
# 粮银折算率(石→两)。清代中期米价约1-2两/石，取1.0简化计算。

# --- 军事 ---
EQUIPMENT_COST_MULTIPLIER = Decimal("0.5")
# 装备等级对维护费的加成系数。equipment_level=1时军费增加50%。

# --- 幸福度 ---
FOOD_SECURITY_HAPPY_THRESHOLD = Decimal("1.05")
# 粮食安全充足线。production/demand >= 1.05 时民众安心。

FOOD_SECURITY_CRISIS_THRESHOLD = Decimal("0.90")
# 粮食危机线。ratio < 0.90 时出现饥荒，幸福度急剧下降。

TAX_BURDEN_THRESHOLD = Decimal("0.10")
# 税负压力线。综合税率超过10%时民众不满。

SECURITY_MORALE_WEIGHT = Decimal("0.05")
# 士气对幸福度的影响权重。高士气→治安好→民众安心。

FISCAL_HAPPINESS_WEIGHT = Decimal("0.02")
# 财政状况对幸福度的微弱影响。

# --- 人口 ---
MAX_GROWTH_RATE = Decimal("0.005")
# 0.5%/年上限。古典农业社会人口增长缓慢。

MIN_GROWTH_RATE = Decimal("-0.10")
# -10%/年下限。极端饥荒+瘟疫时的最大人口损失。

STARVATION_MORTALITY_RATE = Decimal("0.15")
# 饥荒致死率系数。ratio=0(完全断粮)时年死亡率约15%。

FAMINE_THRESHOLD = Decimal("0.90")
# 饥荒开始阈值。ratio < 0.90 时开始出现饥荒死亡。

# --- 商业 ---
MERCHANT_MIGRATION_SENSITIVITY = Decimal("0.02")
# 商户迁移敏感度。每年最多±2%的商户增减。

PROSPERITY_ADJUSTMENT_RATE = Decimal("0.05")
# 繁荣度向幸福度靠拢的速率。

# --- Clamping ---
HAPPINESS_MIN = Decimal("0.05")
HAPPINESS_MAX = Decimal("0.95")
PROSPERITY_MIN = Decimal("0.1")
PROSPERITY_MAX = Decimal("0.9")
MORALE_MIN = Decimal("0.1")
MORALE_MAX = Decimal("0.95")

_ZERO = Decimal("0")
_ONE = Decimal("1")
_TWO = Decimal("2")
_HALF = Decimal("0.5")


def _clamp(value: Decimal, lo: Decimal, hi: Decimal) -> Decimal:
    """将 value 限制在 [lo, hi] 范围内。"""
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


# ---------------------------------------------------------------------------
# 5.1  粮食产量
# ---------------------------------------------------------------------------


def calculate_food_production(
    agriculture: AgricultureData,
    population: PopulationData,
) -> Decimal:
    """计算粮食总产量(石)。

    food_production = Σ(crop.area_mu × yield_per_mu) × irrigation_modifier × labor_modifier
    """
    raw_output = sum(
        (crop.area_mu * crop.yield_per_mu for crop in agriculture.crops),
        start=_ZERO,
    )

    irrigation_modifier = (
        IRRIGATION_BASE_FACTOR + IRRIGATION_BONUS_FACTOR * agriculture.irrigation_level
    )

    total_area = sum((crop.area_mu for crop in agriculture.crops), start=_ZERO)
    required_labor = total_area * LABOR_PER_MU
    if required_labor == _ZERO:
        labor_modifier = _ONE
    else:
        available_labor = population.total * population.labor_ratio
        labor_modifier = min(_ONE, available_labor / required_labor)

    return raw_output * irrigation_modifier * labor_modifier


# ---------------------------------------------------------------------------
# 5.2  粮食需求
# ---------------------------------------------------------------------------


def calculate_food_demand(
    population: PopulationData,
    consumption: ConsumptionData,
    military: MilitaryData,
) -> tuple[Decimal, Decimal, Decimal]:
    """计算粮食需求(石)。

    Returns:
        (civilian_demand, military_demand, total_demand)
    """
    civilian_demand = population.total * consumption.civilian_grain_per_capita
    military_demand = military.garrison_size * consumption.military_grain_per_soldier
    total_demand = civilian_demand + military_demand
    return civilian_demand, military_demand, total_demand


# ---------------------------------------------------------------------------
# 5.3  粮食平衡与粮仓
# ---------------------------------------------------------------------------


def calculate_food_surplus_and_granary(
    food_production: Decimal,
    food_demand_total: Decimal,
    current_granary: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """计算粮食盈余与粮仓变动。

    Returns:
        (food_surplus, new_granary, granary_change)
    """
    food_surplus = food_production - food_demand_total
    new_granary = max(_ZERO, current_granary + food_surplus)
    granary_change = new_granary - current_granary
    return food_surplus, new_granary, granary_change


# ---------------------------------------------------------------------------
# 5.4  田赋收入
# ---------------------------------------------------------------------------


def calculate_land_tax_revenue(
    food_production: Decimal,
    taxation: TaxationData,
    national_tax_modifier: Decimal,
) -> Decimal:
    """计算田赋收入(两)。折银征收，不影响粮食实物流。"""
    return food_production * taxation.land_tax_rate * GRAIN_TO_SILVER_RATE * national_tax_modifier


# ---------------------------------------------------------------------------
# 5.5  商税收入
# ---------------------------------------------------------------------------


def calculate_commercial_tax_revenue(
    commerce: CommerceData,
    taxation: TaxationData,
    national_tax_modifier: Decimal,
) -> Decimal:
    """计算商税收入(两)。"""
    return (
        commerce.merchant_households
        * BASE_TAX_PER_HOUSEHOLD
        * taxation.commercial_tax_rate
        * commerce.market_prosperity
        * national_tax_modifier
    )


# ---------------------------------------------------------------------------
# 5.6  关税收入
# ---------------------------------------------------------------------------


def calculate_trade_tariff_revenue(
    trade: TradeData,
    taxation: TaxationData,
) -> Decimal:
    """计算关税收入(两)。"""
    return trade.trade_volume * taxation.tariff_rate * trade.trade_route_quality


# ---------------------------------------------------------------------------
# 5.7  军事维持费
# ---------------------------------------------------------------------------


def calculate_military_upkeep(military: MilitaryData) -> Decimal:
    """计算军事维持费(两)。"""
    return (
        military.garrison_size
        * military.upkeep_per_soldier
        * (_ONE + EQUIPMENT_COST_MULTIPLIER * military.equipment_level)
    )


# ---------------------------------------------------------------------------
# 5.8  幸福度变化
# ---------------------------------------------------------------------------


def calculate_happiness_change(
    food_production: Decimal,
    food_demand_total: Decimal,
    taxation: TaxationData,
    military: MilitaryData,
    fiscal_surplus: Decimal,
    total_revenue: Decimal,
) -> Decimal:
    """计算幸福度变化量。"""
    # food_factor
    if food_demand_total == _ZERO:
        food_factor = Decimal("0.01")
    else:
        ratio = food_production / food_demand_total
        if ratio >= FOOD_SECURITY_HAPPY_THRESHOLD:
            food_factor = Decimal("0.01")
        elif ratio >= _ONE:
            food_factor = Decimal("0.005")
        elif ratio >= FOOD_SECURITY_CRISIS_THRESHOLD:
            food_factor = Decimal("-0.02")
        else:
            food_factor = Decimal("-0.05") * (FAMINE_THRESHOLD - ratio) / FAMINE_THRESHOLD

    # tax_factor
    effective_tax = (taxation.land_tax_rate + taxation.commercial_tax_rate) / _TWO
    if effective_tax > TAX_BURDEN_THRESHOLD:
        tax_factor = -(effective_tax - TAX_BURDEN_THRESHOLD) * _HALF
    else:
        tax_factor = Decimal("0.005")

    # security_factor
    security_factor = (military.morale - _HALF) * SECURITY_MORALE_WEIGHT

    # fiscal_factor
    if total_revenue == _ZERO:
        fiscal_factor = _ZERO
    else:
        ratio_fiscal = min(abs(fiscal_surplus / total_revenue), Decimal("0.2"))
        sign = _ONE if fiscal_surplus >= _ZERO else -_ONE
        fiscal_factor = sign * ratio_fiscal * FISCAL_HAPPINESS_WEIGHT

    return food_factor + tax_factor + security_factor + fiscal_factor


# ---------------------------------------------------------------------------
# 5.9  人口变化（分段函数）
# ---------------------------------------------------------------------------


def calculate_population_change(
    population: PopulationData,
    food_production: Decimal,
    food_demand_total: Decimal,
) -> Decimal:
    """计算人口变动量。

    包含自然增长和饥荒死亡两个分量。
    """
    # food_security_ratio
    if food_demand_total == _ZERO:
        ratio = FOOD_SECURITY_HAPPY_THRESHOLD  # 无需求时视为充足
    else:
        ratio = food_production / food_demand_total

    # food_modifier (用于自然增长乘数)
    if ratio >= _ONE:
        food_modifier = _ONE
    elif ratio >= Decimal("0.95"):
        food_modifier = _HALF
    elif ratio >= FAMINE_THRESHOLD:
        food_modifier = _ZERO
    else:
        food_modifier = _ZERO  # 饥荒时自然增长归零，死亡由 starvation_deaths 处理

    # happiness_modifier
    happiness_modifier = population.happiness * _TWO

    # effective growth rate (clamped)
    effective_growth = _clamp(
        population.growth_rate * happiness_modifier * food_modifier,
        MIN_GROWTH_RATE,
        MAX_GROWTH_RATE,
    )
    natural_change = population.total * effective_growth

    # starvation deaths (仅 ratio < FAMINE_THRESHOLD 时)
    starvation_deaths = _ZERO
    if ratio < FAMINE_THRESHOLD:
        starvation_deaths = (
            population.total
            * STARVATION_MORTALITY_RATE
            * (FAMINE_THRESHOLD - ratio)
            / FAMINE_THRESHOLD
        )

    return natural_change - starvation_deaths


# ---------------------------------------------------------------------------
# 5.10 士气变化
# ---------------------------------------------------------------------------


def calculate_morale_change(
    military: MilitaryData,
    fiscal_surplus: Decimal,
    military_upkeep: Decimal,
) -> Decimal:
    """计算士气变化量。"""
    # pay_factor
    if fiscal_surplus >= _ZERO:
        pay_factor = Decimal("0.01")
    else:
        if military_upkeep == _ZERO:
            pay_factor = _ZERO
        else:
            deficit_ratio = min(_ONE, abs(fiscal_surplus) / military_upkeep)
            pay_factor = Decimal("-0.03") * deficit_ratio

    # equipment_factor
    equipment_factor = (military.equipment_level - _HALF) * Decimal("0.02")

    return pay_factor + equipment_factor


# ---------------------------------------------------------------------------
# 5.11 商业动态
# ---------------------------------------------------------------------------


def calculate_commerce_dynamics(
    commerce: CommerceData,
    taxation: TaxationData,
    happiness: Decimal,
) -> tuple[Decimal, Decimal]:
    """计算商户变动和繁荣度变动。

    Returns:
        (merchant_change, prosperity_change)
    """
    tax_pressure = max(_ZERO, _ONE - taxation.commercial_tax_rate * Decimal("3"))

    merchant_change = (
        commerce.merchant_households
        * MERCHANT_MIGRATION_SENSITIVITY
        * (happiness - _HALF)
        * tax_pressure
    )

    prosperity_change = (happiness - commerce.market_prosperity) * PROSPERITY_ADJUSTMENT_RATE

    return merchant_change, prosperity_change


# ---------------------------------------------------------------------------
# 5.12 财政平衡
# ---------------------------------------------------------------------------


def calculate_fiscal_balance(
    administration: AdministrationData,
    military_upkeep: Decimal,
    total_revenue: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
    """计算财政平衡。

    Returns:
        (official_salary_cost, infrastructure_cost, court_levy_cost,
         total_expenditure, fiscal_surplus)
    """
    official_salary_cost = administration.official_count * administration.official_salary
    infrastructure_cost = (
        administration.infrastructure_maintenance_rate * administration.infrastructure_value
    )
    court_levy_cost = administration.court_levy_amount

    total_expenditure = (
        military_upkeep + official_salary_cost + infrastructure_cost + court_levy_cost
    )
    fiscal_surplus = total_revenue - total_expenditure

    return (
        official_salary_cost,
        infrastructure_cost,
        court_levy_cost,
        total_expenditure,
        fiscal_surplus,
    )


# ---------------------------------------------------------------------------
# 5.13 国库分配
# ---------------------------------------------------------------------------


def calculate_treasury_distribution(
    fiscal_surplus: Decimal,
    tribute_rate: Decimal,
) -> tuple[Decimal, Decimal]:
    """计算地方/国库财政分配。

    Returns:
        (local_change, imperial_tribute)
    """
    if fiscal_surplus > _ZERO:
        imperial_tribute = fiscal_surplus * tribute_rate
        local_change = fiscal_surplus - imperial_tribute
    else:
        local_change = fiscal_surplus
        imperial_tribute = _ZERO

    return local_change, imperial_tribute
