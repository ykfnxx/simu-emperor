"""Tests for game state API response format and initial state loading."""

import json
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from simu_shared.models import ProvinceData, Incident, Effect
from simu_server.engine.state import GameState
from simu_server.routes.client import _province_to_dict, _serialize_incidents


# ---------------------------------------------------------------------------
# _province_to_dict
# ---------------------------------------------------------------------------

class TestProvinceToDist:
    def test_returns_float_values(self):
        p = ProvinceData(
            province_id="zhili",
            name="直隶",
            production_value=Decimal("100000"),
            population=Decimal("2600000"),
            fixed_expenditure=Decimal("50000"),
            stockpile=Decimal("1200000"),
        )
        result = _province_to_dict(p, Decimal("0.10"))
        assert isinstance(result["production_value"], float)
        assert isinstance(result["population"], float)
        assert isinstance(result["stockpile"], float)
        assert result["production_value"] == 100000.0
        assert result["population"] == 2600000.0

    def test_actual_tax_rate(self):
        p = ProvinceData(
            province_id="zhili",
            name="直隶",
            tax_modifier=Decimal("0.05"),
        )
        result = _province_to_dict(p, Decimal("0.10"))
        assert result["actual_tax_rate"] == pytest.approx(0.15)

    def test_all_expected_keys(self):
        p = ProvinceData(province_id="test", name="Test")
        result = _province_to_dict(p, Decimal("0.10"))
        expected_keys = {
            "province_id", "name", "production_value", "population",
            "fixed_expenditure", "stockpile", "base_production_growth",
            "base_population_growth", "tax_modifier", "actual_tax_rate",
        }
        assert set(result.keys()) == expected_keys


# ---------------------------------------------------------------------------
# _serialize_incidents
# ---------------------------------------------------------------------------

class TestSerializeIncidents:
    def test_empty(self):
        assert _serialize_incidents([]) == []

    def test_decimal_effects_serialized_as_strings(self):
        inc = Incident(
            title="Flood",
            description="A devastating flood",
            effects=[Effect(target_path="provinces.zhili.production_value", add=Decimal("-5000"))],
            remaining_ticks=3,
        )
        raw = [inc.model_dump()]
        result = _serialize_incidents(raw)
        assert len(result) == 1
        assert result[0]["title"] == "Flood"
        assert result[0]["effects"][0]["add"] == "-5000"
        assert result[0]["effects"][0]["factor"] is None

    def test_incident_fields(self):
        inc = Incident(
            title="Drought",
            description="desc",
            effects=[],
            remaining_ticks=5,
            source="agent:minister",
        )
        raw = [inc.model_dump()]
        result = _serialize_incidents(raw)
        assert result[0]["source"] == "agent:minister"
        assert result[0]["remaining_ticks"] == 5


# ---------------------------------------------------------------------------
# Initial state loading (nested JSON format)
# ---------------------------------------------------------------------------

class TestGameStateLoad:
    @pytest.mark.asyncio
    async def test_load_nested_format(self, tmp_path):
        """Verify that the nested JSON format (nation + provinces at same level) loads."""
        state_file = tmp_path / "initial_state.json"
        state_file.write_text(json.dumps({
            "nation": {
                "turn": 0,
                "base_tax_rate": "0.10",
                "imperial_treasury": "100000",
            },
            "provinces": {
                "zhili": {
                    "province_id": "zhili",
                    "name": "直隶",
                    "production_value": "100000",
                    "population": "2600000",
                    "fixed_expenditure": "50000",
                    "stockpile": "1200000",
                },
            },
        }))

        db = AsyncMock()
        db.conn.execute = AsyncMock(return_value=AsyncMock(fetchone=AsyncMock(return_value=None)))
        db.conn.commit = AsyncMock()

        gs = GameState(db)
        await gs.load(state_file)

        assert gs.nation.imperial_treasury == Decimal("100000")
        assert gs.nation.base_tax_rate == Decimal("0.10")
        assert "zhili" in gs.nation.provinces
        assert gs.nation.provinces["zhili"].production_value == Decimal("100000")

    @pytest.mark.asyncio
    async def test_load_reinit_when_db_has_empty_provinces(self, tmp_path):
        """DB has a nation record with no provinces — should fall back to file init."""
        state_file = tmp_path / "initial_state.json"
        state_file.write_text(json.dumps({
            "nation": {
                "turn": 0,
                "base_tax_rate": "0.10",
                "imperial_treasury": "100000",
            },
            "provinces": {
                "zhili": {
                    "province_id": "zhili",
                    "name": "直隶",
                    "production_value": "100000",
                    "population": "2600000",
                },
            },
        }))

        # Simulate DB returning a nation with empty provinces
        from simu_shared.models import NationData
        empty_nation = NationData(turn=3)  # turn=3, no provinces
        db_row = (empty_nation.model_dump_json(),)

        db = AsyncMock()
        db.conn.execute = AsyncMock(
            return_value=AsyncMock(fetchone=AsyncMock(return_value=db_row)),
        )
        db.conn.commit = AsyncMock()

        gs = GameState(db)
        await gs.load(state_file)

        # Should have re-initialized from file, not kept the empty DB state
        assert len(gs.nation.provinces) == 1
        assert "zhili" in gs.nation.provinces
        assert gs.nation.imperial_treasury == Decimal("100000")

    @pytest.mark.asyncio
    async def test_load_keeps_db_state_when_provinces_exist(self, tmp_path):
        """DB has a nation with provinces — should use DB state, not file."""
        state_file = tmp_path / "initial_state.json"
        state_file.write_text(json.dumps({
            "nation": {"turn": 0, "imperial_treasury": "100000"},
            "provinces": {
                "zhili": {"province_id": "zhili", "name": "直隶"},
            },
        }))

        from simu_shared.models import NationData, ProvinceData
        db_nation = NationData(
            turn=5,
            imperial_treasury=Decimal("999999"),
            provinces={
                "shandong": ProvinceData(province_id="shandong", name="山东"),
            },
        )
        db_row = (db_nation.model_dump_json(),)

        db = AsyncMock()
        db.conn.execute = AsyncMock(
            return_value=AsyncMock(fetchone=AsyncMock(return_value=db_row)),
        )
        db.conn.commit = AsyncMock()

        gs = GameState(db)
        await gs.load(state_file)

        # Should use DB state, not file
        assert gs.nation.turn == 5
        assert gs.nation.imperial_treasury == Decimal("999999")
        assert "shandong" in gs.nation.provinces
        assert "zhili" not in gs.nation.provinces
