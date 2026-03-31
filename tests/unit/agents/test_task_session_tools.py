"""Unit tests for TaskSessionTools with permission validation."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from simu_emperor.agents.tools.task_session_tools import TaskSessionTools
from simu_emperor.session import SessionManager


@pytest.fixture
def mock_llm_provider():
    return MagicMock()


@pytest.fixture
def mock_tape_metadata_mgr():
    return AsyncMock()


@pytest.fixture
def mock_tape_writer():
    writer = MagicMock()
    writer._get_tape_path = MagicMock(return_value=Path("/tmp/test/tape.jsonl"))
    return writer


@pytest.fixture
def mock_event_bus():
    return AsyncMock()


@pytest.fixture
async def session_manager(tmp_path, mock_llm_provider, mock_tape_metadata_mgr, mock_tape_writer):
    manager = SessionManager(
        memory_dir=tmp_path,
        llm_provider=mock_llm_provider,
        tape_metadata_mgr=mock_tape_metadata_mgr,
        tape_writer=mock_tape_writer,
    )
    return manager


@pytest.fixture
def task_tools_agent_a(session_manager, mock_event_bus):
    return TaskSessionTools(
        agent_id="agent_a",
        session_manager=session_manager,
        event_bus=mock_event_bus,
    )


@pytest.fixture
def task_tools_agent_b(session_manager, mock_event_bus):
    return TaskSessionTools(
        agent_id="agent_b",
        session_manager=session_manager,
        event_bus=mock_event_bus,
    )


class TestTaskSessionToolsPermission:
    """Test cases for TaskSessionTools permission validation."""

    @pytest.mark.asyncio
    async def test_finish_own_task_succeeds(self, session_manager, task_tools_agent_a):
        parent = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        task = await session_manager.create_session(
            parent_id="session:main",
            created_by="agent:agent_a",
            timeout_seconds=300,
        )

        result = await task_tools_agent_a._finish_task(
            task.session_id,
            "Task completed",
        )

        assert result["success"] is True
        assert result["status"] == "FINISHED"

    @pytest.mark.asyncio
    async def test_finish_others_task_fails(
        self, session_manager, task_tools_agent_a, task_tools_agent_b
    ):
        parent = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        task = await session_manager.create_session(
            parent_id="session:main",
            created_by="agent:agent_a",
            timeout_seconds=300,
        )

        result = await task_tools_agent_b._finish_task(
            task.session_id,
            "Unauthorized finish",
        )
        assert result["success"] is False
        assert "权限错误" in result["error"]

    @pytest.mark.asyncio
    async def test_fail_own_task_succeeds(self, session_manager, task_tools_agent_a):
        parent = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        task = await session_manager.create_session(
            parent_id="session:main",
            created_by="agent:agent_a",
            timeout_seconds=300,
        )

        result = await task_tools_agent_a._fail_task(
            task.session_id,
            "Task failed",
        )

        assert result["success"] is True
        assert result["status"] == "FAILED"

    @pytest.mark.asyncio
    async def test_fail_others_task_fails(
        self, session_manager, task_tools_agent_a, task_tools_agent_b
    ):
        parent = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        task = await session_manager.create_session(
            parent_id="session:main",
            created_by="agent:agent_a",
            timeout_seconds=300,
        )

        result = await task_tools_agent_b._fail_task(
            task.session_id,
            "Unauthorized fail",
        )
        assert result["success"] is False
        assert "权限错误" in result["error"]

    @pytest.mark.asyncio
    async def test_finish_non_task_session_fails(self, session_manager, task_tools_agent_a):
        main_session = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        result = await task_tools_agent_a._finish_task(
            "session:main",
            "Invalid operation",
        )
        assert result["success"] is False
        assert "not a task session" in result["error"]

    @pytest.mark.asyncio
    async def test_fail_non_task_session_fails(self, session_manager, task_tools_agent_a):
        main_session = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        result = await task_tools_agent_a._fail_task(
            "session:main",
            "Invalid operation",
        )
        assert result["success"] is False
        assert "not a task session" in result["error"]

    @pytest.mark.asyncio
    async def test_finish_nonexistent_task_fails(self, task_tools_agent_a):
        result = await task_tools_agent_a._finish_task(
            "task:nonexistent",
            "Invalid",
        )
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_finish_already_finished_task_fails(self, session_manager, task_tools_agent_a):
        parent = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        task = await session_manager.create_session(
            parent_id="session:main",
            created_by="agent:agent_a",
            timeout_seconds=300,
        )

        await task_tools_agent_a._finish_task(
            task.session_id,
            "Task completed",
        )

        result = await task_tools_agent_a._finish_task(
            task.session_id,
            "Duplicate finish",
        )
        assert result["success"] is False
        assert "已结束" in result["error"]

    @pytest.mark.asyncio
    async def test_finish_already_failed_task_fails(self, session_manager, task_tools_agent_a):
        parent = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        task = await session_manager.create_session(
            parent_id="session:main",
            created_by="agent:agent_a",
            timeout_seconds=300,
        )

        await task_tools_agent_a._fail_task(
            task.session_id,
            "Task failed",
        )

        result = await task_tools_agent_a._finish_task(
            task.session_id,
            "Should not work",
        )
        assert result["success"] is False
        assert "已结束" in result["error"]

    @pytest.mark.asyncio
    async def test_fail_already_finished_task_fails(self, session_manager, task_tools_agent_a):
        parent = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        task = await session_manager.create_session(
            parent_id="session:main",
            created_by="agent:agent_a",
            timeout_seconds=300,
        )

        await task_tools_agent_a._finish_task(
            task.session_id,
            "Task completed",
        )

        result = await task_tools_agent_a._fail_task(
            task.session_id,
            "Should not work",
        )
        assert result["success"] is False
        assert "已结束" in result["error"]

    @pytest.mark.asyncio
    async def test_fail_already_failed_task_fails(self, session_manager, task_tools_agent_a):
        parent = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        task = await session_manager.create_session(
            parent_id="session:main",
            created_by="agent:agent_a",
            timeout_seconds=300,
        )

        await task_tools_agent_a._fail_task(
            task.session_id,
            "Task failed",
        )

        result = await task_tools_agent_a._fail_task(
            task.session_id,
            "Duplicate fail",
        )
        assert result["success"] is False
        assert "已结束" in result["error"]
