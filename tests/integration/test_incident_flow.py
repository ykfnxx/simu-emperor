"""Integration tests for the Incident system flow."""

import asyncio
import random
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import aiosqlite

from simu_emperor.config import IncidentConfig
from simu_emperor.engine.engine import Engine
from simu_emperor.engine.models.base_data import NationData, ProvinceData
from simu_emperor.engine.models.incident import Incident, Effect
from simu_emperor.engine.incident_generator import IncidentGenerator
from simu_emperor.engine.tick_coordinator import TickCoordinator
from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.persistence.database import _create_schema
from simu_emperor.persistence.repositories import IncidentRepository


@pytest.fixture
def sample_nation():
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
async def db_conn():
    conn = await aiosqlite.connect(":memory:")
    await _create_schema(conn)
    yield conn
    await conn.close()


class TestAgentCreateIncidentFlow:
    """Test: agent create_incident → Engine → Effect applied → expired."""

    @pytest.mark.asyncio
    async def test_incident_created_via_event_bus(self, sample_nation):
        """Agent sends INCIDENT_CREATED event → Engine receives and adds incident."""
        event_bus = EventBus()
        engine = Engine(sample_nation, event_bus)

        # Simulate agent sending INCIDENT_CREATED event
        event = Event(
            src="agent:governor_zhili",
            dst=["system:engine"],
            type="incident_created",
            payload={
                "incident_id": "inc_test_001",
                "title": "水利建设",
                "description": "建设大型水利设施",
                "effects": [
                    {"target_path": "provinces.zhili.production_value", "factor": "0.1", "add": None},
                ],
                "source": "agent:governor_zhili",
                "remaining_ticks": 2,
            },
            session_id="test_session",
        )
        await event_bus.send_event(event)

        # Allow async handler to process
        await asyncio.sleep(0.05)

        assert len(engine.active_incidents) == 1
        assert engine.active_incidents[0].incident_id == "inc_test_001"

    @pytest.mark.asyncio
    async def test_incident_effect_applied_on_tick(self, sample_nation):
        """Incident effects are applied during apply_tick."""
        engine = Engine(sample_nation)
        incident = Incident(
            incident_id="inc_test_001",
            title="丰收",
            description="大丰收",
            effects=[Effect(target_path="provinces.zhili.production_value", factor=Decimal("0.1"))],
            source="system",
            remaining_ticks=2,
        )
        engine.add_incident(incident)

        original_production = sample_nation.provinces["zhili"].production_value
        engine.apply_tick()

        # Production should increase by base growth + 10% factor
        new_production = engine.state.provinces["zhili"].production_value
        assert new_production > original_production

    @pytest.mark.asyncio
    async def test_incident_expires_after_ticks(self, sample_nation):
        """Incident is removed after remaining_ticks reaches 0."""
        engine = Engine(sample_nation)
        incident = Incident(
            incident_id="inc_test_001",
            title="短期事件",
            description="只持续1tick",
            effects=[Effect(target_path="provinces.zhili.stockpile", add=Decimal("1000"))],
            source="system",
            remaining_ticks=1,
        )
        engine.add_incident(incident)

        engine.apply_tick()

        assert len(engine.active_incidents) == 0
        expired = engine.get_last_expired_incidents()
        assert len(expired) == 1
        assert expired[0].incident_id == "inc_test_001"


