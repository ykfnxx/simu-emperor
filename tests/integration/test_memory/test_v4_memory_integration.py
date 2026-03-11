"""Integration tests for V4 Memory System."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from simu_emperor.memory.tape_metadata import TapeMetadataManager
from simu_emperor.memory.tape_metadata_index import TapeMetadataIndex
from simu_emperor.memory.segment_searcher import SegmentSearcher
from simu_emperor.memory.two_level_searcher import TwoLevelSearcher
from simu_emperor.memory.query_parser import QueryParser
from simu_emperor.event_bus.event import Event


@pytest.fixture
def memory_dir(tmp_path):
    """Create a temporary memory directory."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


@pytest.fixture
def agent_id():
    """Test agent ID."""
    return "test_agent"


@pytest.fixture
def session_id():
    """Test session ID."""
    return "test_session"


@pytest.fixture
def mock_llm():
    """Create a mock LLM provider."""
    llm = AsyncMock()
    llm.call = AsyncMock(return_value="Generated title")
    return llm


class TestV4MemoryIntegration:
    """Integration tests for V4 memory system end-to-end workflows."""

    @pytest.mark.asyncio
    async def test_end_to_end_memory_retrieval(
        self, memory_dir, agent_id, session_id, mock_llm
    ):
        """
        Test end-to-end memory retrieval flow (V4).

        Flow:
        1. Create tape_meta.jsonl with metadata entries
        2. Create tape.jsonl with event data
        3. QueryParser parses natural language query
        4. TwoLevelSearcher searches metadata (Level 1)
        5. SegmentSearcher searches segments (Level 2)
        6. Returns TapeSegment results
        """
        # Setup: Create metadata and tape files
        metadata_mgr = TapeMetadataManager(memory_dir=memory_dir)

        # Create a metadata entry with title containing "税收"
        mock_event = self._create_mock_event("调整税收")
        mock_llm.call = AsyncMock(return_value="税收调整讨论")  # Title with "税收"

        await metadata_mgr.append_or_update_entry(
            agent_id=agent_id,
            session_id=session_id,
            first_event=mock_event,
            llm=mock_llm,
            current_tick=10,
        )

        # Write events to tape - create enough for a segment
        tape_path = memory_dir / "agents" / agent_id / "sessions" / session_id / "tape.jsonl"
        tape_path.parent.mkdir(parents=True, exist_ok=True)

        events = []
        for i in range(12):  # More than SEGMENT_SIZE (10)
            events.append({
                "event_id": f"evt_{i:03d}",
                "type": "command",
                "payload": {"query": f"调整税收操作{i}", "action": "税收"},
                "timestamp": f"2026-03-11T10:{i:02d}:00Z",
                "tick": 10 + i,
            })

        with open(tape_path, "w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

        # Test the retrieval flow
        # Step 1: Parse query
        query_parser = QueryParser(llm_provider=mock_llm)
        with patch.object(query_parser, "parse", return_value=self._mock_parse_result()):
            parse_result = await query_parser.parse("我之前调整过税收吗")

        # Step 2 & 3: Two-level search
        metadata_index = TapeMetadataIndex(memory_dir=memory_dir)
        segment_searcher = SegmentSearcher(memory_dir=memory_dir)
        two_level_searcher = TwoLevelSearcher(
            tape_metadata_index=metadata_index,
            segment_searcher=segment_searcher,
        )

        results = await two_level_searcher.search(
            query=parse_result.structured,
            agent_id=agent_id,
            max_results=5,
        )

        # Verify results
        assert len(results) > 0, f"Expected results but got {len(results)}"
        assert all(hasattr(r, "session_id") for r in results)
        assert all(hasattr(r, "events") for r in results)

        # Verify we found the "税收" event
        found_tax_event = False
        for segment in results:
            for event in segment.events:
                if "税收" in str(event.get("payload", {})):
                    found_tax_event = True
                    break
        assert found_tax_event, "Should find tax adjustment event"

    @pytest.mark.asyncio
    async def test_tick_driven_metadata_refresh(
        self, memory_dir, agent_id, session_id, mock_llm
    ):
        """
        Test tick-driven metadata refresh (V4).

        Flow:
        1. Create metadata entry on first event
        2. Send TICK_COMPLETED event
        3. Metadata entry is updated with new tick
        """
        metadata_mgr = TapeMetadataManager(memory_dir=memory_dir)

        # Create initial entry
        first_event = self._create_mock_event("初始查询")
        entry = await metadata_mgr.append_or_update_entry(
            agent_id=agent_id,
            session_id=session_id,
            first_event=first_event,
            llm=mock_llm,
            current_tick=10,
        )

        assert entry.created_tick == 10
        assert entry.last_updated_tick == 10

        # Simulate tick completion (update without first_event)
        updated_entry = await metadata_mgr.append_or_update_entry(
            agent_id=agent_id,
            session_id=session_id,
            first_event=None,
            llm=mock_llm,
            current_tick=20,
        )

        assert updated_entry.session_id == session_id
        assert updated_entry.created_tick == 10  # Unchanged
        assert updated_entry.last_updated_tick == 20  # Updated
        assert updated_entry.title == "Generated title"  # Unchanged

    @pytest.mark.asyncio
    async def test_segment_index_update_on_compaction(
        self, memory_dir, agent_id, session_id, mock_llm
    ):
        """
        Test segment_index update on window compaction (V4).

        Flow:
        1. Create metadata entry
        2. Update segment_index
        3. Verify segment_index is persisted
        """
        metadata_mgr = TapeMetadataManager(memory_dir=memory_dir)

        # Create entry
        await metadata_mgr.append_or_update_entry(
            agent_id=agent_id,
            session_id=session_id,
            first_event=self._create_mock_event("test"),
            llm=mock_llm,
            current_tick=10,
        )

        # Update segment_index
        segment_info = {
            "start": 0,
            "end": 10,
            "summary": "Compacted segment",
            "tick": 5,
        }

        await metadata_mgr.update_segment_index(
            agent_id=agent_id,
            session_id=session_id,
            segment_info=segment_info,
        )

        # Verify by reading the entry back
        metadata_path = metadata_mgr._get_metadata_path(agent_id)
        entry = await metadata_mgr._find_entry(metadata_path, session_id)

        assert len(entry.segment_index) == 1
        assert entry.segment_index[0]["summary"] == "Compacted segment"
        assert entry.segment_index[0]["tick"] == 5

    @pytest.mark.asyncio
    async def test_multi_session_retrieval(
        self, memory_dir, agent_id
    ):
        """
        Test retrieval across multiple sessions (V4).

        Flow:
        1. Create multiple sessions with metadata
        2. Search across all sessions
        3. Verify results from relevant sessions
        """
        # Create a fresh mock_llm that returns proper titles
        mock_llm = AsyncMock()

        def title_side_effect(prompt, **kwargs):
            # Extract the query text from the prompt
            if "税收" in str(prompt):
                return "税收调整"
            elif "赈灾" in str(prompt):
                return "赈灾拨款"
            elif "人事" in str(prompt):
                return "人事任免"
            return "Generated"

        mock_llm.call = AsyncMock(side_effect=title_side_effect)

        metadata_mgr = TapeMetadataManager(memory_dir=memory_dir)

        # Create multiple sessions
        sessions = {
            "session_1": "税收调整",
            "session_2": "赈灾拨款",
            "session_3": "人事任免",
        }

        for session_id, query_text in sessions.items():
            await metadata_mgr.append_or_update_entry(
                agent_id=agent_id,
                session_id=session_id,
                first_event=self._create_mock_event(query_text),
                llm=mock_llm,
                current_tick=10,
            )

        # Create tape files for each session with multiple events
        for session_id, query_text in sessions.items():
            tape_path = memory_dir / "agents" / agent_id / "sessions" / session_id / "tape.jsonl"
            tape_path.parent.mkdir(parents=True, exist_ok=True)

            # Create multiple events to fill a segment
            events = []
            for i in range(12):  # More than SEGMENT_SIZE (10)
                events.append({
                    "event_id": f"evt_{i:03d}",
                    "type": "command",
                    "payload": {"query": f"{query_text} - 操作 {i}", "action": query_text[:2]},
                    "timestamp": f"2026-03-11T10:0{i}:00Z",
                    "tick": 10 + i,
                })

            with open(tape_path, "w", encoding="utf-8") as f:
                for event in events:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")

        # Search for "税收" across sessions
        metadata_index = TapeMetadataIndex(memory_dir=memory_dir)
        segment_searcher = SegmentSearcher(memory_dir=memory_dir)
        two_level_searcher = TwoLevelSearcher(
            tape_metadata_index=metadata_index,
            segment_searcher=segment_searcher,
        )

        query = self._create_structured_query(entities={"action": ["税收"], "target": [], "time": ""})

        results = await two_level_searcher.search(
            query=query,
            agent_id=agent_id,
            max_results=5,
        )

        # Should find session_1 with "税收"
        assert len(results) > 0, f"Expected results but got {len(results)}"
        assert any(r.session_id == "session_1" for r in results)

    def _create_mock_event(self, query_text):
        """Create a mock event for testing."""
        event = MagicMock(spec=Event)
        event.type = "command"
        event.payload = {"query": query_text}
        event.session_id = "test_session"
        return event

    def _mock_parse_result(self):
        """Create a mock parse result."""
        from simu_emperor.memory.models import ParseResult, StructuredQuery

        structured_query = StructuredQuery(
            raw_query="我之前调整过税收吗",
            intent="query_history",
            entities={"action": ["税收"], "target": [], "time": "history"},
            scope="cross_session",
            depth="tape",
        )

        return ParseResult(
            structured=structured_query,
            parsed_by="llm",
            latency_ms=100.0,
        )

    def _create_structured_query(self, entities):
        """Create a structured query for testing."""
        from simu_emperor.memory.models import StructuredQuery

        return StructuredQuery(
            raw_query="test query",
            intent="query_history",
            entities=entities,
            scope="cross_session",
            depth="tape",
        )
