"""Unit tests for TapeMetadataIndex (V4 Memory System)."""

import json
import pytest

from simu_emperor.memory.tape_metadata_index import TapeMetadataIndex
from simu_emperor.memory.query_parser import StructuredQuery
from simu_emperor.memory.models import TapeMetadataEntry


@pytest.fixture
def memory_dir(tmp_path):
    """Create a temporary memory directory."""
    return tmp_path / "memory"


@pytest.fixture
def metadata_index(memory_dir):
    """Create a TapeMetadataIndex instance."""
    return TapeMetadataIndex(memory_dir=memory_dir)


@pytest.fixture
def sample_entries(tmp_path):
    """Create sample metadata entries for testing."""
    memory_dir = tmp_path / "memory"
    agent_id = "test_agent"
    metadata_path = memory_dir / "agents" / agent_id / "tape_meta.jsonl"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    entries = [
        TapeMetadataEntry(
            session_id="session_1",
            title="直隶税收调整",
            created_tick=10,
            created_time="2026-03-11T10:00:00Z",
            last_updated_tick=20,
            last_updated_time="2026-03-11T12:00:00Z",
            event_count=50,
            anchor_index=[{"start": 0, "end": 10, "summary": "讨论税收政策", "tick": 12}],
        ),
        TapeMetadataEntry(
            session_id="session_2",
            title="江南赈灾",
            created_tick=30,
            created_time="2026-03-11T13:00:00Z",
            last_updated_tick=40,
            last_updated_time="2026-03-11T14:00:00Z",
            event_count=30,
            anchor_index=[{"start": 0, "end": 10, "summary": "拨款赈灾", "tick": 35}],
        ),
        TapeMetadataEntry(
            session_id="session_3",
            title="人事任免",
            created_tick=50,
            created_time="2026-03-11T15:00:00Z",
            last_updated_tick=60,
            last_updated_time="2026-03-11T16:00:00Z",
            event_count=20,
            anchor_index=[],
        ),
    ]

    # Write to file
    with open(metadata_path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    return agent_id, entries


class TestTapeMetadataIndex:
    """Test TapeMetadataIndex functionality."""

    @pytest.mark.asyncio
    async def test_search_tape_metadata_returns_matches(self, metadata_index, sample_entries):
        """Test searching returns matching entries."""
        agent_id, entries = sample_entries

        query = StructuredQuery(
            raw_query="我之前调整过税收吗",
            intent="query_history",
            entities={"action": ["调整", "税收"], "target": [], "time": "history"},
            scope="cross_session",
            depth="tape",
        )

        results = await metadata_index.search_tape_metadata(
            agent_id=agent_id,
            query=query,
        )

        # Should match "直隶税收调整" (title has "税收")
        assert len(results) > 0
        assert any("税收" in r.title for r in results)

    @pytest.mark.asyncio
    async def test_search_tape_metadata_no_match(self, metadata_index, sample_entries):
        """Test searching with no matches."""
        agent_id, _ = sample_entries

        query = StructuredQuery(
            raw_query="关于军事行动",
            intent="query_history",
            entities={"action": ["打仗", "军事"], "target": [], "time": ""},
            scope="cross_session",
            depth="tape",
        )

        results = await metadata_index.search_tape_metadata(
            agent_id=agent_id,
            query=query,
        )

        # Should return empty list
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_tape_metadata_empty_file(self, metadata_index, memory_dir):
        """Test searching when metadata file doesn't exist."""
        query = StructuredQuery(
            raw_query="test",
            intent="query_history",
            entities={"action": ["test"], "target": [], "time": "history"},
            scope="cross_session",
            depth="tape",
        )

        results = await metadata_index.search_tape_metadata(
            agent_id="nonexistent_agent",
            query=query,
        )

        assert results == []

    def test_calculate_entry_score_title_match(self, metadata_index):
        """Test scoring with title matches."""
        entry = TapeMetadataEntry(
            session_id="session_1",
            title="直隶税收调整",
            created_tick=10,
            created_time="2026-03-11T10:00:00Z",
            last_updated_tick=20,
            last_updated_time="2026-03-11T12:00:00Z",
            event_count=50,
            anchor_index=[],
        )

        entities = {"action": ["税收"], "target": ["直隶"], "time": ""}

        score = metadata_index._calculate_entry_score(entry, entities)

        # Title has both "税收" and "直隶"
        assert score > 0

    def test_calculate_entry_score_segment_summary_match(self, metadata_index):
        """Test scoring with segment summary matches."""
        entry = TapeMetadataEntry(
            session_id="session_1",
            title="无关标题",
            created_tick=10,
            created_time="2026-03-11T10:00:00Z",
            last_updated_tick=20,
            last_updated_time="2026-03-11T12:00:00Z",
            event_count=50,
            anchor_index=[{"start": 0, "end": 10, "summary": "讨论拨款赈灾事宜", "tick": 12}],
        )

        entities = {"action": ["拨款"], "target": [], "time": ""}

        score = metadata_index._calculate_entry_score(entry, entities)

        # Segment summary has "拨款"
        assert score > 0

    def test_calculate_entry_score_no_match(self, metadata_index):
        """Test scoring with no matches."""
        entry = TapeMetadataEntry(
            session_id="session_1",
            title="人事任免",
            created_tick=10,
            created_time="2026-03-11T10:00:00Z",
            last_updated_tick=20,
            last_updated_time="2026-03-11T12:00:00Z",
            event_count=50,
            anchor_index=[],
        )

        entities = {"action": ["打仗", "军事"], "target": [], "time": ""}

        score = metadata_index._calculate_entry_score(entry, entities)

        # No matches
        assert score == 0

    def test_calculate_entry_score_time_bonus(self, metadata_index):
        """Test scoring with time history bonus."""
        entry = TapeMetadataEntry(
            session_id="session_1",
            title="人事任免",
            created_tick=10,
            created_time="2026-03-11T10:00:00Z",
            last_updated_tick=20,
            last_updated_time="2026-03-11T12:00:00Z",
            event_count=50,
            anchor_index=[{"start": 0, "end": 10, "summary": "讨论", "tick": 12}],
        )

        entities = {"action": [], "target": [], "time": "history"}

        score = metadata_index._calculate_entry_score(entry, entities)

        # Has anchor_index, so gets bonus for "history"
        assert score > 0
