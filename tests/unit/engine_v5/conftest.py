"""Shared fixtures for engine_v5 tests."""

import pytest
from decimal import Decimal

from simu_emperor.engine_v5.models.base_data import ProvinceData, NationData


@pytest.fixture
def sample_province():
    """Create a sample ProvinceData for testing."""
    return ProvinceData(
        province_id="zhili",
        name="直隶",
        production_value=Decimal("100000"),
        population=Decimal("50000"),
        fixed_expenditure=Decimal("5000"),
        stockpile=Decimal("20000"),
    )


@pytest.fixture
def sample_nation(sample_province):
    """Create a sample NationData for testing."""
    provinces = {
        sample_province.province_id: sample_province,
        "shanxi": ProvinceData(
            province_id="shanxi",
            name="山西",
            production_value=Decimal("80000"),
            population=Decimal("40000"),
            fixed_expenditure=Decimal("4000"),
            stockpile=Decimal("15000"),
        ),
    }
    return NationData(
        turn=0,
        base_tax_rate=Decimal("0.10"),
        tribute_rate=Decimal("0.8"),
        imperial_treasury=Decimal("100000"),
        provinces=provinces,
    )
