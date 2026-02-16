"""共享测试 fixtures + 工厂函数。"""

from decimal import Decimal

import pytest

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


def make_population(**overrides) -> PopulationData:
    defaults = {
        "total": Decimal("100000"),
        "growth_rate": Decimal("0.02"),
        "labor_ratio": Decimal("0.6"),
        "happiness": Decimal("0.7"),
    }
    defaults.update(overrides)
    return PopulationData(**defaults)


def make_agriculture(**overrides) -> AgricultureData:
    defaults = {
        "crops": [
            CropData(crop_type=CropType.RICE, area_mu=Decimal("50000"), yield_per_mu=Decimal("3")),
        ],
        "irrigation_level": Decimal("0.6"),
    }
    defaults.update(overrides)
    return AgricultureData(**defaults)


def make_commerce(**overrides) -> CommerceData:
    defaults = {
        "merchant_households": Decimal("500"),
        "tax_rate": Decimal("0.1"),
        "market_prosperity": Decimal("0.7"),
    }
    defaults.update(overrides)
    return CommerceData(**defaults)


def make_trade(**overrides) -> TradeData:
    defaults = {
        "trade_volume": Decimal("10000"),
        "tariff_rate": Decimal("0.05"),
        "trade_route_quality": Decimal("0.8"),
    }
    defaults.update(overrides)
    return TradeData(**defaults)


def make_military(**overrides) -> MilitaryData:
    defaults = {
        "garrison_size": Decimal("5000"),
        "equipment_level": Decimal("0.6"),
        "morale": Decimal("0.8"),
        "upkeep": Decimal("10000"),
    }
    defaults.update(overrides)
    return MilitaryData(**defaults)


def make_province(province_id: str = "jiangnan", name: str = "江南", **overrides) -> ProvinceBaseData:
    defaults = {
        "province_id": province_id,
        "name": name,
        "population": make_population(),
        "agriculture": make_agriculture(),
        "commerce": make_commerce(),
        "trade": make_trade(),
        "military": make_military(),
        "granary_stock": Decimal("50000"),
        "local_treasury": Decimal("20000"),
    }
    defaults.update(overrides)
    return ProvinceBaseData(**defaults)


def make_national_data(**overrides) -> NationalBaseData:
    defaults = {
        "turn": 1,
        "imperial_treasury": Decimal("500000"),
        "national_tax_modifier": Decimal("1.0"),
        "provinces": [make_province()],
    }
    defaults.update(overrides)
    return NationalBaseData(**defaults)


@pytest.fixture
def sample_province() -> ProvinceBaseData:
    return make_province()


@pytest.fixture
def sample_national_data() -> NationalBaseData:
    return make_national_data()
