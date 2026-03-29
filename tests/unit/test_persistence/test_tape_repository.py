"""Tests for TapeRepository."""

import pytest
from unittest.mock import AsyncMock

from simu_emperor.persistence.repositories.tape import TapeRepository
from simu_emperor.mq.event import Event


@pytest.fixture
def tape_repo(mock_client):
    return TapeRepository(mock_client)


class TestTapeRepository:
    @pytest.mark.asyncio
    async def test_append_event_returns_id(self, tape_repo, mock_client, sample_event):
        mock_client.fetch_one.return_value = {"id": 42}

        result = await tape_repo.append_event(sample_event, tick=10)

        assert result == 42
        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args
        assert "INSERT INTO tape_events" in call_args[0][0]
        assert sample_event.session_id in call_args[0]

    @pytest.mark.asyncio
    async def test_append_event_extracts_agent_id_from_src(
        self, tape_repo, mock_client, sample_event
    ):
        sample_event.src = "agent:governor_zhili"
        mock_client.fetch_one.return_value = {"id": 1}

        await tape_repo.append_event(sample_event, tick=5)

        call_args = mock_client.execute.call_args[0]
        agent_id_arg = call_args[2]
        assert agent_id_arg == "governor_zhili"

    @pytest.mark.asyncio
    async def test_append_event_uses_full_src_if_not_agent_prefix(self, tape_repo, mock_client):
        event = Event(
            event_id="evt_001",
            event_type="QUERY",
            src="player:web",
            dst=["agent:governor"],
            session_id="sess_001",
            payload={},
            timestamp="2025-01-15T10:00:00",
        )
        mock_client.fetch_one.return_value = {"id": 1}

        await tape_repo.append_event(event)

        call_args = mock_client.execute.call_args[0]
        agent_id_arg = call_args[2]
        assert agent_id_arg == "player:web"

    @pytest.mark.asyncio
    async def test_load_events_returns_parsed_json(self, tape_repo, mock_client):
        mock_client.fetch_all.return_value = [
            {
                "id": 1,
                "session_id": "sess_001",
                "agent_id": "governor_zhili",
                "event_type": "RESPONSE",
                "event_id": "evt_001",
                "src": "agent:governor_zhili",
                "dst": '["player:web"]',
                "payload": '{"action": "report"}',
                "tick": 10,
            }
        ]

        events = await tape_repo.load_events("sess_001", "governor_zhili")

        assert len(events) == 1
        assert events[0]["dst"] == ["player:web"]
        assert events[0]["payload"] == {"action": "report"}

    @pytest.mark.asyncio
    async def test_load_events_with_offset_and_limit(self, tape_repo, mock_client):
        mock_client.fetch_all.return_value = []

        await tape_repo.load_events("sess_001", "agent_001", offset=100, limit=50)

        call_args = mock_client.fetch_all.call_args
        sql = call_args[0][0]
        assert "id > ?" in sql
        assert "LIMIT 50" in sql

    @pytest.mark.asyncio
    async def test_load_events_handles_null_json(self, tape_repo, mock_client):
        mock_client.fetch_all.return_value = [
            {
                "id": 1,
                "session_id": "sess_001",
                "agent_id": "agent_001",
                "event_type": "CMD",
                "event_id": "evt_001",
                "src": "player",
                "dst": None,
                "payload": None,
                "tick": 5,
            }
        ]

        events = await tape_repo.load_events("sess_001", "agent_001")

        assert events[0]["dst"] == []
        assert events[0]["payload"] == {}

    @pytest.mark.asyncio
    async def test_get_session_returns_dict(self, tape_repo, mock_client):
        mock_client.fetch_one.return_value = {
            "session_id": "sess_001",
            "agent_id": "governor_zhili",
            "tick_start": 1,
            "title": "Test Session",
        }

        result = await tape_repo.get_session("sess_001")

        assert result["session_id"] == "sess_001"
        mock_client.fetch_one.assert_called_once()
        assert "tape_sessions" in mock_client.fetch_one.call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_session_returns_none_if_not_found(self, tape_repo, mock_client):
        mock_client.fetch_one.return_value = None

        result = await tape_repo.get_session("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_create_session_calls_execute(self, tape_repo, mock_client):
        await tape_repo.create_session(
            session_id="sess_001",
            agent_id="governor_zhili",
            tick_start=1,
            title="New Session",
        )

        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args[0]
        assert "INSERT INTO tape_sessions" in call_args[0]
        assert "ON DUPLICATE KEY UPDATE" in call_args[0]

    @pytest.mark.asyncio
    async def test_update_window_offset(self, tape_repo, mock_client):
        await tape_repo.update_window_offset("sess_001", 50, "Summary text")

        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args[0]
        assert "UPDATE tape_sessions" in call_args[0]
        assert "window_offset = ?" in call_args[0]
        assert "summary = ?" in call_args[0]
