"""共享测试 fixtures + 工厂函数 (V4)."""

from decimal import Decimal
from pathlib import Path
import asyncio

import pytest

from simu_emperor.engine.models.base_data import (
    ProvinceData,
    NationData,
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


def make_province(
    province_id: str = "zhili", name: str = "直隶", **overrides
) -> ProvinceData:
    """创建省份数据 (V4)."""
    defaults = {
        "province_id": province_id,
        "name": name,
        "production_value": Decimal("100000"),
        "population": Decimal("50000"),
        "fixed_expenditure": Decimal("5000"),
        "stockpile": Decimal("20000"),
    }
    defaults.update(overrides)
    return ProvinceData(**defaults)


def make_national_data(**overrides) -> NationData:
    """创建国家数据 (V4)."""
    defaults = {
        "turn": 0,
        "base_tax_rate": Decimal("0.10"),
        "tribute_rate": Decimal("0.8"),
        "imperial_treasury": Decimal("100000"),
        "provinces": {},
    }
    defaults.update(overrides)
    return NationData(**defaults)


@pytest.fixture
def sample_province() -> ProvinceData:
    return make_province()


@pytest.fixture
def sample_national_data() -> NationData:
    return make_national_data()


@pytest.fixture
def fixtures_dir() -> Path:
    """返回测试 fixtures 目录路径"""
    return Path(__file__).parent / "fixtures"
