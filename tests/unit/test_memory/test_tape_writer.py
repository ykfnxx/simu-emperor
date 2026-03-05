"""Test TapeWriter for event logging."""

import json

import pytest

from simu_emperor.memory.tape_writer import TapeWriter


class TestTapeWriter:
    """Test TapeWriter class"""

    @pytest.mark.asyncio
    async def test_write_event_creates_file(self, tmp_path):
        """Test that write_event creates tape.jsonl file"""
        tape_writer = TapeWriter(memory_dir=tmp_path)

        event = {
            "session_id": "session:cli:default",
            "agent_id": "revenue_minister",
            "event_type": "USER_QUERY",
            "content": {"query": "我之前给直隶拨过款吗？"},
            "tokens": 15,
        }
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

        event = {
            "session_id": "session:cli:default",
            "agent_id": "revenue_minister",
            "event_type": "USER_QUERY",
            "content": {"query": "拨款给直隶"},
            "tokens": 10,
        }
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
        assert event_data["event_type"] == "USER_QUERY"
        assert event_data["content"]["query"] == "拨款给直隶"
        assert event_data["tokens"] == 10
        assert event_data["agent_id"] == "revenue_minister"
        assert "event_id" in event_data
        assert "timestamp" in event_data

    @pytest.mark.asyncio
    async def test_multiple_events_append(self, tmp_path):
        """Test that multiple events append to the same file"""
        tape_writer = TapeWriter(memory_dir=tmp_path)

        event1 = {
            "session_id": "session:cli:default",
            "agent_id": "revenue_minister",
            "event_type": "USER_QUERY",
            "content": {"query": "拨款给直隶"},
            "tokens": 10,
        }
        await tape_writer.write_event(event1)

        event2 = {
            "session_id": "session:cli:default",
            "agent_id": "revenue_minister",
            "event_type": "TOOL_CALL",
            "content": {"tool": "allocate_funds", "args": {"province": "zhili", "amount": 50000}},
            "tokens": 25,
        }
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

        assert data1["event_type"] == "USER_QUERY"
        assert data2["event_type"] == "TOOL_CALL"
        assert data1["event_id"] != data2["event_id"]

    @pytest.mark.asyncio
    async def test_event_id_uniqueness(self, tmp_path):
        """Test that each event gets a unique event ID"""
        tape_writer = TapeWriter(memory_dir=tmp_path)

        event1 = {
            "session_id": "session:cli:default",
            "agent_id": "revenue_minister",
            "event_type": "USER_QUERY",
            "content": {"query": "test1"},
            "tokens": 5,
        }
        event_id_1 = await tape_writer.write_event(event1)

        event2 = {
            "session_id": "session:cli:default",
            "agent_id": "revenue_minister",
            "event_type": "USER_QUERY",
            "content": {"query": "test2"},
            "tokens": 5,
        }
        event_id_2 = await tape_writer.write_event(event2)

        assert event_id_1 != event_id_2
        assert event_id_1.startswith("evt_")
        assert event_id_2.startswith("evt_")
