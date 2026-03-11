"""Tests for Engine class (V4)."""

import pytest

from decimal import Decimal

from simu_emperor.engine.models.base_data import ProvinceData, NationData
from simu_emperor.engine.models.incident import Incident, Effect
from simu_emperor.engine.engine import Engine


@pytest.fixture
def sample_nation():
    """Create a sample NationData for testing."""
    provinces = {
        "zhili": ProvinceData(
            province_id="zhili",
            name="直隶",
            production_value=Decimal("100000"),
            population=Decimal("50000"),
            fixed_expenditure=Decimal("5000"),
            stockpile=Decimal("20000"),
        ),
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


@pytest.fixture
def engine(sample_nation):
    """Create an Engine instance for testing."""
    return Engine(initial_state=sample_nation)


class TestEngineInit:
    """Test Engine initialization."""

    def test_engine_init(self, engine, sample_nation):
        """Test Engine initialization."""
        assert engine.get_state() is sample_nation
        assert engine.get_active_incidents() == []
        assert engine.state.turn == 0

    def test_engine_get_state(self, engine, sample_nation):
        """Test get_state returns current state."""
        state = engine.get_state()
        assert state is sample_nation
        assert state.turn == 0


class TestApplyTick:
    """Test apply_tick method."""

    def test_apply_tick_increments_turn(self, engine):
        """Test apply_tick increments turn counter."""
        initial_turn = engine.state.turn
        new_state = engine.apply_tick()
        assert new_state.turn == initial_turn + 1

    def test_apply_base_growth(self, engine):
        """Test base growth rates are applied."""
        initial_production = engine.state.provinces["zhili"].production_value
        initial_population = engine.state.provinces["zhili"].population

        engine.apply_tick()

        # production_value *= 1.01
        expected_production = initial_production * Decimal("1.01")
        # population *= 1.005
        expected_population = initial_population * Decimal("1.005")

        assert engine.state.provinces["zhili"].production_value == expected_production
        assert engine.state.provinces["zhili"].population == expected_population

    def test_apply_tax_and_treasury(self, engine):
        """Test tax calculation and treasury update."""
        # zhili: production_value=100000 * 1.01 (growth) = 101000, tax_rate=0.10, expenditure=5000
        # tax = 101000 * 0.10 = 10100
        # surplus = 10100 - 5000 = 5100
        # remittance = 5100 * 0.8 = 4080
        # stockpile += 5100 - 4080 = 1020

        engine.apply_tick()

        # Check zhili stockpile increased by surplus - remittance
        # stockpile was 20000, now 20000 + (10100 - 5000 - 4080) = 21020
        assert engine.state.provinces["zhili"].stockpile == Decimal("21020")

        # Check imperial_treasury increased by total remittance - fixed_expenditure
        # shanxi: production = 80000 * 1.01 = 80800
        # tax = 80800 * 0.10 = 8080, surplus = 8080 - 4000 = 4080
        # remittance = 4080 * 0.8 = 3264
        # total remittance = 4080 + 3264 = 7344
        # treasury was 100000, now 100000 + 7344 - 0 = 107344
        assert engine.state.imperial_treasury == Decimal("107344")

    def test_tax_with_tax_modifier(self, engine):
        """Test tax calculation with province tax modifier."""
        # Set zhili tax modifier to +0.05
        engine.state.provinces["zhili"].tax_modifier = Decimal("0.05")

        engine.apply_tick()

        # zhili: production = 100000 * 1.01 = 101000
        # tax = 101000 * (0.10 + 0.05) = 15150
        # surplus = 15150 - 5000 = 10150
        # remittance = 10150 * 0.8 = 8120
        # stockpile = 20000 + 10150 - 8120 = 22030
        assert engine.state.provinces["zhili"].stockpile == Decimal("22030")


class TestEffects:
    """Test Effect application."""

    def test_effect_factor(self, engine):
        """Test factor effect increases value by percentage."""
        incident = Incident(
            incident_id="inc_001",
            title="丰收",
            description="今年大丰收",
            effects=[Effect(target_path="provinces.zhili.production_value", factor=Decimal("0.1"))],
            source="system",
            remaining_ticks=2,
        )
        engine.add_incident(incident)

        # production_value *= 1.01 (base growth) * 1.10 (effect factor)
        initial = Decimal("100000")
        expected = initial * Decimal("1.01") * Decimal("1.10")
        engine.apply_tick()

        assert engine.state.provinces["zhili"].production_value == expected

    def test_effect_add(self, engine):
        """Test add effect adds value once."""
        incident = Incident(
            incident_id="inc_002",
            title="拨款",
            description="国库拨款",
            effects=[Effect(target_path="provinces.zhili.stockpile", add=Decimal("5000"))],
            source="player",
            remaining_ticks=2,
        )
        engine.add_incident(incident)

        engine.apply_tick()

        # stockpile: 20000 + 5000 (add) + tax change
        # production = 100000 * 1.01 = 101000
        # tax revenue = 101000 * 0.10 = 10100
        # surplus = 10100 - 5000 = 5100
        # remittance = 5100 * 0.8 = 4080
        # stockpile = 20000 + 5000 (add) + 5100 - 4080 = 26020
        assert engine.state.provinces["zhili"].stockpile == Decimal("26020")

    def test_effect_add_only_applied_once(self, engine):
        """Test add effect is only applied once (incident.applied)."""
        incident = Incident(
            incident_id="inc_003",
            title="拨款",
            description="国库拨款",
            effects=[Effect(target_path="provinces.zhili.stockpile", add=Decimal("5000"))],
            source="player",
            remaining_ticks=3,
        )
        engine.add_incident(incident)

        # First tick: add is applied
        engine.apply_tick()
        first_stockpile = engine.state.provinces["zhili"].stockpile

        # Second tick: add should NOT be applied again
        engine.apply_tick()
        second_stockpile = engine.state.provinces["zhili"].stockpile

        # The difference should be just the normal tax change, not another 5000
        # Normal tax change is (101000 * 0.10 - 5000) * (1 - 0.8) = about 1020
        difference = second_stockpile - first_stockpile
        # Should be around 1020, not 5000 + something
        assert difference < Decimal("2000")

    def test_effect_negative_factor(self, engine):
        """Test negative factor reduces value."""
        incident = Incident(
            incident_id="inc_004",
            title="旱灾",
            description="严重旱灾",
            effects=[
                Effect(target_path="provinces.zhili.production_value", factor=Decimal("-0.2"))
            ],
            source="system",
            remaining_ticks=1,
        )
        engine.add_incident(incident)

        engine.apply_tick()

        # production_value *= 1.01 (base growth) * 0.80 (effect factor)
        initial = Decimal("100000")
        expected = initial * Decimal("1.01") * Decimal("0.80")
        assert engine.state.provinces["zhili"].production_value == expected


class TestIncidentManagement:
    """Test Incident lifecycle management."""

    def test_add_incident(self, engine):
        """Test adding an incident."""
        incident = Incident(
            incident_id="inc_001",
            title="测试",
            description="测试事件",
            effects=[Effect(target_path="provinces.zhili.production_value", factor=Decimal("0.0"))],
            source="test",
            remaining_ticks=5,
        )
        engine.add_incident(incident)

        assert len(engine.get_active_incidents()) == 1
        assert engine.get_active_incidents()[0].incident_id == "inc_001"

    def test_add_incident_with_zero_ticks_raises(self, engine):
        """Test adding incident with zero ticks raises ValueError."""
        # Validation happens at Incident creation time (__post_init__)
        with pytest.raises(ValueError, match="remaining_ticks must be > 0"):
            Incident(
                incident_id="inc_001",
                title="测试",
                description="测试事件",
                effects=[
                    Effect(target_path="provinces.zhili.production_value", factor=Decimal("0.0"))
                ],
                source="test",
                remaining_ticks=0,
            )

    def test_remove_incident(self, engine):
        """Test removing an incident."""
        incident = Incident(
            incident_id="inc_001",
            title="测试",
            description="测试事件",
            effects=[Effect(target_path="provinces.zhili.production_value", factor=Decimal("0.0"))],
            source="test",
            remaining_ticks=5,
        )
        engine.add_incident(incident)
        assert len(engine.get_active_incidents()) == 1

        engine.remove_incident("inc_001")
        assert len(engine.get_active_incidents()) == 0

    def test_incident_expires_after_remaining_ticks(self, engine):
        """Test incident is removed after remaining_ticks reaches 0."""
        incident = Incident(
            incident_id="inc_001",
            title="测试",
            description="测试事件",
            effects=[Effect(target_path="provinces.zhili.production_value", factor=Decimal("0.0"))],
            source="test",
            remaining_ticks=2,
        )
        engine.add_incident(incident)

        assert len(engine.get_active_incidents()) == 1
        assert engine.get_active_incidents()[0].remaining_ticks == 2

        engine.apply_tick()
        assert engine.get_active_incidents()[0].remaining_ticks == 1

        engine.apply_tick()
        # Incident should be removed
        assert len(engine.get_active_incidents()) == 0

    def test_get_active_incidents_returns_copy(self, engine):
        """Test get_active_incidents returns a copy, not the internal list."""
        incident = Incident(
            incident_id="inc_001",
            title="测试",
            description="测试事件",
            effects=[Effect(target_path="provinces.zhili.production_value", factor=Decimal("0.0"))],
            source="test",
            remaining_ticks=5,
        )
        engine.add_incident(incident)

        incidents = engine.get_active_incidents()
        incidents.clear()

        # Internal list should not be affected
        assert len(engine.get_active_incidents()) == 1


class TestEngineEventBusIntegration:
    """Test Engine EventBus integration (V4)."""

    @pytest.fixture
    def mock_event_bus(self):
        """Create a mock EventBus."""
        from unittest.mock import MagicMock, AsyncMock

        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()
        event_bus.send_event = AsyncMock()
        return event_bus

    @pytest.fixture
    def engine_with_bus(self, sample_nation, mock_event_bus):
        """Create an Engine instance with EventBus."""
        return Engine(initial_state=sample_nation, event_bus=mock_event_bus)

    def test_engine_subscribes_to_incident_created(self, engine_with_bus, mock_event_bus):
        """Test Engine subscribes to system:engine for INCIDENT_CREATED events."""
        mock_event_bus.subscribe.assert_called_once()
        args = mock_event_bus.subscribe.call_args
        assert args[0][0] == "system:engine"

    @pytest.mark.asyncio
    async def test_on_incident_created_adds_incident(self, engine_with_bus, mock_event_bus):
        """Test _on_incident_created handler adds incident to active list."""
        from simu_emperor.event_bus.event import Event

        event = Event(
            src="agent:test_agent",
            dst=["system:engine"],
            type="incident_created",
            payload={
                "incident_id": "inc_001",
                "title": "拨款",
                "description": "国库拨款",
                "effects": [
                    {
                        "target_path": "provinces.zhili.stockpile",
                        "add": "5000",
                        "factor": None,
                    }
                ],
                "source": "test_agent",
                "remaining_ticks": 3,
            },
            session_id="test_session",
        )

        await engine_with_bus._on_incident_created(event)

        assert len(engine_with_bus.get_active_incidents()) == 1
        incident = engine_with_bus.get_active_incidents()[0]
        assert incident.incident_id == "inc_001"
        assert incident.title == "拨款"
        assert incident.remaining_ticks == 3
        assert incident.applied is False

    @pytest.mark.asyncio
    async def test_on_incident_created_ignores_other_event_types(
        self, engine_with_bus, mock_event_bus
    ):
        """Test _on_incident_created ignores non-incident_created events."""
        from simu_emperor.event_bus.event import Event

        event = Event(
            src="player",
            dst=["system:engine"],
            type="chat",
            payload={},
            session_id="test_session",
        )

        await engine_with_bus._on_incident_created(event)

        assert len(engine_with_bus.get_active_incidents()) == 0

    @pytest.mark.asyncio
    async def test_on_incident_created_with_factor_effect(self, engine_with_bus, mock_event_bus):
        """Test _on_incident_created handles factor effects correctly."""
        from simu_emperor.event_bus.event import Event

        event = Event(
            src="agent:test_agent",
            dst=["system:engine"],
            type="incident_created",
            payload={
                "incident_id": "inc_002",
                "title": "丰收",
                "description": "大丰收",
                "effects": [
                    {
                        "target_path": "provinces.zhili.production_value",
                        "add": None,
                        "factor": "0.1",
                    }
                ],
                "source": "test_agent",
                "remaining_ticks": 2,
            },
            session_id="test_session",
        )

        await engine_with_bus._on_incident_created(event)

        incident = engine_with_bus.get_active_incidents()[0]
        assert incident.effects[0].factor == Decimal("0.1")
        assert incident.effects[0].add is None

    @pytest.mark.asyncio
    async def test_on_incident_created_with_multiple_effects(self, engine_with_bus, mock_event_bus):
        """Test _on_incident_created handles multiple effects."""
        from simu_emperor.event_bus.event import Event

        event = Event(
            src="agent:test_agent",
            dst=["system:engine"],
            type="incident_created",
            payload={
                "incident_id": "inc_003",
                "title": "复合事件",
                "description": "多效果",
                "effects": [
                    {
                        "target_path": "provinces.zhili.stockpile",
                        "add": "1000",
                        "factor": None,
                    },
                    {
                        "target_path": "provinces.zhili.production_value",
                        "add": None,
                        "factor": "0.05",
                    },
                ],
                "source": "test_agent",
                "remaining_ticks": 3,
            },
            session_id="test_session",
        )

        await engine_with_bus._on_incident_created(event)

        incident = engine_with_bus.get_active_incidents()[0]
        assert len(incident.effects) == 2
        assert incident.effects[0].add == Decimal("1000")
        assert incident.effects[1].factor == Decimal("0.05")

    @pytest.mark.asyncio
    async def test_on_incident_created_with_negative_factor(self, engine_with_bus, mock_event_bus):
        """Test _on_incident_created handles negative factor (penalty)."""
        from simu_emperor.event_bus.event import Event

        event = Event(
            src="agent:test_agent",
            dst=["system:engine"],
            type="incident_created",
            payload={
                "incident_id": "inc_004",
                "title": "旱灾",
                "description": "严重旱灾",
                "effects": [
                    {
                        "target_path": "provinces.zhili.production_value",
                        "add": None,
                        "factor": "-0.2",
                    }
                ],
                "source": "system",
                "remaining_ticks": 2,
            },
            session_id="test_session",
        )

        await engine_with_bus._on_incident_created(event)

        incident = engine_with_bus.get_active_incidents()[0]
        assert incident.effects[0].factor == Decimal("-0.2")

    def test_engine_without_event_bus_still_works(self, sample_nation):
        """Test Engine works without EventBus (backward compatibility)."""
        engine = Engine(initial_state=sample_nation, event_bus=None)

        assert engine.event_bus is None
        assert engine.get_state() is sample_nation

        incident = Incident(
            incident_id="inc_001",
            title="测试",
            description="测试事件",
            effects=[Effect(target_path="provinces.zhili.stockpile", add=Decimal("1000"))],
            source="test",
            remaining_ticks=1,
        )
        engine.add_incident(incident)
        assert len(engine.get_active_incidents()) == 1
