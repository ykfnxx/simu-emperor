"""Tests for SegmentRepository."""

import pytest

from simu_emperor.persistence.repositories.segment import SegmentRepository


@pytest.fixture
def segment_repo(mock_client):
    return SegmentRepository(mock_client)


class TestSegmentRepository:
    @pytest.mark.asyncio
    async def test_create_segment_returns_id(self, segment_repo, mock_client):
        mock_client.fetch_one.return_value = {"id": 1}

        result = await segment_repo.create_segment(
            session_id="sess_001",
            agent_id="agent_001",
            start_pos=0,
            end_pos=10,
            summary="First segment summary",
            tick=5,
        )

        assert result == 1
        mock_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_segment_with_embedding(self, segment_repo, mock_client):
        mock_client.fetch_one.return_value = {"id": 2}
        embedding = b"\x00\x01\x02\x03"

        result = await segment_repo.create_segment(
            session_id="sess_001",
            agent_id="agent_001",
            start_pos=10,
            end_pos=20,
            summary="Second segment",
            embedding=embedding,
        )

        assert result == 2
        call_args = mock_client.execute.call_args[0]
        assert embedding in call_args

    @pytest.mark.asyncio
    async def test_create_segment_returns_zero_if_no_row(self, segment_repo, mock_client):
        mock_client.fetch_one.return_value = None

        result = await segment_repo.create_segment(
            session_id="sess_001",
            agent_id="agent_001",
            start_pos=0,
            end_pos=10,
            summary="Test",
        )

        assert result == 0

    @pytest.mark.asyncio
    async def test_get_segments_returns_list(self, segment_repo, mock_client):
        mock_client.fetch_all.return_value = [
            {
                "id": 1,
                "session_id": "sess_001",
                "agent_id": "agent_001",
                "start_pos": 0,
                "end_pos": 10,
                "summary": "First segment",
                "tick": 1,
            },
            {
                "id": 2,
                "session_id": "sess_001",
                "agent_id": "agent_001",
                "start_pos": 10,
                "end_pos": 20,
                "summary": "Second segment",
                "tick": 5,
            },
        ]

        segments = await segment_repo.get_segments("sess_001", "agent_001")

        assert len(segments) == 2
        assert segments[0]["start_pos"] == 0
        assert segments[1]["start_pos"] == 10

    @pytest.mark.asyncio
    async def test_get_segments_empty_list(self, segment_repo, mock_client):
        mock_client.fetch_all.return_value = []

        segments = await segment_repo.get_segments("sess_001", "agent_001")

        assert segments == []

    @pytest.mark.asyncio
    async def test_search_by_embedding_returns_results(self, segment_repo, mock_client):
        mock_client.fetch_all.return_value = [
            {
                "id": 1,
                "session_id": "sess_001",
                "agent_id": "agent_001",
                "start_pos": 0,
                "end_pos": 10,
                "summary": "Matched segment",
                "tick": 1,
            }
        ]

        results = await segment_repo.search_by_embedding(
            agent_id="agent_001", embedding=b"fake_embedding", limit=5
        )

        assert len(results) == 1
        assert results[0]["summary"] == "Matched segment"

    @pytest.mark.asyncio
    async def test_search_by_embedding_respects_limit(self, segment_repo, mock_client):
        mock_client.fetch_all.return_value = []

        await segment_repo.search_by_embedding("agent_001", b"embedding", limit=10)

        call_args = mock_client.fetch_all.call_args[0]
        assert call_args[-1] == 10
