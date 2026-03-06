"""Test TapeWriter for event logging."""

import json

import pytest

from simu_emperor.memory.tape_writer import TapeWriter
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType


class TestTapeWriter:
    """Test TapeWriter class"""

    @pytest.mark.asyncio
    async def test_write_event_creates_file(self, tmp_path):
        """Test that write_event creates tape.jsonl file"""
        tape_writer = TapeWriter(memory_dir=tmp_path)

        event = Event(
            src="agent:revenue_minister",
            dst=["player"],
            type=EventType.USER_QUERY,
            payload={"query": "我之前给直隶拨过款吗？", "event_type": EventType.COMMAND},
            session_id="session:cli:default",
        )
        event_id = await tape_writer.write_event(event)

        # Verify event_id is returned
        assert event_id is not None
        assert event_id.startswith("evt_")

        # Verify file was created
        tape_path = (
            tmp_path
            / "agents"
            / "revenue_minister"
            / "sessions"
            / "session:cli:default"
            / "tape.jsonl"
        )
        assert tape_path.exists()

    @pytest.mark.asyncio
    async def test_write_event_format(self, tmp_path):
        """Test that written event has correct JSONL format"""
        tape_writer = TapeWriter(memory_dir=tmp_path)

        event = Event(
            src="agent:revenue_minister",
            dst=["player"],
            type=EventType.USER_QUERY,
            payload={"query": "拨款给直隶", "event_type": EventType.COMMAND},
            session_id="session:cli:default",
        )
        await tape_writer.write_event(event)

        tape_path = (
            tmp_path
            / "agents"
            / "revenue_minister"
            / "sessions"
            / "session:cli:default"
            / "tape.jsonl"
        )
        content = tape_path.read_text()

        # Verify JSONL format (one JSON object per line)
        lines = content.strip().split("\n")
        assert len(lines) == 1

        event_data = json.loads(lines[0])
        assert event_data["type"] == "user_query"
        assert event_data["payload"]["query"] == "拨款给直隶"
        assert event_data["src"] == "agent:revenue_minister"
        assert event_data["dst"] == ["player"]
        assert "event_id" in event_data
        assert "timestamp" in event_data

    @pytest.mark.asyncio
    async def test_multiple_events_append(self, tmp_path):
        """Test that multiple events append to the same file"""
        tape_writer = TapeWriter(memory_dir=tmp_path)

        event1 = Event(
            src="agent:revenue_minister",
            dst=["player"],
            type=EventType.USER_QUERY,
            payload={"query": "拨款给直隶", "event_type": EventType.COMMAND},
            session_id="session:cli:default",
        )
        await tape_writer.write_event(event1)

        event2 = Event(
            src="agent:revenue_minister",
            dst=["player"],
            type=EventType.TOOL_RESULT,
            payload={
                "tool": "allocate_funds",
                "result": "success",
            },
            session_id="session:cli:default",
        )
        await tape_writer.write_event(event2)

        tape_path = (
            tmp_path
            / "agents"
            / "revenue_minister"
            / "sessions"
            / "session:cli:default"
            / "tape.jsonl"
        )
        content = tape_path.read_text()

        lines = content.strip().split("\n")
        assert len(lines) == 2

        data1 = json.loads(lines[0])
        data2 = json.loads(lines[1])

        assert data1["type"] == "user_query"
        assert data2["type"] == "tool_result"
        assert data1["event_id"] != data2["event_id"]

    @pytest.mark.asyncio
    async def test_event_id_uniqueness(self, tmp_path):
        """Test that each event gets a unique event ID"""
        tape_writer = TapeWriter(memory_dir=tmp_path)

        event1 = Event(
            src="agent:revenue_minister",
            dst=["player"],
            type=EventType.USER_QUERY,
            payload={"query": "test1", "event_type": EventType.COMMAND},
            session_id="session:cli:default",
        )
        event_id_1 = await tape_writer.write_event(event1)

        event2 = Event(
            src="agent:revenue_minister",
            dst=["player"],
            type=EventType.USER_QUERY,
            payload={"query": "test2", "event_type": EventType.COMMAND},
            session_id="session:cli:default",
        )
        event_id_2 = await tape_writer.write_event(event2)

        assert event_id_1 != event_id_2
        assert event_id_1.startswith("evt_")
        assert event_id_2.startswith("evt_")

    @pytest.mark.asyncio
    async def test_write_event_rejects_non_agent_src(self, tmp_path):
        """Test that write_event skips writing for non-agent sources"""
        tape_writer = TapeWriter(memory_dir=tmp_path)

        # Test with player source
        event = Event(
            src="player",
            dst=["agent:revenue_minister"],
            type=EventType.COMMAND,
            payload={"command": "拨款给直隶"},
            session_id="session:cli:default",
        )
        event_id = await tape_writer.write_event(event)

        # Verify event_id is returned but no file created
        assert event_id is not None

        # Verify no file was created for player
        player_tape_path = (
            tmp_path
            / "agents"
            / "player"
            / "sessions"
            / "session:cli:default"
            / "tape.jsonl"
        )
        assert not player_tape_path.exists()

    @pytest.mark.asyncio
    async def test_write_event_preserves_dst(self, tmp_path):
        """Test that write_event preserves the dst field correctly"""
        tape_writer = TapeWriter(memory_dir=tmp_path)

        # Test with player destination
        event = Event(
            src="agent:revenue_minister",
            dst=["player"],
            type=EventType.USER_QUERY,
            payload={"query": "拨款给直隶", "event_type": EventType.COMMAND},
            session_id="session:cli:default",
        )
        await tape_writer.write_event(event)

        tape_path = (
            tmp_path
            / "agents"
            / "revenue_minister"
            / "sessions"
            / "session:cli:default"
            / "tape.jsonl"
        )
        content = tape_path.read_text()

        event_data = json.loads(content.strip())
        assert event_data["dst"] == ["player"]
        assert event_data["src"] == "agent:revenue_minister"
