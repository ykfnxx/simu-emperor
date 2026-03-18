"""Tests for IncidentRepository."""

import pytest
from decimal import Decimal

import aiosqlite

from simu_emperor.engine.models.incident import Incident, Effect
from simu_emperor.persistence.repositories import IncidentRepository
from simu_emperor.persistence.database import _create_schema


@pytest.fixture
async def db_conn():
    """Create an in-memory database with schema."""
    conn = await aiosqlite.connect(":memory:")
    await _create_schema(conn)
    yield conn
    await conn.close()


@pytest.fixture
def repo(db_conn):
    return IncidentRepository(conn=db_conn)


@pytest.fixture
def sample_incident():
    return Incident(
        incident_id="inc_test_001",
        title="直隶大丰收",
        description="风调雨顺，粮食产量大增",
        effects=[
            Effect(target_path="provinces.zhili.production_value", factor=Decimal("0.15")),
            Effect(target_path="provinces.zhili.stockpile", add=Decimal("2000")),
        ],
        source="system:incident_generator",
        remaining_ticks=3,
    )


@pytest.fixture
def sample_incident_2():
    return Incident(
        incident_id="inc_test_002",
        title="山西旱灾",
        description="久旱无雨",
        effects=[
            Effect(target_path="provinces.shanxi.production_value", factor=Decimal("-0.20")),
        ],
        source="agent:governor_shanxi",
        remaining_ticks=4,
    )


class TestIncidentRepository:
    """Test IncidentRepository CRUD operations."""

    @pytest.mark.asyncio
    async def test_save_and_load(self, repo, sample_incident):
        await repo.save_incident(sample_incident, tick=10)
        loaded = await repo.load_active_incidents()
        assert len(loaded) == 1
        assert loaded[0].incident_id == "inc_test_001"
        assert loaded[0].title == "直隶大丰收"
        assert loaded[0].source == "system:incident_generator"
        assert loaded[0].remaining_ticks == 3
        assert loaded[0].applied is True  # restored from DB

    @pytest.mark.asyncio
    async def test_save_preserves_effects(self, repo, sample_incident):
        await repo.save_incident(sample_incident, tick=10)
        loaded = await repo.load_active_incidents()
        assert len(loaded[0].effects) == 2
        eff0 = loaded[0].effects[0]
        assert eff0.target_path == "provinces.zhili.production_value"
        assert eff0.factor == Decimal("0.15")
        eff1 = loaded[0].effects[1]
        assert eff1.target_path == "provinces.zhili.stockpile"
        assert eff1.add == Decimal("2000")

    @pytest.mark.asyncio
    async def test_expire_incident(self, repo, sample_incident):
        await repo.save_incident(sample_incident, tick=10)
        await repo.expire_incident("inc_test_001", tick=13)
        loaded = await repo.load_active_incidents()
        assert len(loaded) == 0

    @pytest.mark.asyncio
    async def test_load_only_active(self, repo, sample_incident, sample_incident_2):
        await repo.save_incident(sample_incident, tick=10)
        await repo.save_incident(sample_incident_2, tick=10)
        await repo.expire_incident("inc_test_001", tick=13)
        loaded = await repo.load_active_incidents()
        assert len(loaded) == 1
        assert loaded[0].incident_id == "inc_test_002"

    @pytest.mark.asyncio
    async def test_save_updates_existing(self, repo, sample_incident):
        await repo.save_incident(sample_incident, tick=10)
        # Update remaining_ticks
        sample_incident.remaining_ticks = 1
        sample_incident.title = "直隶大丰收（更新）"
        await repo.save_incident(sample_incident, tick=12)
        loaded = await repo.load_active_incidents()
        assert len(loaded) == 1
        assert loaded[0].remaining_ticks == 1
        assert loaded[0].title == "直隶大丰收（更新）"

    @pytest.mark.asyncio
    async def test_get_incident_history(self, repo, sample_incident, sample_incident_2):
        await repo.save_incident(sample_incident, tick=10)
        await repo.save_incident(sample_incident_2, tick=10)
        await repo.expire_incident("inc_test_001", tick=13)

        history = await repo.get_incident_history()
        assert len(history) == 2
        # Most recent first
        assert history[0]["incident_id"] in ("inc_test_001", "inc_test_002")

    @pytest.mark.asyncio
    async def test_get_incident_history_filter_source(self, repo, sample_incident, sample_incident_2):
        await repo.save_incident(sample_incident, tick=10)
        await repo.save_incident(sample_incident_2, tick=10)

        history = await repo.get_incident_history(source="agent:governor_shanxi")
        assert len(history) == 1
        assert history[0]["incident_id"] == "inc_test_002"

    @pytest.mark.asyncio
    async def test_get_incident_history_limit(self, repo, sample_incident, sample_incident_2):
        await repo.save_incident(sample_incident, tick=10)
        await repo.save_incident(sample_incident_2, tick=10)

        history = await repo.get_incident_history(limit=1)
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_load_empty(self, repo):
        loaded = await repo.load_active_incidents()
        assert loaded == []

    @pytest.mark.asyncio
    async def test_history_includes_status(self, repo, sample_incident):
        await repo.save_incident(sample_incident, tick=10)
        history = await repo.get_incident_history()
        assert history[0]["status"] == "active"

        await repo.expire_incident("inc_test_001", tick=13)
        history = await repo.get_incident_history()
        assert history[0]["status"] == "expired"
        assert history[0]["expired_tick"] == 13
