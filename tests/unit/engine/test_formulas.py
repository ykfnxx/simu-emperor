"""经济公式单元测试：每个公式的默认场景、边界条件、极端情况验证。"""

from decimal import Decimal

from simu_emperor.engine.formulas import (
    FAMINE_THRESHOLD,
    GRAIN_TO_SILVER_RATE,
    IRRIGATION_BASE_FACTOR,
    MAX_GROWTH_RATE,
    STARVATION_MORTALITY_RATE,
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
from simu_emperor.engine.models.base_data import (
    AdministrationData,
    AgricultureData,
    CommerceData,
    ConsumptionData,
    CropData,
    CropType,
    MilitaryData,
    PopulationData,
    TaxationData,
    TradeData,
)

from tests.conftest import make_zhili_province


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _zhili():
    """返回直隶初始数据。"""
    return make_zhili_province()


# ---------------------------------------------------------------------------
# 5.1 calculate_food_production
# ---------------------------------------------------------------------------


class TestFoodProduction:
    def test_zhili_default(self):
        """直隶默认产量 = 8,316,000 石。"""
        p = _zhili()
        result = calculate_food_production(p.agriculture, p.population)
        assert result == Decimal("8316000")

    def test_no_crops(self):
        agri = AgricultureData(crops=[], irrigation_level=Decimal("0.6"))
        pop = PopulationData(
            total=Decimal("100000"),
            growth_rate=Decimal("0.01"),
            labor_ratio=Decimal("0.5"),
            happiness=Decimal("0.5"),
        )
        assert calculate_food_production(agri, pop) == Decimal("0")

    def test_labor_shortage(self):
        """劳动力不足时产量按比例下降。"""
        agri = AgricultureData(
            crops=[
                CropData(
                    crop_type=CropType.WHEAT,
                    area_mu=Decimal("1000000"),
                    yield_per_mu=Decimal("1.0"),
                )
            ],
            irrigation_level=Decimal("0"),
        )
        # required_labor = 1000000 × 0.05 = 50000
        # available_labor = 10000 × 0.5 = 5000 → modifier = 5000/50000 = 0.1
        pop = PopulationData(
            total=Decimal("10000"),
            growth_rate=Decimal("0.01"),
            labor_ratio=Decimal("0.5"),
            happiness=Decimal("0.5"),
        )
        result = calculate_food_production(agri, pop)
        # raw = 1000000, irrigation = 0.6+0 = 0.6, labor = 0.1
        expected = Decimal("1000000") * Decimal("0.6") * Decimal("0.1")
        assert result == expected

    def test_full_irrigation(self):
        """满灌溉 modifier = 1.0。"""
        agri = AgricultureData(
            crops=[
                CropData(
                    crop_type=CropType.WHEAT, area_mu=Decimal("100"), yield_per_mu=Decimal("2")
                )
            ],
            irrigation_level=Decimal("1"),
        )
        pop = PopulationData(
            total=Decimal("1000000"),
            growth_rate=Decimal("0"),
            labor_ratio=Decimal("1"),
            happiness=Decimal("0.5"),
        )
        result = calculate_food_production(agri, pop)
        # raw=200, irrigation=0.6+0.4=1.0, labor充足=1.0
        assert result == Decimal("200")

    def test_zero_irrigation(self):
        """零灌溉 modifier = 0.6。"""
        agri = AgricultureData(
            crops=[
                CropData(
                    crop_type=CropType.RICE, area_mu=Decimal("1000"), yield_per_mu=Decimal("3")
                )
            ],
            irrigation_level=Decimal("0"),
        )
        pop = PopulationData(
            total=Decimal("1000000"),
            growth_rate=Decimal("0"),
            labor_ratio=Decimal("1"),
            happiness=Decimal("0.5"),
        )
        result = calculate_food_production(agri, pop)
        assert result == Decimal("3000") * IRRIGATION_BASE_FACTOR


# ---------------------------------------------------------------------------
# 5.2 calculate_food_demand
# ---------------------------------------------------------------------------


class TestFoodDemand:
    def test_zhili_default(self):
        """直隶默认需求：civilian=7,800,000, military=150,000, total=7,950,000。"""
        p = _zhili()
        civ, mil, total = calculate_food_demand(p.population, p.consumption, p.military)
        assert civ == Decimal("7800000")
        assert mil == Decimal("150000")
        assert total == Decimal("7950000")

    def test_zero_population(self):
        pop = PopulationData(
            total=Decimal("0"),
            growth_rate=Decimal("0"),
            labor_ratio=Decimal("0.5"),
            happiness=Decimal("0.5"),
        )
        cons = ConsumptionData()
        mil = MilitaryData(
            garrison_size=Decimal("0"), equipment_level=Decimal("0.5"), morale=Decimal("0.5")
        )
        civ, military, total = calculate_food_demand(pop, cons, mil)
        assert civ == Decimal("0")
        assert military == Decimal("0")
        assert total == Decimal("0")


# ---------------------------------------------------------------------------
# 5.3 calculate_food_surplus_and_granary
# ---------------------------------------------------------------------------


class TestFoodSurplusAndGranary:
    def test_zhili_default(self):
        """直隶默认盈余 = 366,000 石。"""
        surplus, new_granary, change = calculate_food_surplus_and_granary(
            Decimal("8316000"),
            Decimal("7950000"),
            Decimal("1200000"),
        )
        assert surplus == Decimal("366000")
        assert new_granary == Decimal("1566000")
        assert change == Decimal("366000")

    def test_deficit_drains_granary(self):
        surplus, new_granary, change = calculate_food_surplus_and_granary(
            Decimal("100"),
            Decimal("300"),
            Decimal("500"),
        )
        assert surplus == Decimal("-200")
        assert new_granary == Decimal("300")
        assert change == Decimal("-200")

    def test_granary_floor_at_zero(self):
        """粮仓不能为负。"""
        surplus, new_granary, change = calculate_food_surplus_and_granary(
            Decimal("0"),
            Decimal("1000"),
            Decimal("500"),
        )
        assert surplus == Decimal("-1000")
        assert new_granary == Decimal("0")
        assert change == Decimal("-500")  # 只能减到0


# ---------------------------------------------------------------------------
# 5.4 calculate_land_tax_revenue
# ---------------------------------------------------------------------------


class TestLandTaxRevenue:
    def test_zhili_default(self):
        """直隶默认田赋 = 249,480 两。"""
        result = calculate_land_tax_revenue(
            Decimal("8316000"),
            TaxationData(),
            Decimal("1.0"),
        )
        assert result == Decimal("249480.00")

    def test_with_tax_modifier(self):
        result = calculate_land_tax_revenue(
            Decimal("1000000"),
            TaxationData(land_tax_rate=Decimal("0.05")),
            Decimal("1.5"),
        )
        expected = Decimal("1000000") * Decimal("0.05") * GRAIN_TO_SILVER_RATE * Decimal("1.5")
        assert result == expected


# ---------------------------------------------------------------------------
# 5.5 calculate_commercial_tax_revenue
# ---------------------------------------------------------------------------


class TestCommercialTaxRevenue:
    def test_zhili_default(self):
        """直隶默认商税 = 10,500 两。"""
        p = _zhili()
        result = calculate_commercial_tax_revenue(p.commerce, p.taxation, Decimal("1.0"))
        assert result == Decimal("10500.00")

    def test_zero_prosperity(self):
        commerce = CommerceData(merchant_households=Decimal("1000"), market_prosperity=Decimal("0"))
        result = calculate_commercial_tax_revenue(commerce, TaxationData(), Decimal("1.0"))
        assert result == Decimal("0")


# ---------------------------------------------------------------------------
# 5.6 calculate_trade_tariff_revenue
# ---------------------------------------------------------------------------


class TestTradeTariffRevenue:
    def test_zhili_default(self):
        """直隶默认关税 = 2,600 两。"""
        p = _zhili()
        result = calculate_trade_tariff_revenue(p.trade, p.taxation)
        assert result == Decimal("2600.00")

    def test_zero_volume(self):
        trade = TradeData(trade_volume=Decimal("0"), trade_route_quality=Decimal("1"))
        result = calculate_trade_tariff_revenue(trade, TaxationData())
        assert result == Decimal("0")


# ---------------------------------------------------------------------------
# 5.7 calculate_military_upkeep
# ---------------------------------------------------------------------------


class TestMilitaryUpkeep:
    def test_zhili_default(self):
        """直隶默认军费 = 225,000 两。"""
        p = _zhili()
        result = calculate_military_upkeep(p.military)
        assert result == Decimal("225000.0")

    def test_zero_garrison(self):
        mil = MilitaryData(
            garrison_size=Decimal("0"), equipment_level=Decimal("1"), morale=Decimal("0.5")
        )
        assert calculate_military_upkeep(mil) == Decimal("0")

    def test_max_equipment(self):
        """equipment_level=1 时军费增加 50%。"""
        mil = MilitaryData(
            garrison_size=Decimal("1000"),
            equipment_level=Decimal("1"),
            morale=Decimal("0.5"),
            upkeep_per_soldier=Decimal("10"),
        )
        # 1000 × 10 × (1 + 0.5 × 1) = 15000
        assert calculate_military_upkeep(mil) == Decimal("15000.0")


# ---------------------------------------------------------------------------
# 5.8 calculate_happiness_change
# ---------------------------------------------------------------------------


class TestHappinessChange:
    def test_zhili_default(self):
        """直隶默认幸福度变化约 +0.02。"""
        p = _zhili()
        food_prod = Decimal("8316000")
        food_demand = Decimal("7950000")
        fiscal_surplus = Decimal("15580")
        total_revenue = Decimal("262580")
        result = calculate_happiness_change(
            food_prod,
            food_demand,
            p.taxation,
            p.military,
            fiscal_surplus,
            total_revenue,
        )
        # food_factor: ratio=1.046, >=1.0 but <1.05 → +0.005
        # tax_factor: (0.03+0.10)/2=0.065 < 0.10 → +0.005
        # security_factor: (0.70-0.50)×0.05 = +0.01
        # fiscal_factor: min(15580/262580, 0.2)×0.02 ≈ +0.001
        assert result > Decimal("0.01")
        assert result < Decimal("0.03")

    def test_famine_negative(self):
        """粮食严重短缺 ratio<0.9 → 幸福度大幅下降。"""
        result = calculate_happiness_change(
            food_production=Decimal("700000"),
            food_demand_total=Decimal("1000000"),  # ratio=0.7
            taxation=TaxationData(),
            military=MilitaryData(
                garrison_size=Decimal("0"), equipment_level=Decimal("0.5"), morale=Decimal("0.5")
            ),
            fiscal_surplus=Decimal("0"),
            total_revenue=Decimal("1000"),
        )
        assert result < Decimal("0")

    def test_zero_demand(self):
        """需求为零 → food_factor = +0.01。"""
        result = calculate_happiness_change(
            food_production=Decimal("100"),
            food_demand_total=Decimal("0"),
            taxation=TaxationData(),
            military=MilitaryData(
                garrison_size=Decimal("0"), equipment_level=Decimal("0.5"), morale=Decimal("0.5")
            ),
            fiscal_surplus=Decimal("0"),
            total_revenue=Decimal("0"),
        )
        assert result > Decimal("0")

    def test_high_tax_burden(self):
        """高税率 → 负 tax_factor。"""
        result = calculate_happiness_change(
            food_production=Decimal("1000"),
            food_demand_total=Decimal("500"),  # ratio=2.0, food_factor=+0.01
            taxation=TaxationData(
                land_tax_rate=Decimal("0.30"), commercial_tax_rate=Decimal("0.30")
            ),
            military=MilitaryData(
                garrison_size=Decimal("0"), equipment_level=Decimal("0.5"), morale=Decimal("0.5")
            ),
            fiscal_surplus=Decimal("0"),
            total_revenue=Decimal("0"),
        )
        # tax_factor: (0.30+0.30)/2=0.30 > 0.10 → -(0.30-0.10)×0.5 = -0.10
        # food_factor +0.01, security=0, fiscal=0 → net < 0
        assert result < Decimal("0")


# ---------------------------------------------------------------------------
# 5.9 calculate_population_change
# ---------------------------------------------------------------------------


class TestPopulationChange:
    def test_zhili_default(self):
        """直隶默认人口增长 = 7,280 人/年。"""
        p = _zhili()
        result = calculate_population_change(p.population, Decimal("8316000"), Decimal("7950000"))
        # ratio=1.046, food_modifier=1.0, happiness_modifier=0.7×2=1.4
        # effective=0.002×1.4×1.0=0.0028 → 2600000×0.0028=7280
        assert result == Decimal("7280.0")

    def test_extreme_famine(self):
        """完全断粮 ratio=0 → 人口损失约 15%。"""
        pop = PopulationData(
            total=Decimal("2600000"),
            growth_rate=Decimal("0.002"),
            labor_ratio=Decimal("0.55"),
            happiness=Decimal("0.70"),
        )
        result = calculate_population_change(pop, Decimal("0"), Decimal("7950000"))
        # ratio=0, food_modifier=0 → natural_change=0
        # starvation = 2600000 × 0.15 × (0.9-0)/0.9 = 2600000 × 0.15 = 390000
        assert result == Decimal("-390000.0")

    def test_moderate_famine(self):
        """ratio=0.8 → 饥荒死亡约 pop × 1.67%。"""
        pop = PopulationData(
            total=Decimal("1000000"),
            growth_rate=Decimal("0.002"),
            labor_ratio=Decimal("0.55"),
            happiness=Decimal("0.50"),
        )
        # demand=1000000, production=800000 → ratio=0.8
        result = calculate_population_change(pop, Decimal("800000"), Decimal("1000000"))
        # natural_change = 0 (food_modifier=0 for ratio<0.9)
        # starvation = 1000000 × 0.15 × (0.9-0.8)/0.9 = 1000000 × 0.15 × 0.111... ≈ 16666.67
        starvation_expected = (
            Decimal("1000000")
            * STARVATION_MORTALITY_RATE
            * (FAMINE_THRESHOLD - Decimal("0.8"))
            / FAMINE_THRESHOLD
        )
        assert result == -starvation_expected

    def test_slight_shortage(self):
        """ratio=0.97 → food_modifier=0.5, 增长减半。"""
        pop = PopulationData(
            total=Decimal("1000000"),
            growth_rate=Decimal("0.004"),
            labor_ratio=Decimal("0.55"),
            happiness=Decimal("0.50"),
        )
        result = calculate_population_change(pop, Decimal("970"), Decimal("1000"))
        # ratio=0.97, food_modifier=0.5, happiness_modifier=0.5×2=1.0
        # effective=0.004×1.0×0.5=0.002
        expected = Decimal("1000000") * Decimal("0.002")
        assert result == expected

    def test_zero_demand(self):
        """需求为零 → 视为充足，正常增长。"""
        pop = PopulationData(
            total=Decimal("1000"),
            growth_rate=Decimal("0.004"),
            labor_ratio=Decimal("0.5"),
            happiness=Decimal("0.50"),
        )
        result = calculate_population_change(pop, Decimal("0"), Decimal("0"))
        # ratio=1.05 (充足), food_modifier=1.0, happiness_modifier=1.0
        expected = Decimal("1000") * Decimal("0.004")
        assert result == expected

    def test_growth_rate_capped(self):
        """增长率不能超过 MAX_GROWTH_RATE。"""
        pop = PopulationData(
            total=Decimal("1000000"),
            growth_rate=Decimal("0.05"),
            labor_ratio=Decimal("0.5"),
            happiness=Decimal("0.95"),
        )
        result = calculate_population_change(pop, Decimal("2000"), Decimal("1000"))
        # effective = 0.05 × 1.9 × 1.0 = 0.095 → clamped to 0.005
        expected = Decimal("1000000") * MAX_GROWTH_RATE
        assert result == expected


# ---------------------------------------------------------------------------
# 5.10 calculate_morale_change
# ---------------------------------------------------------------------------


class TestMoraleChange:
    def test_surplus_good_equipment(self):
        """有盈余 + 好装备 → 士气上升。"""
        mil = MilitaryData(
            garrison_size=Decimal("1000"),
            equipment_level=Decimal("0.8"),
            morale=Decimal("0.5"),
        )
        result = calculate_morale_change(mil, Decimal("1000"), Decimal("5000"))
        # pay_factor=+0.01, equipment_factor=(0.8-0.5)×0.02=+0.006
        assert result == Decimal("0.016")

    def test_deficit_poor_equipment(self):
        """赤字 + 差装备 → 士气下降。"""
        mil = MilitaryData(
            garrison_size=Decimal("1000"),
            equipment_level=Decimal("0.2"),
            morale=Decimal("0.5"),
        )
        result = calculate_morale_change(mil, Decimal("-5000"), Decimal("5000"))
        # pay_factor = -0.03 × min(1, 5000/5000) = -0.03
        # equipment_factor = (0.2-0.5)×0.02 = -0.006
        assert result == Decimal("-0.036")

    def test_zero_upkeep(self):
        """军费为零 → pay_factor 为 0（无军队无欠饷）。"""
        mil = MilitaryData(
            garrison_size=Decimal("0"),
            equipment_level=Decimal("0.5"),
            morale=Decimal("0.5"),
        )
        result = calculate_morale_change(mil, Decimal("-100"), Decimal("0"))
        # pay_factor=0, equipment_factor=0
        assert result == Decimal("0")


# ---------------------------------------------------------------------------
# 5.11 calculate_commerce_dynamics
# ---------------------------------------------------------------------------


class TestCommerceDynamics:
    def test_zhili_default(self):
        """直隶默认：商户+9.8, 繁荣度+0.005。"""
        p = _zhili()
        merchant_change, prosperity_change = calculate_commerce_dynamics(
            p.commerce,
            p.taxation,
            p.population.happiness,
        )
        # tax_pressure = max(0, 1-0.10×3) = 0.7
        # merchant_change = 3500 × 0.02 × (0.7-0.5) × 0.7 = 9.8
        assert merchant_change == Decimal("9.800")
        # prosperity_change = (0.7-0.6) × 0.05 = 0.005
        assert prosperity_change == Decimal("0.005")

    def test_high_tax_kills_migration(self):
        """商税>=0.34 → tax_pressure=0, 商户不受税率驱动增长。"""
        commerce = CommerceData(
            merchant_households=Decimal("1000"), market_prosperity=Decimal("0.5")
        )
        taxation = TaxationData(commercial_tax_rate=Decimal("0.34"))
        merchant_change, _ = calculate_commerce_dynamics(
            commerce,
            taxation,
            Decimal("0.8"),
        )
        assert merchant_change == Decimal("0")

    def test_low_happiness_drives_exodus(self):
        """低幸福度 → 商户外流。"""
        commerce = CommerceData(
            merchant_households=Decimal("1000"), market_prosperity=Decimal("0.5")
        )
        taxation = TaxationData(commercial_tax_rate=Decimal("0.05"))
        merchant_change, _ = calculate_commerce_dynamics(
            commerce,
            taxation,
            Decimal("0.3"),
        )
        assert merchant_change < Decimal("0")


# ---------------------------------------------------------------------------
# 5.12 calculate_fiscal_balance
# ---------------------------------------------------------------------------


class TestFiscalBalance:
    def test_zhili_default(self):
        """直隶默认：支出=247,000, 盈余=15,580。"""
        p = _zhili()
        salary, infra, levy, total_exp, surplus = calculate_fiscal_balance(
            p.administration,
            Decimal("225000"),
            Decimal("262580"),
        )
        assert salary == Decimal("12000")
        assert infra == Decimal("10000.00")
        assert levy == Decimal("0")
        assert total_exp == Decimal("247000.00")
        assert surplus == Decimal("15580.00")

    def test_deficit(self):
        admin = AdministrationData(
            official_count=Decimal("500"),
            official_salary=Decimal("100"),
            infrastructure_maintenance_rate=Decimal("0.05"),
            infrastructure_value=Decimal("1000000"),
            court_levy_amount=Decimal("10000"),
        )
        _, _, _, total_exp, surplus = calculate_fiscal_balance(
            admin, Decimal("100000"), Decimal("50000")
        )
        # salary=50000, infra=50000, levy=10000, upkeep=100000 → total=210000
        assert total_exp == Decimal("210000")
        assert surplus == Decimal("-160000")


# ---------------------------------------------------------------------------
# 5.13 calculate_treasury_distribution
# ---------------------------------------------------------------------------


class TestTreasuryDistribution:
    def test_zhili_default(self):
        """直隶默认：local=10,906, tribute=4,674。"""
        local, tribute = calculate_treasury_distribution(Decimal("15580"), Decimal("0.30"))
        assert tribute == Decimal("4674.0")
        assert local == Decimal("10906.0")

    def test_deficit_no_tribute(self):
        """亏损时 tribute=0，地方承担全部亏损。"""
        local, tribute = calculate_treasury_distribution(Decimal("-5000"), Decimal("0.30"))
        assert tribute == Decimal("0")
        assert local == Decimal("-5000")

    def test_zero_surplus(self):
        """刚好收支平衡。"""
        local, tribute = calculate_treasury_distribution(Decimal("0"), Decimal("0.30"))
        assert tribute == Decimal("0")
        assert local == Decimal("0")
