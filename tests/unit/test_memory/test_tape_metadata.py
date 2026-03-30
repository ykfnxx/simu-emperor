"""Unit tests for TapeMetadataManager (V4 Memory System)."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from simu_emperor.memory.tape_metadata import TapeMetadataManager
from simu_emperor.memory.models import TapeMetadataEntry
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType


@pytest.fixture
def memory_dir(tmp_path):
    """Create a temporary memory directory."""
    return tmp_path / "memory"


@pytest.fixture
def metadata_mgr(memory_dir):
    """Create a TapeMetadataManager instance."""
    return TapeMetadataManager(memory_dir=memory_dir)


@pytest.fixture
def mock_event():
    """Create a mock event for title generation."""
    event = MagicMock(spec=Event)
    event.type = "command"
    event.payload = {"query": "调整直隶税收"}
    event.session_id = "test_session"
    return event


@pytest.fixture
def mock_llm():
    """Create a mock LLM provider."""
    llm = AsyncMock()
    llm.call = AsyncMock(return_value="直隶税收调整")
    return llm


class TestTapeMetadataManager:
    """Test TapeMetadataManager functionality."""

    @pytest.mark.asyncio
    async def test_append_entry_first_time(self, metadata_mgr, mock_event, mock_llm):
        """Test creating a new metadata entry for the first time."""
        agent_id = "test_agent"
        session_id = "session_1"

        entry = await metadata_mgr.append_or_update_entry(
            agent_id=agent_id,
            session_id=session_id,
            first_event=mock_event,
            llm=mock_llm,
            current_tick=10,
        )

        assert entry.session_id == session_id
        assert entry.title == "Session session_"
        assert entry.created_tick == 10
        assert entry.last_updated_tick == 10
        assert entry.event_count == 0
        assert len(entry.anchor_index) == 0

        # Verify file was created
        metadata_path = metadata_mgr._get_metadata_path(agent_id)
        assert metadata_path.exists()

        updated_entry = None
        for _ in range(20):
            await asyncio.sleep(0.01)
            updated_entry = await metadata_mgr._find_entry(metadata_path, session_id)
            if updated_entry and updated_entry.title == "直隶税收调整":
                break

        assert updated_entry is not None
        assert updated_entry.title == "直隶税收调整"

    @pytest.mark.asyncio
    async def test_update_existing_entry(self, metadata_mgr, mock_event, mock_llm):
        """Test updating an existing metadata entry."""
        agent_id = "test_agent"
        session_id = "session_1"

        # Create initial entry
        await metadata_mgr.append_or_update_entry(
            agent_id=agent_id,
            session_id=session_id,
            first_event=mock_event,
            llm=mock_llm,
            current_tick=10,
        )

        # Update with new tick
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

    @pytest.mark.asyncio
    async def test_async_title_update(self, memory_dir, mock_event, mock_llm):
        """Test async title update persists title."""
        event_bus = AsyncMock()
        metadata_mgr = TapeMetadataManager(memory_dir=memory_dir, event_bus=event_bus)
        agent_id = "test_agent"
        session_id = "session_1"

        entry = await metadata_mgr.append_or_update_entry(
            agent_id=agent_id,
            session_id=session_id,
            first_event=mock_event,
            llm=mock_llm,
            current_tick=10,
        )
        assert entry.title == "Session session_"

        updated_entry = None
        metadata_path = metadata_mgr._get_metadata_path(agent_id)
        for _ in range(20):
            await asyncio.sleep(0.01)
            updated_entry = await metadata_mgr._find_entry(metadata_path, session_id)
            if updated_entry and updated_entry.title == "直隶税收调整":
                break

        assert updated_entry is not None
        assert updated_entry.title == "直隶税收调整"

    @pytest.mark.asyncio
    async def test_generate_title_command(self, metadata_mgr):
        """Test title generation for command events."""
        mock_llm = AsyncMock()
        mock_llm.call = AsyncMock(return_value="江南赈灾")

        mock_event = MagicMock(spec=Event)
        mock_event.type = "command"
        mock_event.payload = {"query": "给江南拨款赈灾", "province": "江南"}

        title = await metadata_mgr._generate_title(mock_event, mock_llm)

        assert title == "江南赈灾"

    @pytest.mark.asyncio
    async def test_generate_title_chat(self, metadata_mgr, mock_llm):
        """Test title generation for chat events."""
        mock_llm.call = AsyncMock(return_value="朝政讨论")

        mock_event = MagicMock(spec=Event)
        mock_event.type = "chat"
        mock_event.payload = {"message": "今天天气不错"}

        title = await metadata_mgr._generate_title(mock_event, mock_llm)

        assert title == "朝政讨论"

    @pytest.mark.asyncio
    async def test_generate_title_fallback(self, metadata_mgr, mock_llm):
        """Test title generation fallback when LLM fails."""
        mock_llm.call = AsyncMock(side_effect=Exception("LLM error"))

        mock_event = MagicMock(spec=Event)
        mock_event.type = "command"
        mock_event.payload = {"query": "test"}

        title = await metadata_mgr._generate_title(mock_event, mock_llm)

        assert title == "Untitled (LLM failed)"

    @pytest.mark.asyncio
    async def test_increment_event_count(self, metadata_mgr):
        """Test incrementing event count for an entry."""
        agent_id = "test_agent"
        session_id = "session_1"

        # Create entry first
        with patch.object(metadata_mgr, "_generate_title", return_value="Test"):
            await metadata_mgr.append_or_update_entry(
                agent_id=agent_id,
                session_id=session_id,
                first_event=MagicMock(),
                llm=AsyncMock(),
                current_tick=10,
            )

        # Increment event count
        await metadata_mgr.increment_event_count(
            agent_id=agent_id,
            session_id=session_id,
        )

        # Verify event count was incremented
        entry = await metadata_mgr._find_entry(
            metadata_mgr._get_metadata_path(agent_id), session_id
        )
        assert entry.event_count == 1

        # Increment again
        await metadata_mgr.increment_event_count(
            agent_id=agent_id,
            session_id=session_id,
        )

        entry = await metadata_mgr._find_entry(
            metadata_mgr._get_metadata_path(agent_id), session_id
        )
        assert entry.event_count == 2

    @pytest.mark.asyncio
    async def test_get_all_entries(self, metadata_mgr):
        """Test retrieving all entries for an agent."""
        agent_id = "test_agent"

        # Create multiple entries
        with patch.object(metadata_mgr, "_generate_title", return_value="Test"):
            await metadata_mgr.append_or_update_entry(
                agent_id=agent_id,
                session_id="session_1",
                first_event=MagicMock(),
                llm=AsyncMock(),
                current_tick=10,
            )
            await metadata_mgr.append_or_update_entry(
                agent_id=agent_id,
                session_id="session_2",
                first_event=MagicMock(),
                llm=AsyncMock(),
                current_tick=20,
            )

        # Get all entries
        entries = await metadata_mgr.get_all_entries(agent_id)

        assert len(entries) == 2
        session_ids = {e.session_id for e in entries}
        assert session_ids == {"session_1", "session_2"}

    @pytest.mark.asyncio
    async def test_get_all_entries_empty(self, metadata_mgr):
        """Test retrieving entries when none exist."""
        entries = await metadata_mgr.get_all_entries("nonexistent_agent")
        assert entries == []

    def test_get_metadata_path(self, metadata_mgr, memory_dir):
        """Test getting the metadata file path."""
        path = metadata_mgr._get_metadata_path("test_agent")
        expected = memory_dir / "agents" / "test_agent" / "tape_meta.jsonl"
        assert path == expected


class TestTapeMetadataEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_malformed_json_lines_skipped(self, metadata_mgr, memory_dir):
        """Test that malformed JSON lines are skipped when reading entries."""
        agent_id = "test_agent"

        # Create metadata file with some valid and some invalid lines
        metadata_path = metadata_mgr._get_metadata_path(agent_id)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        valid_entry = TapeMetadataEntry(
            session_id="valid_session",
            title="Valid Session",
            created_tick=10,
            created_time="2024-01-01T00:00:00Z",
            last_updated_tick=10,
            last_updated_time="2024-01-01T00:00:00Z",
            event_count=5,
        )

        with open(metadata_path, "w", encoding="utf-8") as f:
            f.write("{invalid json\n")  # Malformed line
            f.write(json.dumps(valid_entry.to_dict(), ensure_ascii=False) + "\n")
            f.write("another malformed line\n")
            f.write(json.dumps(valid_entry.to_dict(), ensure_ascii=False) + "\n")

        # Get all entries - should skip malformed lines
        entries = await metadata_mgr.get_all_entries(agent_id)

        # Both valid entries should be parsed, malformed lines skipped
        assert len(entries) == 2
        assert all(e.session_id == "valid_session" for e in entries)

    @pytest.mark.asyncio
    async def test_empty_file_returns_empty_list(self, metadata_mgr, memory_dir):
        """Test reading from an empty metadata file."""
        agent_id = "test_agent"

        # Create empty metadata file
        metadata_path = metadata_mgr._get_metadata_path(agent_id)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.touch()

        entries = await metadata_mgr.get_all_entries(agent_id)

        assert entries == []

    @pytest.mark.asyncio
    async def test_update_nonexistent_entry_fails_silently(self, metadata_mgr):
        """Test operations on nonexistent entry don't raise."""
        from simu_emperor.memory.models import TapeAnchor

        anchor = TapeAnchor(
            anchor_id="anchor:nonexist:0",
            name="handoff/test",
            tape_position=0,
            state={"summary": "test"},
            created_at="2026-01-01T00:00:00Z",
            created_tick=1,
        )
        # Should not raise
        await metadata_mgr.add_anchor("nonexistent_agent", "nonexist_session", anchor)

    @pytest.mark.asyncio
    async def test_increment_nonexistent_entry_fails_silently(self, metadata_mgr):
        """Test incrementing event count for a nonexistent entry."""
        # This should not raise an exception, just log a warning
        await metadata_mgr.increment_event_count(
            agent_id="nonexistent_agent",
            session_id="nonexistent_session",
        )
        # If we get here without exception, the test passes

    @pytest.mark.asyncio
    async def test_find_entry_in_nonexistent_file(self, metadata_mgr):
        """Test finding an entry when the metadata file doesn't exist."""
        metadata_path = metadata_mgr._get_metadata_path("nonexistent_agent")

        entry = await metadata_mgr._find_entry(metadata_path, "any_session")

        assert entry is None
