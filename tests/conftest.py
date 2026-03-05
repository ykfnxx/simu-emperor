"""共享测试 fixtures + 工厂函数。"""

from decimal import Decimal
from pathlib import Path
import asyncio

import pytest

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


@pytest.fixture
async def event_bus_cleanup():
    """
    EventBus 专用清理 fixture

    只在使用真实 EventBus 的测试中使用此 fixture。
    自动清理后台任务，防止测试挂起。
    """
    # 将在测试 yield 后执行清理
    yield
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            pending = asyncio.all_tasks(loop)
            current = asyncio.current_task(loop)
            background_tasks = [t for t in pending if t != current and not t.done()]

            if background_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*background_tasks, return_exceptions=True), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    for task in background_tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*background_tasks, return_exceptions=True)
    except RuntimeError:
        pass


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
        "market_prosperity": Decimal("0.7"),
    }
    defaults.update(overrides)
    return CommerceData(**defaults)


def make_trade(**overrides) -> TradeData:
    defaults = {
        "trade_volume": Decimal("10000"),
        "trade_route_quality": Decimal("0.8"),
    }
    defaults.update(overrides)
    return TradeData(**defaults)


def make_military(**overrides) -> MilitaryData:
    defaults = {
        "garrison_size": Decimal("5000"),
        "equipment_level": Decimal("0.6"),
        "morale": Decimal("0.8"),
        "upkeep_per_soldier": Decimal("6.0"),
        "upkeep": Decimal("0"),
    }
    defaults.update(overrides)
    return MilitaryData(**defaults)


def make_taxation(**overrides) -> TaxationData:
    defaults = {
        "land_tax_rate": Decimal("0.03"),
        "commercial_tax_rate": Decimal("0.10"),
        "tariff_rate": Decimal("0.05"),
    }
    defaults.update(overrides)
    return TaxationData(**defaults)


def make_consumption(**overrides) -> ConsumptionData:
    defaults = {
        "civilian_grain_per_capita": Decimal("3.0"),
        "military_grain_per_soldier": Decimal("5.0"),
    }
    defaults.update(overrides)
    return ConsumptionData(**defaults)


def make_administration(**overrides) -> AdministrationData:
    defaults = {
        "official_count": Decimal("200"),
        "official_salary": Decimal("60"),
        "infrastructure_maintenance_rate": Decimal("0.02"),
        "infrastructure_value": Decimal("500000"),
        "court_levy_amount": Decimal("0"),
    }
    defaults.update(overrides)
    return AdministrationData(**defaults)


def make_province(
    province_id: str = "jiangnan", name: str = "江南", **overrides
) -> ProvinceBaseData:
    defaults = {
        "province_id": province_id,
        "name": name,
        "population": make_population(),
        "agriculture": make_agriculture(),
        "commerce": make_commerce(),
        "trade": make_trade(),
        "military": make_military(),
        "taxation": make_taxation(),
        "consumption": make_consumption(),
        "administration": make_administration(),
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
        "tribute_rate": Decimal("0.30"),
        "provinces": [make_province()],
    }
    defaults.update(overrides)
    return NationalBaseData(**defaults)


def make_zhili_province(**overrides) -> ProvinceBaseData:
    """直隶省初始数据工厂，使用 eco_system_design.md 中定义的均衡初始值。"""
    defaults = {
        "province_id": "zhili",
        "name": "直隶",
        "population": PopulationData(
            total=Decimal("2600000"),
            growth_rate=Decimal("0.002"),
            labor_ratio=Decimal("0.55"),
            happiness=Decimal("0.70"),
        ),
        "agriculture": AgricultureData(
            crops=[
                CropData(
                    crop_type=CropType.WHEAT,
                    area_mu=Decimal("5500000"),
                    yield_per_mu=Decimal("1.3"),
                ),
                CropData(
                    crop_type=CropType.MILLET,
                    area_mu=Decimal("2500000"),
                    yield_per_mu=Decimal("1.1"),
                ),
            ],
            irrigation_level=Decimal("0.60"),
        ),
        "commerce": CommerceData(
            merchant_households=Decimal("3500"),
            market_prosperity=Decimal("0.60"),
        ),
        "trade": TradeData(
            trade_volume=Decimal("80000"),
            trade_route_quality=Decimal("0.65"),
        ),
        "military": MilitaryData(
            garrison_size=Decimal("30000"),
            equipment_level=Decimal("0.50"),
            morale=Decimal("0.70"),
            upkeep_per_soldier=Decimal("6.0"),
            upkeep=Decimal("0"),
        ),
        "taxation": TaxationData(
            land_tax_rate=Decimal("0.03"),
            commercial_tax_rate=Decimal("0.10"),
            tariff_rate=Decimal("0.05"),
        ),
        "consumption": ConsumptionData(
            civilian_grain_per_capita=Decimal("3.0"),
            military_grain_per_soldier=Decimal("5.0"),
        ),
        "administration": AdministrationData(
            official_count=Decimal("200"),
            official_salary=Decimal("60"),
            infrastructure_maintenance_rate=Decimal("0.02"),
            infrastructure_value=Decimal("500000"),
            court_levy_amount=Decimal("0"),
        ),
        "granary_stock": Decimal("1200000"),
        "local_treasury": Decimal("80000"),
    }
    defaults.update(overrides)
    return ProvinceBaseData(**defaults)


@pytest.fixture
def sample_province() -> ProvinceBaseData:
    return make_province()


@pytest.fixture
def sample_national_data() -> NationalBaseData:
    return make_national_data()


@pytest.fixture
def zhili_province() -> ProvinceBaseData:
    return make_zhili_province()


@pytest.fixture
def fixtures_dir() -> Path:
    """返回测试 fixtures 目录路径"""
    return Path(__file__).parent / "fixtures"
