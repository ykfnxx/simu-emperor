"""Tests for V4 serialization module."""

import pytest

from decimal import Decimal

from simu_emperor.engine.models.base_data import ProvinceData, NationData
from simu_emperor.persistence.serialization import (
    serialize_nation_data,
    deserialize_nation_data,
    serialize_province_data,
    deserialize_province_data,
)


class TestNationDataSerialization:
    """Test NationData serialization."""

    def test_serialize_nation_data(self):
        """Test serializing NationData to JSON."""
        nation = NationData(
            turn=5,
            base_tax_rate=Decimal("0.15"),
            imperial_treasury=Decimal("10000"),
            provinces={
                "zhili": ProvinceData(
                    province_id="zhili",
                    name="直隶",
                    production_value=Decimal("100000"),
                    population=Decimal("50000"),
                    fixed_expenditure=Decimal("5000"),
                    stockpile=Decimal("20000"),
                )
            },
        )

        json_str = serialize_nation_data(nation)

        # Should be valid JSON
        import json

        data = json.loads(json_str)
        assert data["turn"] == 5
        assert data["base_tax_rate"] == "0.15"
        assert data["imperial_treasury"] == "10000"
        assert "provinces" in data
        assert "zhili" in data["provinces"]

    def test_serialize_none_nation(self):
        """Test serializing None NationData."""
        json_str = serialize_nation_data(None)
        assert json_str == "{}"

    def test_deserialize_nation_data(self):
        """Test deserializing JSON to NationData."""
        json_str = """{
            "turn": 5,
            "base_tax_rate": "0.15",
            "tribute_rate": "0.8",
            "fixed_expenditure": "0",
            "imperial_treasury": "10000",
            "provinces": {
                "zhili": {
                    "province_id": "zhili",
                    "name": "直隶",
                    "production_value": "100000",
                    "population": "50000",
                    "fixed_expenditure": "5000",
                    "stockpile": "20000",
                    "base_production_growth": "0.01",
                    "base_population_growth": "0.005",
                    "tax_modifier": "0.0"
                }
            }
        }"""

        nation = deserialize_nation_data(json_str)

        assert nation.turn == 5
        assert nation.base_tax_rate == Decimal("0.15")
        assert nation.imperial_treasury == Decimal("10000")
        assert "zhili" in nation.provinces
        assert nation.provinces["zhili"].production_value == Decimal("100000")
        assert nation.provinces["zhili"].population == Decimal("50000")

    def test_deserialize_empty_json(self):
        """Test deserializing empty JSON returns default NationData."""
        nation = deserialize_nation_data("{}")
        assert nation.turn == 0
        assert nation.provinces == {}

    def test_deserialize_invalid_json_raises(self):
        """Test deserializing invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid NationData JSON"):
            deserialize_nation_data("not valid json")

    def test_round_trip_serialization(self):
        """Test serialize → deserialize preserves data."""
        original = NationData(
            turn=10,
            base_tax_rate=Decimal("0.12"),
            imperial_treasury=Decimal("50000"),
            provinces={
                "shanxi": ProvinceData(
                    province_id="shanxi",
                    name="山西",
                    production_value=Decimal("80000"),
                    population=Decimal("40000"),
                    fixed_expenditure=Decimal("4000"),
                    stockpile=Decimal("15000"),
                )
            },
        )

        json_str = serialize_nation_data(original)
        restored = deserialize_nation_data(json_str)

        assert restored.turn == original.turn
        assert restored.base_tax_rate == original.base_tax_rate
        assert restored.imperial_treasury == original.imperial_treasury
        assert len(restored.provinces) == len(original.provinces)
        assert restored.provinces["shanxi"].production_value == Decimal("80000")
        assert restored.provinces["shanxi"].population == Decimal("40000")


class TestProvinceDataSerialization:
    """Test ProvinceData serialization."""

    def test_serialize_province_data(self):
        """Test serializing ProvinceData to JSON."""
        province = ProvinceData(
            province_id="zhili",
            name="直隶",
            production_value=Decimal("100000"),
            population=Decimal("50000"),
            fixed_expenditure=Decimal("5000"),
            stockpile=Decimal("20000"),
        )

        json_str = serialize_province_data(province)

        # Should be valid JSON
        import json

        data = json.loads(json_str)
        assert data["province_id"] == "zhili"
        assert data["production_value"] == "100000"
        assert data["population"] == "50000"

    def test_deserialize_province_data(self):
        """Test deserializing JSON to ProvinceData."""
        json_str = """{
            "province_id": "zhili",
            "name": "直隶",
            "production_value": "100000",
            "population": "50000",
            "fixed_expenditure": "5000",
            "stockpile": "20000",
            "base_production_growth": "0.01",
            "base_population_growth": "0.005",
            "tax_modifier": "0.0"
        }"""

        province = deserialize_province_data(json_str)

        assert province.province_id == "zhili"
        assert province.name == "直隶"
        assert province.production_value == Decimal("100000")
        assert province.population == Decimal("50000")

    def test_deserialize_empty_province_raises(self):
        """Test deserializing empty JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid ProvinceData JSON"):
            deserialize_province_data("{}")

    def test_province_round_trip(self):
        """Test serialize → deserialize preserves ProvinceData."""
        original = ProvinceData(
            province_id="shanxi",
            name="山西",
            production_value=Decimal("80000"),
            population=Decimal("40000"),
            fixed_expenditure=Decimal("4000"),
            stockpile=Decimal("15000"),
        )

        json_str = serialize_province_data(original)
        restored = deserialize_province_data(json_str)

        assert restored.province_id == original.province_id
        assert restored.production_value == original.production_value
        assert restored.population == original.population
