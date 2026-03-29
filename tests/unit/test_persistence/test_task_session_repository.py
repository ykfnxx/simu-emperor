"""Tests for TaskSessionRepository."""

import pytest

from simu_emperor.persistence.repositories.task_session import TaskSessionRepository


@pytest.fixture
def task_session_repo(mock_client):
    return TaskSessionRepository(mock_client)


class TestTaskSessionRepository:
    @pytest.mark.asyncio
    async def test_create_inserts_task_session(self, task_session_repo, mock_client):
        await task_session_repo.create(
            task_id="task_001",
            session_id="sess_001",
            creator_id="player_001",
            task_type="query",
            timeout_seconds=300,
        )

        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args[0]
        assert "INSERT INTO task_sessions" in call_args[0]
        assert "task_001" in call_args

    @pytest.mark.asyncio
    async def test_create_with_defaults(self, task_session_repo, mock_client):
        await task_session_repo.create(
            task_id="task_002",
            session_id="sess_001",
            creator_id="player_001",
        )

        call_args = mock_client.execute.call_args[0]
        assert call_args[4] is None
        assert call_args[5] == 300

    @pytest.mark.asyncio
    async def test_get_returns_task(self, task_session_repo, mock_client):
        mock_client.fetch_one.return_value = {
            "task_id": "task_001",
            "session_id": "sess_001",
            "creator_id": "player_001",
            "status": "pending",
            "result": None,
        }

        result = await task_session_repo.get("task_001")

        assert result["task_id"] == "task_001"
        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_returns_none_if_not_found(self, task_session_repo, mock_client):
        mock_client.fetch_one.return_value = None

        result = await task_session_repo.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_status_to_completed(self, task_session_repo, mock_client):
        result_data = {"output": "success", "value": 42}

        await task_session_repo.update_status("task_001", "completed", result=result_data)

        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args[0]
        assert "UPDATE task_sessions" in call_args[0]
        assert "status = ?" in call_args[0]
        assert "completed" in call_args

    @pytest.mark.asyncio
    async def test_update_status_to_failed(self, task_session_repo, mock_client):
        result_data = {"error": "Something went wrong"}

        await task_session_repo.update_status("task_001", "failed", result=result_data)

        mock_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_without_result(self, task_session_repo, mock_client):
        await task_session_repo.update_status("task_001", "running")

        call_args = mock_client.execute.call_args[0]
        assert call_args[2] is None

    @pytest.mark.asyncio
    async def test_get_by_session_returns_tasks(self, task_session_repo, mock_client):
        mock_client.fetch_all.return_value = [
            {"task_id": "task_001", "session_id": "sess_001", "status": "completed"},
            {"task_id": "task_002", "session_id": "sess_001", "status": "pending"},
        ]

        results = await task_session_repo.get_by_session("sess_001")

        assert len(results) == 2
        assert results[0]["task_id"] == "task_001"

    @pytest.mark.asyncio
    async def test_get_by_session_returns_empty_list(self, task_session_repo, mock_client):
        mock_client.fetch_all.return_value = []

        results = await task_session_repo.get_by_session("sess_nonexistent")

        assert results == []

    @pytest.mark.asyncio
    async def test_get_pending_tasks_returns_only_pending(self, task_session_repo, mock_client):
        mock_client.fetch_all.return_value = [
            {"task_id": "task_001", "status": "pending"},
            {"task_id": "task_002", "status": "pending"},
        ]

        results = await task_session_repo.get_pending_tasks()

        assert len(results) == 2
        mock_client.fetch_all.assert_called_once()
        sql = mock_client.fetch_all.call_args[0][0]
        assert "status = 'pending'" in sql

    @pytest.mark.asyncio
    async def test_get_pending_tasks_returns_empty_list(self, task_session_repo, mock_client):
        mock_client.fetch_all.return_value = []

        results = await task_session_repo.get_pending_tasks()

        assert results == []
