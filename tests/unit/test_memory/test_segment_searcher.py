"""Unit tests for SegmentSearcher (V4 Memory System)."""

import json
import pytest

from simu_emperor.memory.segment_searcher import SegmentSearcher
from simu_emperor.memory.query_parser import StructuredQuery
from simu_emperor.memory.models import TapeMetadataEntry, TapeView


@pytest.fixture
def memory_dir(tmp_path):
    """Create a temporary memory directory."""
    return tmp_path / "memory"


@pytest.fixture
def segment_searcher(memory_dir):
    """Create a SegmentSearcher instance."""
    return SegmentSearcher(memory_dir=memory_dir)


@pytest.fixture
def sample_tape(memory_dir):
    """Create a sample tape.jsonl file."""
    agent_id = "test_agent"
    session_id = "session_1"
    tape_path = memory_dir / "agents" / agent_id / "sessions" / session_id / "tape.jsonl"
    tape_path.parent.mkdir(parents=True, exist_ok=True)

    events = [
        {
            "event_id": "evt_001",
            "type": "command",
            "payload": {"query": "调整直隶税收", "province": "直隶"},
            "timestamp": "2026-03-11T10:00:00Z",
            "tick": 10,
        },
        {
            "event_id": "evt_002",
            "type": "response",
            "payload": {"narrative": "遵旨，臣这就去办"},
            "timestamp": "2026-03-11T10:01:00Z",
            "tick": 10,
        },
        {
            "event_id": "evt_003",
            "type": "command",
            "payload": {"query": "给江南拨款赈灾", "province": "江南"},
            "timestamp": "2026-03-11T11:00:00Z",
            "tick": 15,
        },
        {
            "event_id": "evt_004",
            "type": "response",
            "payload": {"narrative": "江南赈灾款已拨付"},
            "timestamp": "2026-03-11T11:01:00Z",
            "tick": 15,
        },
        {
            "event_id": "evt_005",
            "type": "command",
            "payload": {"query": "任命新官员", "action": "任命"},
            "timestamp": "2026-03-11T12:00:00Z",
            "tick": 20,
        },
    ]

    with open(tape_path, "w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    return agent_id, session_id, events


@pytest.fixture
def sample_metadata_entries(sample_tape):
    """Create sample metadata entries."""
    agent_id, session_id, _ = sample_tape

    return [
        TapeMetadataEntry(
            session_id=session_id,
            title="税收与赈灾",
            created_tick=10,
            created_time="2026-03-11T10:00:00Z",
            last_updated_tick=20,
            last_updated_time="2026-03-11T12:00:00Z",
            event_count=5,
        )
    ]


class TestSegmentSearcher:
    """Test SegmentSearcher functionality."""

    @pytest.mark.asyncio
    async def test_search_segments_returns_matching(
        self, segment_searcher, sample_tape, sample_metadata_entries
    ):
        """Test searching returns matching segments."""
        agent_id, _, events = sample_tape

        query = StructuredQuery(
            raw_query="之前有关于税收的讨论吗",
            intent="query_history",
            entities={"action": ["税收"], "target": [], "time": "history"},
            scope="cross_session",
            depth="tape",
        )

        results = await segment_searcher.search_segments(
            agent_id=agent_id,
            matching_entries=sample_metadata_entries,
            query=query,
            max_results=5,
        )

        # Should find segments with "税收" keyword
        assert len(results) > 0
        assert all(isinstance(r, TapeView) for r in results)

    @pytest.mark.asyncio
    async def test_search_segments_no_match(
        self, segment_searcher, sample_tape, sample_metadata_entries
    ):
        """Test searching with no matching segments."""
        agent_id, _, _ = sample_tape

        query = StructuredQuery(
            raw_query="军事行动",
            intent="query_history",
            entities={"action": ["打仗", "军事"], "target": [], "time": ""},
            scope="cross_session",
            depth="tape",
        )

        results = await segment_searcher.search_segments(
            agent_id=agent_id,
            matching_entries=sample_metadata_entries,
            query=query,
            max_results=5,
        )

        # Should return empty list (no matches)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_segments_respects_max_results(
        self, segment_searcher, sample_tape, sample_metadata_entries
    ):
        """Test searching respects max_results parameter."""
        agent_id, _, _ = sample_tape

        query = StructuredQuery(
            raw_query="查询",
            intent="query_history",
            entities={"action": ["调整"], "target": [], "time": "history"},
            scope="cross_session",
            depth="tape",
        )

        results = await segment_searcher.search_segments(
            agent_id=agent_id,
            matching_entries=sample_metadata_entries,
            query=query,
            max_results=1,
        )

        # Should return at most 1 result
        assert len(results) <= 1

    @pytest.mark.asyncio
    async def test_search_segments_sorted_by_score(
        self, segment_searcher, sample_tape, sample_metadata_entries
    ):
        """Test results are sorted by relevance score."""
        agent_id, _, _ = sample_tape

        query = StructuredQuery(
            raw_query="税收 赈灾",
            intent="query_history",
            entities={"action": ["税收", "赈灾"], "target": [], "time": "history"},
            scope="cross_session",
            depth="tape",
        )

        results = await segment_searcher.search_segments(
            agent_id=agent_id,
            matching_entries=sample_metadata_entries,
            query=query,
            max_results=5,
        )

        # Check scores are in descending order
        for i in range(len(results) - 1):
            assert results[i].relevance_score >= results[i + 1].relevance_score

    def test_create_view(self, segment_searcher, sample_metadata_entries):
        """Test creating a TapeView from events."""
        events = [
            {"type": "command", "payload": {"query": "test"}, "tick": 10},
            {"type": "response", "payload": {"narrative": "ok"}, "tick": 10},
        ]

        entry = sample_metadata_entries[0]

        view = segment_searcher._create_view(events, 0, entry, agent_id="test_agent")

        assert view.session_id == entry.session_id
        assert view.agent_id == "test_agent"
        assert view.tape_position_start == 0
        assert view.tape_position_end == 1
        assert view.event_count == 2
        assert view.events == events
        assert view.tick_start == 10
        assert view.tick_end == 10

    def test_calculate_segment_score_action_match(self, segment_searcher):
        """Test segment scoring with action matches."""
        events = [
            {"type": "command", "payload": {"query": "调整税收"}, "tick": 10},
        ]

        entities = {"action": ["税收"], "target": [], "time": ""}

        score = segment_searcher._calculate_segment_score(events, entities)

        assert score > 0

    def test_calculate_segment_score_target_match(self, segment_searcher):
        """Test segment scoring with target matches."""
        events = [
            {"type": "command", "payload": {"query": "直隶赈灾", "province": "直隶"}},
        ]

        entities = {"action": [], "target": ["直隶"], "time": ""}

        score = segment_searcher._calculate_segment_score(events, entities)

        assert score > 0

    def test_calculate_segment_score_no_match(self, segment_searcher):
        """Test segment scoring with no matches."""
        events = [
            {"type": "command", "payload": {"query": "人事任免"}},
        ]

        entities = {"action": ["打仗", "军事"], "target": [], "time": ""}

        score = segment_searcher._calculate_segment_score(events, entities)

        assert score == 0

    def test_extract_tick_range(self, segment_searcher):
        """Test extracting tick range from events."""
        events = [
            {"tick": 10, "type": "test"},
            {"tick": 15, "type": "test"},
            {"tick": 20, "type": "test"},
        ]

        tick_start, tick_end = segment_searcher._extract_tick_range(events)

        assert tick_start == 10
        assert tick_end == 20

    def test_extract_tick_range_no_ticks(self, segment_searcher):
        """Test extracting tick range when no ticks present."""
        events = [
            {"type": "test"},
            {"type": "test"},
        ]

        tick_start, tick_end = segment_searcher._extract_tick_range(events)

        assert tick_start is None
        assert tick_end is None

    def test_extract_timestamp_range(self, segment_searcher):
        """Test extracting timestamp range from events."""
        events = [
            {"timestamp": "2026-03-11T10:00:00Z"},
            {"timestamp": "2026-03-11T11:00:00Z"},
            {"timestamp": "2026-03-11T12:00:00Z"},
        ]

        ts_start, ts_end = segment_searcher._extract_timestamp_range(events)

        assert ts_start == "2026-03-11T10:00:00Z"
        assert ts_end == "2026-03-11T12:00:00Z"

    def test_extract_timestamp_range_no_timestamps(self, segment_searcher):
        """Test extracting timestamp range when no timestamps present."""
        events = [
            {"type": "test"},
            {"type": "test"},
        ]

        ts_start, ts_end = segment_searcher._extract_timestamp_range(events)

        assert ts_start is None
        assert ts_end is None

    def test_extract_agent_id_from_path(self, segment_searcher, memory_dir):
        """Test extracting agent_id from tape path."""
        tape_path = memory_dir / "agents" / "test_agent" / "sessions" / "session_1" / "tape.jsonl"

        agent_id = segment_searcher._extract_agent_id(tape_path)

        assert agent_id == "test_agent"
