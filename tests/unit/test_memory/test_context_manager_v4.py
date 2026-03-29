"""Unit tests for ContextManager V4 changes."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from simu_emperor.memory.context_manager import ContextManager, ContextConfig


@pytest.fixture
def tmp_memory_dir(tmp_path):
    """Create a temporary memory directory."""
    return tmp_path / "memory"


@pytest.fixture
def tape_path(tmp_memory_dir):
    """Create a temporary tape file."""
    tape_path = (
        tmp_memory_dir / "agents" / "test_agent" / "sessions" / "test_session" / "tape.jsonl"
    )
    tape_path.parent.mkdir(parents=True, exist_ok=True)
    return tape_path


@pytest.fixture
def mock_llm():
    """Create a mock LLM provider."""
    llm = AsyncMock()
    llm.call = AsyncMock(return_value="Summary of events")
    llm.get_context_window_size = MagicMock(return_value=8000)
    return llm


@pytest.fixture
def mock_tape_metadata_mgr():
    """Create a mock TapeMetadataManager."""
    mgr = AsyncMock()
    mgr.update_segment_index = AsyncMock()
    return mgr


@pytest.fixture
def context_config():
    """Create a test context config."""
    return ContextConfig(
        max_tokens=1000,
        threshold_ratio=0.9,
        keep_recent_events=5,
        anchor_buffer=2,
        enable_anchor_aware=True,
    )


@pytest.fixture
def context_manager(tape_path, context_config, mock_llm, mock_tape_metadata_mgr, tmp_memory_dir):
    """Create a ContextManager with V4 components."""
    return ContextManager(
        session_id="test_session",
        agent_id="test_agent",
        tape_path=tape_path,
        config=context_config,
        llm_provider=mock_llm,
        session_manager=None,
        tape_metadata_mgr=mock_tape_metadata_mgr,
    )


class TestContextManagerV4:
    """Test ContextManager V4 changes."""

    @pytest.mark.asyncio
    async def test_slide_window_updates_segment_index(
        self, context_manager, mock_tape_metadata_mgr
    ):
        """Test slide_window updates segment_index in tape_meta.jsonl."""
        # Add some events to trigger sliding
        for i in range(10):
            event = {
                "type": "command",
                "payload": {"query": f"test command {i}"},
                "timestamp": "2026-03-11T10:00:00Z",
                "tick": i,
            }
            context_manager.events.append(event)
            context_manager.events[-1]["_tokens"] = 100

        # Trigger slide window
        await context_manager.slide_window()

        # Verify update_segment_index was called
        mock_tape_metadata_mgr.update_segment_index.assert_called_once()

        # Verify call arguments
        call_args = mock_tape_metadata_mgr.update_segment_index.call_args
        assert call_args[1]["agent_id"] == "test_agent"
        assert call_args[1]["session_id"] == "test_session"
        assert "segment_info" in call_args[1]

    @pytest.mark.asyncio
    async def test_slide_window_without_metadata_mgr(
        self, tape_path, context_config, mock_llm, tmp_memory_dir
    ):
        """Test slide_window works without TapeMetadataManager (backward compat)."""
        # Create ContextManager without tape_metadata_mgr
        context_manager = ContextManager(
            session_id="test_session",
            agent_id="test_agent",
            tape_path=tape_path,
            config=context_config,
            llm_provider=mock_llm,
            session_manager=None,
            tape_metadata_mgr=None,  # No metadata manager
        )

        # Add some events
        for i in range(10):
            event = {
                "type": "command",
                "payload": {"query": f"test command {i}"},
                "timestamp": "2026-03-11T10:00:00Z",
            }
            context_manager.events.append(event)
            context_manager.events[-1]["_tokens"] = 100

        # Should not raise error
        await context_manager.slide_window()

        # Events should be reduced to keep_recent_events
        assert len(context_manager.events) <= context_config.keep_recent_events

    def test_extract_tick_from_events(self, context_manager):
        """Test extracting tick from event list."""
        events = [
            {"type": "command", "payload": {"query": "test"}},
            {"tick": 15, "type": "response"},
            {"type": "tool"},
        ]

        tick = context_manager._extract_tick_from_events(events)

        assert tick == 15  # First tick found

    def test_extract_tick_from_events_no_tick(self, context_manager):
        """Test extracting tick when no tick present."""
        events = [
            {"type": "command", "payload": {"query": "test"}},
            {"type": "response", "payload": {"narrative": "ok"}},
        ]

        tick = context_manager._extract_tick_from_events(events)

        assert tick is None

    def test_extract_tick_from_events_with_payload_tick(self, context_manager):
        """Test extracting tick from payload."""
        events = [
            {"type": "command", "payload": {"tick": 20, "query": "test"}},
        ]

        tick = context_manager._extract_tick_from_events(events)

        assert tick == 20

    @pytest.mark.asyncio
    async def test_summarize_events(self, context_manager, mock_llm):
        """Test summarizing events."""
        events = [
            {"type": "command", "payload": {"query": "调整税收"}},
            {"type": "response", "payload": {"narrative": "遵旨"}},
        ]

        summary = await context_manager._summarize_events(events)

        assert summary is not None
        assert len(summary) <= 100  # Max length enforced

    @pytest.mark.asyncio
    async def test_summarize_events_llm_failure(self, context_manager, mock_llm):
        """Test summarizing events when LLM fails."""
        mock_llm.call = AsyncMock(side_effect=Exception("LLM error"))

        events = [
            {"type": "command", "payload": {"query": "调整税收"}},
            {"type": "response", "payload": {"narrative": "遵旨"}},
        ]

        summary = await context_manager._summarize_events(events)

        # Should return fallback summary
        assert summary is not None
        assert "events" in summary.lower()

    @pytest.mark.asyncio
    async def test_summarize_empty_events(self, context_manager):
        """Test summarizing empty event list."""
        summary = await context_manager._summarize_events([])

        assert summary is None

    @pytest.mark.asyncio
    async def test_update_segment_index_for_dropped_no_mgr(
        self, tape_path, context_config, mock_llm, tmp_memory_dir
    ):
        """Test _update_segment_index_for_dropped without manager."""
        context_manager = ContextManager(
            session_id="test_session",
            agent_id="test_agent",
            tape_path=tape_path,
            config=context_config,
            llm_provider=mock_llm,
            tape_metadata_mgr=None,
        )

        # Should not raise error
        await context_manager._update_segment_index_for_dropped([])

        # No-op when no manager
        assert True
