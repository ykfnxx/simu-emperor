"""base_data 模型单元测试：Pydantic 模型验证、序列化往返。"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from simu_emperor.engine.models.base_data import (
    AgricultureData,
    CommerceData,
    CropData,
    CropType,
    MilitaryData,
    NationalBaseData,
    PopulationData,
    ProvinceBaseData,
    TradeData,
)

from tests.conftest import make_national_data, make_province


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
                CropData(crop_type=CropType.RICE, area_mu=Decimal("30000"), yield_per_mu=Decimal("3")),
                CropData(crop_type=CropType.TEA, area_mu=Decimal("5000"), yield_per_mu=Decimal("1")),
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
            tax_rate=Decimal("0.1"),
            market_prosperity=Decimal("0.7"),
        )
        assert commerce.merchant_households == Decimal("500")

    def test_tax_rate_boundary(self):
        commerce = CommerceData(
            merchant_households=Decimal("0"),
            tax_rate=Decimal("0"),
            market_prosperity=Decimal("0"),
        )
        assert commerce.tax_rate == Decimal("0")


class TestTradeData:
    def test_valid_creation(self):
        trade = TradeData(
            trade_volume=Decimal("10000"),
            tariff_rate=Decimal("0.05"),
            trade_route_quality=Decimal("0.8"),
        )
        assert trade.trade_volume == Decimal("10000")


class TestMilitaryData:
    def test_valid_creation(self):
        mil = MilitaryData(
            garrison_size=Decimal("5000"),
            equipment_level=Decimal("0.6"),
            morale=Decimal("0.8"),
            upkeep=Decimal("10000"),
        )
        assert mil.garrison_size == Decimal("5000")

    def test_morale_out_of_range(self):
        with pytest.raises(ValidationError):
            MilitaryData(
                garrison_size=Decimal("5000"),
                equipment_level=Decimal("0.6"),
                morale=Decimal("1.1"),
                upkeep=Decimal("10000"),
            )


class TestProvinceBaseData:
    def test_factory_creation(self):
        province = make_province()
        assert province.province_id == "jiangnan"
        assert province.name == "江南"
        assert province.population.total == Decimal("100000")

    def test_factory_override(self):
        province = make_province(province_id="xibei", name="西北", granary_stock=Decimal("0"))
        assert province.province_id == "xibei"
        assert province.granary_stock == Decimal("0")

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
