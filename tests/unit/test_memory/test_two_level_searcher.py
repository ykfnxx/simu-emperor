"""Unit tests for TwoLevelSearcher (V4 Memory System)."""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from simu_emperor.memory.two_level_searcher import TwoLevelSearcher
from simu_emperor.memory.query_parser import StructuredQuery
from simu_emperor.memory.models import TapeMetadataEntry, TapeSegment


@pytest.fixture
def memory_dir(tmp_path):
    """Create a temporary memory directory."""
    return tmp_path / "memory"


@pytest.fixture
def mock_metadata_index():
    """Create a mock TapeMetadataIndex."""
    metadata_index = AsyncMock()

    # Sample metadata entries
    entries = [
        TapeMetadataEntry(
            session_id="session_1",
            title="直隶税收调整",
            created_tick=10,
            created_time="2026-03-11T10:00:00Z",
            last_updated_tick=20,
            last_updated_time="2026-03-11T12:00:00Z",
            event_count=50,
            segment_index=[],
        ),
        TapeMetadataEntry(
            session_id="session_2",
            title="江南赈灾",
            created_tick=30,
            created_time="2026-03-11T13:00:00Z",
            last_updated_tick=40,
            last_updated_time="2026-03-11T14:00:00Z",
            event_count=30,
            segment_index=[],
        ),
    ]

    metadata_index.search_tape_metadata = AsyncMock(return_value=entries)

    return metadata_index


@pytest.fixture
def mock_segment_searcher():
    """Create a mock SegmentSearcher."""
    segment_searcher = AsyncMock()

    # Sample segments
    segments = [
        TapeSegment(
            session_id="session_1",
            agent_id="test_agent",
            start_position=0,
            end_position=10,
            event_count=11,
            events=[{"type": "command", "payload": {"query": "调整税收"}}],
            tick_start=10,
            tick_end=15,
            relevance_score=0.8,
        ),
        TapeSegment(
            session_id="session_2",
            agent_id="test_agent",
            start_position=0,
            end_position=5,
            event_count=6,
            events=[{"type": "command", "payload": {"query": "赈灾拨款"}}],
            tick_start=30,
            tick_end=35,
            relevance_score=0.6,
        ),
    ]

    segment_searcher.search_segments = AsyncMock(return_value=segments)

    return segment_searcher


@pytest.fixture
def two_level_searcher(mock_metadata_index, mock_segment_searcher):
    """Create a TwoLevelSearcher instance."""
    return TwoLevelSearcher(
        tape_metadata_index=mock_metadata_index,
        segment_searcher=mock_segment_searcher,
    )


class TestTwoLevelSearcher:
    """Test TwoLevelSearcher functionality."""

    @pytest.mark.asyncio
    async def test_search_full_flow(
        self, two_level_searcher, mock_metadata_index, mock_segment_searcher
    ):
        """Test full two-level search flow."""
        query = StructuredQuery(
            raw_query="我之前调整过税收吗",
            intent="query_history",
            entities={"action": ["税收"], "target": [], "time": "history"},
            scope="cross_session",
            depth="tape",
        )

        results = await two_level_searcher.search(
            query=query,
            agent_id="test_agent",
            exclude_session=None,
            max_results=5,
        )

        # Verify Level 1 was called
        mock_metadata_index.search_tape_metadata.assert_called_once_with(
            agent_id="test_agent",
            query=query,
        )

        # Verify Level 2 was called
        mock_segment_searcher.search_segments.assert_called_once()

        # Verify results
        assert len(results) == 2
        assert all(isinstance(r, TapeSegment) for r in results)

    @pytest.mark.asyncio
    async def test_search_with_exclude_session(
        self, two_level_searcher, mock_metadata_index, mock_segment_searcher
    ):
        """Test search excludes specified session."""
        query = StructuredQuery(
            raw_query="test",
            intent="query_history",
            entities={"action": ["test"], "target": [], "time": "history"},
            scope="cross_session",
            depth="tape",
        )

        results = await two_level_searcher.search(
            query=query,
            agent_id="test_agent",
            exclude_session="session_1",
            max_results=5,
        )

        # Verify Level 2 was called with filtered entries
        call_args = mock_segment_searcher.search_segments.call_args
        matching_entries = call_args[1]["matching_entries"]

        # session_1 should be filtered out
        assert all(e.session_id != "session_1" for e in matching_entries)

    @pytest.mark.asyncio
    async def test_search_no_matches(self, mock_metadata_index, mock_segment_searcher):
        """Test search when no matches found."""
        # Return empty from Level 1
        mock_metadata_index.search_tape_metadata = AsyncMock(return_value=[])

        searcher = TwoLevelSearcher(
            tape_metadata_index=mock_metadata_index,
            segment_searcher=mock_segment_searcher,
        )

        query = StructuredQuery(
            raw_query="军事行动",
            intent="query_history",
            entities={"action": ["打仗"], "target": [], "time": "history"},
            scope="cross_session",
            depth="tape",
        )

        results = await searcher.search(
            query=query,
            agent_id="test_agent",
            max_results=5,
        )

        # Should return empty list
        assert results == []

        # Level 2 should not be called
        mock_segment_searcher.search_segments.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_respects_max_results(
        self, two_level_searcher, mock_segment_searcher
    ):
        """Test search respects max_results parameter."""
        query = StructuredQuery(
            raw_query="test",
            intent="query_history",
            entities={"action": ["test"], "target": [], "time": "history"},
            scope="cross_session",
            depth="tape",
        )

        results = await two_level_searcher.search(
            query=query,
            agent_id="test_agent",
            max_results=1,
        )

        # Level 2 should be called with max_results=1
        call_args = mock_segment_searcher.search_segments.call_args
        assert call_args[1]["max_results"] == 1

    @pytest.mark.asyncio
    async def test_search_propagates_agent_id(
        self, two_level_searcher, mock_segment_searcher
    ):
        """Test search propagates agent_id to Level 2."""
        query = StructuredQuery(
            raw_query="test",
            intent="query_history",
            entities={"action": ["test"], "target": [], "time": "history"},
            scope="cross_session",
            depth="tape",
        )

        await two_level_searcher.search(
            query=query,
            agent_id="my_agent",
            max_results=5,
        )

        # Level 2 should receive the same agent_id
        call_args = mock_segment_searcher.search_segments.call_args
        assert call_args[1]["agent_id"] == "my_agent"