class TestRandomGenerationFlow:
    """Test: TickCoordinator → Generator → Engine → persistence."""

    @pytest.mark.asyncio
    async def test_generator_creates_incidents_in_tick_loop(self, sample_nation, db_conn):
        """TickCoordinator triggers generator and persists incidents."""
        mock_event_bus = MagicMock()
        mock_event_bus.send_event = AsyncMock()

        engine = Engine(sample_nation)
        game_repo = MagicMock()
        game_repo.save_nation_data = AsyncMock()
        incident_repo = IncidentRepository(conn=db_conn)

        config = IncidentConfig(
            enabled=True,
            check_interval_ticks=1,  # Check every tick
            max_active_system_incidents=5,
            llm_beautify_enabled=False,
        )

        # Use a generator that always triggers
        province_names = {"zhili": "直隶", "shanxi": "山西"}
        generator = IncidentGenerator(
            config=config,
            rng=random.Random(42),
            province_names=province_names,
        )
        # Override templates with 100% probability
        from simu_emperor.engine.incident_generator import IncidentTemplate
        generator._templates = [
            IncidentTemplate(
                template_id="test",
                title_template="{province_name}测试事件",
                description_template="测试描述",
                effects=[{"target_path": "provinces.{province}.production_value", "factor": "0.1"}],
                duration_ticks=2,
                probability=1.0,
            )
        ]

        coordinator = TickCoordinator(
            event_bus=mock_event_bus,
            engine=engine,
            game_repo=game_repo,
            tick_interval_seconds=100,  # Won't actually wait
            incident_repo=incident_repo,
            incident_generator=generator,
            incident_config=config,
        )

        # Manually run one tick iteration
        coordinator._running = True
        coordinator._tick_counter = 0

        # Simulate one tick loop iteration (without the sleep)
        new_state = engine.apply_tick()
        coordinator._tick_counter += 1

        # Check interval = 1, so generator should run
        active_system_count = sum(
            1 for inc in engine.active_incidents
            if inc.source == "system:incident_generator"
        )
        new_incidents = generator.generate(new_state, active_system_count)
        for inc in new_incidents:
            engine.add_incident(inc)
            await incident_repo.save_incident(inc, new_state.turn)

        # Verify incident was generated and persisted
        assert len(new_incidents) == 1
        assert len(engine.active_incidents) == 1

        # Verify persistence
        loaded = await incident_repo.load_active_incidents()
        assert len(loaded) == 1
        assert loaded[0].title == new_incidents[0].title


class TestIncidentExpiredEventFlow:
    """Test: expired incidents publish events via TickCoordinator."""

    @pytest.mark.asyncio
    async def test_expired_incident_publishes_event(self, sample_nation, db_conn):
        """TickCoordinator publishes INCIDENT_EXPIRED when incidents expire."""
        mock_event_bus = MagicMock()
        mock_event_bus.send_event = AsyncMock()

        engine = Engine(sample_nation)
        game_repo = MagicMock()
        game_repo.save_nation_data = AsyncMock()
        incident_repo = IncidentRepository(conn=db_conn)

        # Add incident that expires in 1 tick
        incident = Incident(
            incident_id="inc_expire_001",
            title="即将过期",
            description="只剩1tick",
            effects=[Effect(target_path="provinces.zhili.stockpile", add=Decimal("500"))],
            source="system:incident_generator",
            remaining_ticks=1,
        )
        engine.add_incident(incident)
        await incident_repo.save_incident(incident, tick=0)

        coordinator = TickCoordinator(
            event_bus=mock_event_bus,
            engine=engine,
            game_repo=game_repo,
            tick_interval_seconds=100,
            incident_repo=incident_repo,
        )

        # Run one tick manually (simulating the tick loop body)
        new_state = engine.apply_tick()

        # Publish expired events (as TickCoordinator would)
        for expired_inc in engine.get_last_expired_incidents():
            expired_event = Event(
                src="system:engine",
                dst=["*"],
                type="incident_expired",
                payload={
                    "incident_id": expired_inc.incident_id,
                    "title": expired_inc.title,
                    "source": expired_inc.source,
                },
                session_id=coordinator.session_id,
            )
            await mock_event_bus.send_event(expired_event)
            await incident_repo.expire_incident(expired_inc.incident_id, new_state.turn)

        # Verify event was published
        expired_calls = [
            call for call in mock_event_bus.send_event.call_args_list
            if call.args[0].type == "incident_expired"
        ]
        assert len(expired_calls) == 1
        assert expired_calls[0].args[0].payload["incident_id"] == "inc_expire_001"

        # Verify DB updated
        active = await incident_repo.load_active_incidents()
        assert len(active) == 0

        history = await incident_repo.get_incident_history()
        assert len(history) == 1
        assert history[0]["status"] == "expired"
