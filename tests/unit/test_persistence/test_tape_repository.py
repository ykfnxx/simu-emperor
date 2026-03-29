"""Test TapeRepository (V4.2)."""

import json
import pytest

from simu_emperor.persistence.tape_repository import TapeRepository
from simu_emperor.event_bus.event import Event


async def _create_tables(conn):
    """Create the tape_events and failed_embeddings tables."""
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS tape_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE NOT NULL,
            session_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            src TEXT NOT NULL,
            dst TEXT NOT NULL,
            type TEXT NOT NULL,
            payload TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            tick INTEGER,
            parent_event_id TEXT,
            root_event_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS failed_embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            segment_id TEXT UNIQUE NOT NULL,
            summary TEXT NOT NULL,
            metadata TEXT NOT NULL,
            error TEXT NOT NULL,
            retry_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            last_retry_at TEXT
        );
    """)
    await conn.commit()


@pytest.mark.asyncio
async def test_insert_and_query():
    """Test inserting event and querying by session_id."""
    conn = await pytest.importorskip("aiosqlite").connect(":memory:")
    await _create_tables(conn)

    repo = TapeRepository(":memory:")
    repo._conn = conn

    event = Event(
        src="player",
        dst=["agent:revenue_minister"],
        type="COMMAND",
        payload={"action": "adjust_tax", "rate": 0.15},
        session_id="session:test:001",
    )

    await repo.insert_event(event, agent_id="revenue_minister", tick=5)

    results = await repo.query_events(session_id="session:test:001")

    assert len(results) == 1
    assert results[0]["event_id"] == event.event_id
    assert results[0]["session_id"] == "session:test:001"
    assert results[0]["agent_id"] == "revenue_minister"
    assert results[0]["src"] == "player"
    assert results[0]["dst"] == ["agent:revenue_minister"]
    assert results[0]["type"] == "COMMAND"
    assert results[0]["tick"] == 5

    await conn.close()


@pytest.mark.asyncio
async def test_query_by_agent_id():
    """Test filtering events by agent_id."""
    conn = await pytest.importorskip("aiosqlite").connect(":memory:")
    await _create_tables(conn)

    repo = TapeRepository(":memory:")
    repo._conn = conn

    event1 = Event(
        src="player",
        dst=["agent:revenue_minister"],
        type="COMMAND",
        payload={"action": "tax"},
        session_id="session:test:001",
    )
    event2 = Event(
        src="player",
        dst=["agent:war_minister"],
        type="COMMAND",
        payload={"action": "military"},
        session_id="session:test:001",
    )

    await repo.insert_event(event1, agent_id="revenue_minister", tick=1)
    await repo.insert_event(event2, agent_id="war_minister", tick=2)

    results = await repo.query_events(agent_id="revenue_minister")

    assert len(results) == 1
    assert results[0]["agent_id"] == "revenue_minister"
    assert results[0]["payload"]["action"] == "tax"

    await conn.close()


@pytest.mark.asyncio
async def test_query_by_type():
    """Test filtering events by event type."""
    conn = await pytest.importorskip("aiosqlite").connect(":memory:")
    await _create_tables(conn)

    repo = TapeRepository(":memory:")
    repo._conn = conn

    event1 = Event(
        src="player",
        dst=["agent:test"],
        type="COMMAND",
        payload={"cmd": 1},
        session_id="session:test:001",
    )
    event2 = Event(
        src="agent:test",
        dst=["player"],
        type="RESPONSE",
        payload={"resp": 2},
        session_id="session:test:001",
    )

    await repo.insert_event(event1, agent_id="test_agent", tick=1)
    await repo.insert_event(event2, agent_id="test_agent", tick=2)

    results = await repo.query_events(event_type="RESPONSE")

    assert len(results) == 1
    assert results[0]["type"] == "RESPONSE"

    await conn.close()


@pytest.mark.asyncio
async def test_count_events():
    """Test counting events by session_id."""
    conn = await pytest.importorskip("aiosqlite").connect(":memory:")
    await _create_tables(conn)

    repo = TapeRepository(":memory:")
    repo._conn = conn

    event1 = Event(
        src="player",
        dst=["agent:test"],
        type="COMMAND",
        payload={},
        session_id="session:test:001",
    )
    event2 = Event(
        src="player",
        dst=["agent:test"],
        type="COMMAND",
        payload={},
        session_id="session:test:001",
    )
    event3 = Event(
        src="player",
        dst=["agent:test"],
        type="COMMAND",
        payload={},
        session_id="session:test:002",
    )

    await repo.insert_event(event1, agent_id="test_agent", tick=1)
    await repo.insert_event(event2, agent_id="test_agent", tick=2)
    await repo.insert_event(event3, agent_id="test_agent", tick=3)

    count1 = await repo.count_events("session:test:001")
    count2 = await repo.count_events("session:test:002")
    count3 = await repo.count_events("session:unknown")

    assert count1 == 2
    assert count2 == 1
    assert count3 == 0

    await conn.close()


@pytest.mark.asyncio
async def test_failed_embeddings_lifecycle():
    """Test record, get, mark retried, and remove failed embeddings."""
    conn = await pytest.importorskip("aiosqlite").connect(":memory:")
    await _create_tables(conn)

    repo = TapeRepository(":memory:")
    repo._conn = conn

    await repo.record_failed_embedding(
        segment_id="seg_001",
        summary="Test summary",
        metadata={"source": "test", "turn": 5},
        error="Connection timeout",
    )

    results = await repo.get_failed_embeddings()
    assert len(results) == 1
    assert results[0]["segment_id"] == "seg_001"
    assert results[0]["summary"] == "Test summary"
    assert results[0]["metadata"] == {"source": "test", "turn": 5}
    assert results[0]["error"] == "Connection timeout"
    assert results[0]["retry_count"] == 0

    await repo.mark_embedding_retried("seg_001")

    results = await repo.get_failed_embeddings()
    assert results[0]["retry_count"] == 1
    assert results[0]["last_retry_at"] is not None

    await repo.remove_failed_embedding("seg_001")

    results = await repo.get_failed_embeddings()
    assert len(results) == 0

    await conn.close()


@pytest.mark.asyncio
async def test_failed_embeddings_retry_limit():
    """Test that only records with retry_count < 3 are returned."""
    conn = await pytest.importorskip("aiosqlite").connect(":memory:")
    await _create_tables(conn)

    repo = TapeRepository(":memory:")
    repo._conn = conn

    await repo.record_failed_embedding(
        segment_id="seg_001",
        summary="Summary 1",
        metadata={},
        error="Error 1",
    )
    await repo.record_failed_embedding(
        segment_id="seg_002",
        summary="Summary 2",
        metadata={},
        error="Error 2",
    )

    await repo.mark_embedding_retried("seg_001")
    await repo.mark_embedding_retried("seg_001")
    await repo.mark_embedding_retried("seg_001")

    results = await repo.get_failed_embeddings()

    assert len(results) == 1
    assert results[0]["segment_id"] == "seg_002"

    await conn.close()
