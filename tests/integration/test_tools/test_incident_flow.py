"""Integration tests for incident creation and application flow.

Tests the end-to-end flow:
1. Agent calls create_incident tool
2. Event sent to Engine
3. Engine applies effects via apply_tick
4. Query tools return updated data
"""

import pytest
from decimal import Decimal
from pathlib import Path

from simu_emperor.engine.engine import Engine
from simu_emperor.engine.models.base_data import NationData, ProvinceData
from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.agents.tools.action_tools import ActionTools
from simu_emperor.agents.tools.query_tools import QueryTools


@pytest.fixture
def nation_data():
    """Create minimal nation data for testing."""
    return NationData(
        turn=0,
        base_tax_rate=Decimal("0.1"),
        tribute_rate=Decimal("0.8"),
        fixed_expenditure=Decimal("0"),
        imperial_treasury=Decimal("100000"),
        provinces={
            "zhili": ProvinceData(
                province_id="zhili",
                name="直隶",
                production_value=Decimal("100000"),
                population=Decimal("2600000"),
                fixed_expenditure=Decimal("50000"),
                stockpile=Decimal("1200000"),
            )
        },
    )


@pytest.fixture
def event_bus():
    """Create event bus."""
    return EventBus()


@pytest.fixture
def engine(nation_data, event_bus):
    """Create engine with event bus."""
    return Engine(nation_data, event_bus)


@pytest.fixture
def action_tools(event_bus, tmp_path):
    """Create action tools."""
    return ActionTools(
        agent_id="test_agent",
        event_bus=event_bus,
        data_dir=tmp_path,
    )


@pytest.fixture
def mock_repository(nation_data):
    """Create mock repository."""
    class MockRepo:
        async def load_nation_data(self):
            return nation_data
    return MockRepo()


@pytest.fixture
def query_tools(mock_repository, tmp_path):
    """Create query tools."""
    return QueryTools(
        agent_id="test_agent",
        repository=mock_repository,
        data_dir=tmp_path,
    )


@pytest.mark.asyncio
async def test_incident_with_add_effect(engine, action_tools, query_tools, event_bus):
    """Test incident with add effect on stockpile."""
    event = Event(
        src="player",
        dst=["agent:test_agent"],
        type=EventType.CHAT,
        payload={},
        session_id="test_session",
    )

    # Create incident with add effect
    result = await action_tools.create_incident(
        {
            "title": "丰收",
            "description": "直隶大丰收",
            "effects": [
                {
                    "target_path": "provinces.zhili.stockpile",
                    "add": 50000,
                }
            ],
            "duration_ticks": 1,
        },
        event,
    )

    assert "✅" in result

    # Wait for event processing
    await event_bus.wait_for_background_tasks()

    # Apply tick
    engine.apply_tick()

    # Verify incident was added
    assert len(engine.get_active_incidents()) == 0  # Expired after 1 tick


@pytest.mark.asyncio
async def test_incident_with_factor_effect(engine, action_tools, event_bus):
    """Test incident with factor effect on production_value."""
    event = Event(
        src="player",
        dst=["agent:test_agent"],
        type=EventType.CHAT,
        payload={},
        session_id="test_session",
    )

    # Create incident with factor effect (10% boost)
    result = await action_tools.create_incident(
        {
            "title": "商贸繁荣",
            "description": "直隶商贸繁荣",
            "effects": [
                {
                    "target_path": "provinces.zhili.production_value",
                    "factor": 0.1,
                }
            ],
            "duration_ticks": 2,
        },
        event,
    )

    assert "✅" in result
    await event_bus.wait_for_background_tasks()

    initial_value = engine.state.provinces["zhili"].production_value
    engine.apply_tick()

    # Production should be boosted by factor
    new_value = engine.state.provinces["zhili"].production_value
    assert new_value > initial_value


@pytest.mark.asyncio
async def test_incident_with_multiple_effects(engine, action_tools, event_bus):
    """Test incident with multiple effects."""
    event = Event(
        src="player",
        dst=["agent:test_agent"],
        type=EventType.CHAT,
        payload={},
        session_id="test_session",
    )

    result = await action_tools.create_incident(
        {
            "title": "综合政策",
            "description": "多项措施",
            "effects": [
                {"target_path": "provinces.zhili.stockpile", "add": 10000},
                {"target_path": "provinces.zhili.production_value", "factor": 0.05},
            ],
            "duration_ticks": 1,
        },
        event,
    )

    assert "✅" in result
    await event_bus.wait_for_background_tasks()
    engine.apply_tick()

    assert len(engine.get_active_incidents()) == 0  # Expired after 1 tick
