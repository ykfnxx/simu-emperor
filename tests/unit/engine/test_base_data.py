"""base_data 模型单元测试：Pydantic 模型验证、序列化往返。"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from simu_emperor.engine.models.base_data import (
    AdministrationData,
    AgricultureData,
    CommerceData,
    ConsumptionData,
    CropData,
    CropType,
    MilitaryData,
    NationalBaseData,
    PopulationData,
    ProvinceBaseData,
    TaxationData,
    TradeData,
)
from simu_emperor.engine.models.metrics import (
    NationalTurnMetrics,
    ProvinceTurnMetrics,
)

from tests.conftest import (
    make_national_data,
    make_province,
    make_zhili_province,
)


class TestCropType:
    def test_enum_values(self):
        assert CropType.RICE == "rice"
        assert CropType.WHEAT == "wheat"
        assert CropType.MILLET == "millet"
        assert CropType.TEA == "tea"
        assert CropType.SILK_MULBERRY == "silk_mulberry"

    def test_enum_from_string(self):
        assert CropType("rice") is CropType.RICE


class TestPopulationData:
    def test_valid_creation(self):
        pop = PopulationData(
            total=Decimal("100000"),
            growth_rate=Decimal("0.02"),
            labor_ratio=Decimal("0.6"),
            happiness=Decimal("0.7"),
        )
        assert pop.total == Decimal("100000")
        assert pop.happiness == Decimal("0.7")

    def test_negative_total_rejected(self):
        with pytest.raises(ValidationError):
            PopulationData(
                total=Decimal("-1"),
                growth_rate=Decimal("0.02"),
                labor_ratio=Decimal("0.6"),
                happiness=Decimal("0.7"),
            )

    def test_happiness_out_of_range(self):
        with pytest.raises(ValidationError):
            PopulationData(
                total=Decimal("100000"),
                growth_rate=Decimal("0.02"),
                labor_ratio=Decimal("0.6"),
                happiness=Decimal("1.5"),
            )

    def test_labor_ratio_boundary(self):
        pop = PopulationData(
            total=Decimal("0"),
            growth_rate=Decimal("-0.01"),
            labor_ratio=Decimal("0"),
            happiness=Decimal("1"),
        )
        assert pop.labor_ratio == Decimal("0")
        assert pop.happiness == Decimal("1")

    def test_negative_growth_rate_allowed(self):
        pop = PopulationData(
            total=Decimal("100000"),
            growth_rate=Decimal("-0.05"),
            labor_ratio=Decimal("0.5"),
            happiness=Decimal("0.3"),
        )
        assert pop.growth_rate == Decimal("-0.05")


class TestCropData:
    def test_valid_creation(self):
        crop = CropData(
            crop_type=CropType.RICE,
            area_mu=Decimal("50000"),
            yield_per_mu=Decimal("3.5"),
        )
        assert crop.crop_type == CropType.RICE
        assert crop.area_mu == Decimal("50000")

    def test_negative_area_rejected(self):
        with pytest.raises(ValidationError):
            CropData(
                crop_type=CropType.WHEAT,
                area_mu=Decimal("-100"),
                yield_per_mu=Decimal("2"),
            )


class TestAgricultureData:
    def test_empty_crops(self):
        agri = AgricultureData(crops=[], irrigation_level=Decimal("0.5"))
        assert agri.crops == []

    def test_multiple_crops(self):
        agri = AgricultureData(
            crops=[
                CropData(
                    crop_type=CropType.RICE, area_mu=Decimal("30000"), yield_per_mu=Decimal("3")
                ),
                CropData(
                    crop_type=CropType.TEA, area_mu=Decimal("5000"), yield_per_mu=Decimal("1")
                ),
            ],
            irrigation_level=Decimal("0.8"),
        )
        assert len(agri.crops) == 2

    def test_irrigation_out_of_range(self):
        with pytest.raises(ValidationError):
            AgricultureData(crops=[], irrigation_level=Decimal("1.1"))


class TestCommerceData:
    def test_valid_creation(self):
        commerce = CommerceData(
            merchant_households=Decimal("500"),
            market_prosperity=Decimal("0.7"),
        )
        assert commerce.merchant_households == Decimal("500")
        assert commerce.market_prosperity == Decimal("0.7")

    def test_prosperity_boundary(self):
        commerce = CommerceData(
            merchant_households=Decimal("0"),
            market_prosperity=Decimal("0"),
        )
        assert commerce.market_prosperity == Decimal("0")

    def test_no_tax_rate_field(self):
        """tax_rate has been moved to TaxationData."""
        assert not hasattr(CommerceData.model_fields, "tax_rate")


class TestTradeData:
    def test_valid_creation(self):
        trade = TradeData(
            trade_volume=Decimal("10000"),
            trade_route_quality=Decimal("0.8"),
        )
        assert trade.trade_volume == Decimal("10000")

    def test_no_tariff_rate_field(self):
        """tariff_rate has been moved to TaxationData."""
        assert "tariff_rate" not in TradeData.model_fields


class TestMilitaryData:
    def test_valid_creation(self):
        mil = MilitaryData(
            garrison_size=Decimal("5000"),
            equipment_level=Decimal("0.6"),
            morale=Decimal("0.8"),
        )
        assert mil.garrison_size == Decimal("5000")
        assert mil.upkeep_per_soldier == Decimal("6.0")
        assert mil.upkeep == Decimal("0")

    def test_explicit_upkeep_per_soldier(self):
        mil = MilitaryData(
            garrison_size=Decimal("5000"),
            equipment_level=Decimal("0.6"),
            morale=Decimal("0.8"),
            upkeep_per_soldier=Decimal("8.0"),
            upkeep=Decimal("50000"),
        )
        assert mil.upkeep_per_soldier == Decimal("8.0")
        assert mil.upkeep == Decimal("50000")

    def test_morale_out_of_range(self):
        with pytest.raises(ValidationError):
            MilitaryData(
                garrison_size=Decimal("5000"),
                equipment_level=Decimal("0.6"),
                morale=Decimal("1.1"),
            )


class TestTaxationData:
    def test_defaults(self):
        tax = TaxationData()
        assert tax.land_tax_rate == Decimal("0.03")
        assert tax.commercial_tax_rate == Decimal("0.10")
        assert tax.tariff_rate == Decimal("0.05")

    def test_custom_rates(self):
        tax = TaxationData(
            land_tax_rate=Decimal("0.05"),
            commercial_tax_rate=Decimal("0.15"),
            tariff_rate=Decimal("0.08"),
        )
        assert tax.land_tax_rate == Decimal("0.05")

    def test_rate_out_of_range(self):
        with pytest.raises(ValidationError):
            TaxationData(land_tax_rate=Decimal("1.5"))

    def test_negative_rate_rejected(self):
        with pytest.raises(ValidationError):
            TaxationData(commercial_tax_rate=Decimal("-0.01"))

    def test_serialization_roundtrip(self):
        tax = TaxationData(land_tax_rate=Decimal("0.07"))
        json_str = tax.model_dump_json()
        restored = TaxationData.model_validate_json(json_str)
        assert restored == tax


class TestConsumptionData:
    def test_defaults(self):
        cons = ConsumptionData()
        assert cons.civilian_grain_per_capita == Decimal("3.0")
        assert cons.military_grain_per_soldier == Decimal("5.0")

    def test_custom_values(self):
        cons = ConsumptionData(
            civilian_grain_per_capita=Decimal("4.0"),
            military_grain_per_soldier=Decimal("6.0"),
        )
        assert cons.civilian_grain_per_capita == Decimal("4.0")

    def test_negative_rejected(self):
        with pytest.raises(ValidationError):
            ConsumptionData(civilian_grain_per_capita=Decimal("-1"))

    def test_serialization_roundtrip(self):
        cons = ConsumptionData(civilian_grain_per_capita=Decimal("2.5"))
        json_str = cons.model_dump_json()
        restored = ConsumptionData.model_validate_json(json_str)
        assert restored == cons


class TestAdministrationData:
    def test_defaults(self):
        admin = AdministrationData()
        assert admin.official_count == Decimal("200")
        assert admin.official_salary == Decimal("60")
        assert admin.infrastructure_maintenance_rate == Decimal("0.02")
        assert admin.infrastructure_value == Decimal("500000")
        assert admin.court_levy_amount == Decimal("0")

    def test_custom_values(self):
        admin = AdministrationData(
            official_count=Decimal("300"),
            court_levy_amount=Decimal("10000"),
        )
        assert admin.official_count == Decimal("300")
        assert admin.court_levy_amount == Decimal("10000")

    def test_maintenance_rate_out_of_range(self):
        with pytest.raises(ValidationError):
            AdministrationData(infrastructure_maintenance_rate=Decimal("1.5"))

    def test_negative_rejected(self):
        with pytest.raises(ValidationError):
            AdministrationData(official_count=Decimal("-1"))

    def test_serialization_roundtrip(self):
        admin = AdministrationData(court_levy_amount=Decimal("5000"))
        json_str = admin.model_dump_json()
        restored = AdministrationData.model_validate_json(json_str)
        assert restored == admin


class TestProvinceBaseData:
    def test_factory_creation(self):
        province = make_province()
        assert province.province_id == "jiangnan"
        assert province.name == "江南"
        assert province.population.total == Decimal("100000")
        assert province.taxation.land_tax_rate == Decimal("0.03")
        assert province.consumption.civilian_grain_per_capita == Decimal("3.0")
        assert province.administration.official_count == Decimal("200")

    def test_factory_override(self):
        province = make_province(province_id="xibei", name="西北", granary_stock=Decimal("0"))
        assert province.province_id == "xibei"
        assert province.granary_stock == Decimal("0")

    def test_default_factory_fields(self):
        """taxation/consumption/administration use default_factory and can be omitted."""
        province = ProvinceBaseData(
            province_id="test",
            name="测试",
            population=PopulationData(
                total=Decimal("1000"),
                growth_rate=Decimal("0"),
                labor_ratio=Decimal("0.5"),
                happiness=Decimal("0.5"),
            ),
            agriculture=AgricultureData(crops=[], irrigation_level=Decimal("0")),
            commerce=CommerceData(merchant_households=Decimal("0"), market_prosperity=Decimal("0")),
            trade=TradeData(trade_volume=Decimal("0"), trade_route_quality=Decimal("0")),
            military=MilitaryData(
                garrison_size=Decimal("0"), equipment_level=Decimal("0"), morale=Decimal("0.5")
            ),
            granary_stock=Decimal("0"),
            local_treasury=Decimal("0"),
        )
        assert province.taxation.land_tax_rate == Decimal("0.03")
        assert province.consumption.civilian_grain_per_capita == Decimal("3.0")
        assert province.administration.official_count == Decimal("200")

    def test_serialization_roundtrip(self):
        province = make_province()
        json_str = province.model_dump_json()
        restored = ProvinceBaseData.model_validate_json(json_str)
        assert restored == province

    def test_dict_roundtrip(self):
        province = make_province()
        data = province.model_dump()
        restored = ProvinceBaseData.model_validate(data)
        assert restored == province


class TestNationalBaseData:
    def test_factory_creation(self):
        national = make_national_data()
        assert national.turn == 1
        assert national.imperial_treasury == Decimal("500000")
        assert national.tribute_rate == Decimal("0.30")
        assert len(national.provinces) == 1

    def test_multiple_provinces(self):
        national = make_national_data(
            provinces=[
                make_province("jiangnan", "江南"),
                make_province("xibei", "西北"),
            ]
        )
        assert len(national.provinces) == 2
        assert national.provinces[1].province_id == "xibei"

    def test_serialization_roundtrip(self):
        national = make_national_data(
            provinces=[
                make_province("jiangnan", "江南"),
                make_province("xibei", "西北"),
            ]
        )
        json_str = national.model_dump_json()
        restored = NationalBaseData.model_validate_json(json_str)
        assert restored == national

    def test_negative_treasury_rejected(self):
        with pytest.raises(ValidationError):
            NationalBaseData(
                turn=1,
                imperial_treasury=Decimal("-100"),
                provinces=[],
            )

    def test_default_tax_modifier(self):
        national = NationalBaseData(
            turn=0,
            imperial_treasury=Decimal("0"),
            provinces=[],
        )
        assert national.national_tax_modifier == Decimal("1.0")

    def test_default_tribute_rate(self):
        national = NationalBaseData(
            turn=0,
            imperial_treasury=Decimal("0"),
            provinces=[],
        )
        assert national.tribute_rate == Decimal("0.30")

    def test_tribute_rate_out_of_range(self):
        with pytest.raises(ValidationError):
            NationalBaseData(
                turn=0,
                imperial_treasury=Decimal("0"),
                tribute_rate=Decimal("1.5"),
                provinces=[],
            )


class TestZhiliProvince:
    def test_zhili_factory(self):
        zhili = make_zhili_province()
        assert zhili.province_id == "zhili"
        assert zhili.name == "直隶"
        assert zhili.population.total == Decimal("2600000")
        assert zhili.military.garrison_size == Decimal("30000")
        assert zhili.military.upkeep == Decimal("0")
        assert zhili.taxation.land_tax_rate == Decimal("0.03")
        assert zhili.granary_stock == Decimal("1200000")

    def test_zhili_serialization_roundtrip(self):
        zhili = make_zhili_province()
        json_str = zhili.model_dump_json()
        restored = ProvinceBaseData.model_validate_json(json_str)
        assert restored == zhili


class TestMetricsModels:
    def test_province_turn_metrics_creation(self):
        metrics = ProvinceTurnMetrics(
            province_id="zhili",
            food_production=Decimal("8316000"),
            food_demand_civilian=Decimal("7800000"),
            food_demand_military=Decimal("150000"),
            food_demand_total=Decimal("7950000"),
            food_surplus=Decimal("366000"),
            granary_change=Decimal("366000"),
            land_tax_revenue=Decimal("249480"),
            commercial_tax_revenue=Decimal("10500"),
            trade_tariff_revenue=Decimal("2600"),
            total_revenue=Decimal("262580"),
            military_upkeep=Decimal("225000"),
            official_salary_cost=Decimal("12000"),
            infrastructure_cost=Decimal("10000"),
            court_levy_cost=Decimal("0"),
            total_expenditure=Decimal("247000"),
            fiscal_surplus=Decimal("15580"),
            population_change=Decimal("7280"),
            happiness_change=Decimal("0.02"),
            treasury_change=Decimal("10906"),
        )
        assert metrics.province_id == "zhili"
        assert metrics.food_production == Decimal("8316000")
        assert metrics.fiscal_surplus == Decimal("15580")

    def test_national_turn_metrics_creation(self):
        province_metrics = ProvinceTurnMetrics(
            province_id="zhili",
            food_production=Decimal("8316000"),
            food_demand_civilian=Decimal("7800000"),
            food_demand_military=Decimal("150000"),
            food_demand_total=Decimal("7950000"),
            food_surplus=Decimal("366000"),
            granary_change=Decimal("366000"),
            land_tax_revenue=Decimal("249480"),
            commercial_tax_revenue=Decimal("10500"),
            trade_tariff_revenue=Decimal("2600"),
            total_revenue=Decimal("262580"),
            military_upkeep=Decimal("225000"),
            official_salary_cost=Decimal("12000"),
            infrastructure_cost=Decimal("10000"),
            court_levy_cost=Decimal("0"),
            total_expenditure=Decimal("247000"),
            fiscal_surplus=Decimal("15580"),
            population_change=Decimal("7280"),
            happiness_change=Decimal("0.02"),
            treasury_change=Decimal("10906"),
        )
        national_metrics = NationalTurnMetrics(
            turn=1,
            province_metrics=[province_metrics],
            imperial_treasury_change=Decimal("4674"),
            tribute_total=Decimal("4674"),
        )
        assert national_metrics.turn == 1
        assert len(national_metrics.province_metrics) == 1
        assert national_metrics.tribute_total == Decimal("4674")

    def test_metrics_serialization_roundtrip(self):
        province_metrics = ProvinceTurnMetrics(
            province_id="zhili",
            food_production=Decimal("8316000"),
            food_demand_civilian=Decimal("7800000"),
            food_demand_military=Decimal("150000"),
            food_demand_total=Decimal("7950000"),
            food_surplus=Decimal("366000"),
            granary_change=Decimal("366000"),
            land_tax_revenue=Decimal("249480"),
            commercial_tax_revenue=Decimal("10500"),
            trade_tariff_revenue=Decimal("2600"),
            total_revenue=Decimal("262580"),
            military_upkeep=Decimal("225000"),
            official_salary_cost=Decimal("12000"),
            infrastructure_cost=Decimal("10000"),
            court_levy_cost=Decimal("0"),
            total_expenditure=Decimal("247000"),
            fiscal_surplus=Decimal("15580"),
            population_change=Decimal("7280"),
            happiness_change=Decimal("0.02"),
            treasury_change=Decimal("10906"),
        )
        national_metrics = NationalTurnMetrics(
            turn=1,
            province_metrics=[province_metrics],
            imperial_treasury_change=Decimal("4674"),
            tribute_total=Decimal("4674"),
        )
        json_str = national_metrics.model_dump_json()
        restored = NationalTurnMetrics.model_validate_json(json_str)
        assert restored == national_metrics
