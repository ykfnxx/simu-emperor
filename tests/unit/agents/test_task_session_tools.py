"""Unit tests for TaskSessionTools with permission validation."""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from simu_emperor.agents.tools.task_session_tools import TaskSessionTools
from simu_emperor.session import SessionManager


@pytest.fixture
def mock_llm_provider():
    return MagicMock()


@pytest.fixture
def mock_manifest_index():
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
async def session_manager(tmp_path, mock_llm_provider, mock_manifest_index, mock_tape_writer):
    manager = SessionManager(
        memory_dir=tmp_path,
        llm_provider=mock_llm_provider,
        manifest_index=mock_manifest_index,
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

        result = await task_tools_agent_a.finish_task_session(
            task_session_id=task.session_id,
            result="Task completed",
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

        with pytest.raises(ValueError, match="权限错误"):
            await task_tools_agent_b.finish_task_session(
                task_session_id=task.session_id,
                result="Unauthorized finish",
            )

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

        result = await task_tools_agent_a.fail_task_session(
            task_session_id=task.session_id,
            reason="Task failed",
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

        with pytest.raises(ValueError, match="权限错误"):
            await task_tools_agent_b.fail_task_session(
                task_session_id=task.session_id,
                reason="Unauthorized fail",
            )

    @pytest.mark.asyncio
    async def test_finish_non_task_session_fails(self, session_manager, task_tools_agent_a):
        main_session = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        with pytest.raises(ValueError, match="is not a task session"):
            await task_tools_agent_a.finish_task_session(
                task_session_id="session:main",
                result="Invalid operation",
            )

    @pytest.mark.asyncio
    async def test_fail_non_task_session_fails(self, session_manager, task_tools_agent_a):
        main_session = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        with pytest.raises(ValueError, match="is not a task session"):
            await task_tools_agent_a.fail_task_session(
                task_session_id="session:main",
                reason="Invalid operation",
            )

    @pytest.mark.asyncio
    async def test_finish_nonexistent_task_fails(self, task_tools_agent_a):
        with pytest.raises(ValueError, match="Task session not found"):
            await task_tools_agent_a.finish_task_session(
                task_session_id="task:nonexistent",
                result="Invalid",
            )

    @pytest.mark.asyncio
    async def test_finish_already_finished_task_fails(self, session_manager, task_tools_agent_a):
        """Test that finishing an already finished task raises an error."""
        parent = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        task = await session_manager.create_session(
            parent_id="session:main",
            created_by="agent:agent_a",
            timeout_seconds=300,
        )

        # First finish should succeed
        await task_tools_agent_a.finish_task_session(
            task_session_id=task.session_id,
            result="Task completed",
        )

        # Second finish should fail
        with pytest.raises(ValueError, match="已完成"):
            await task_tools_agent_a.finish_task_session(
                task_session_id=task.session_id,
                result="Duplicate finish",
            )

    @pytest.mark.asyncio
    async def test_finish_already_failed_task_fails(self, session_manager, task_tools_agent_a):
        """Test that finishing an already failed task raises an error."""
        parent = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        task = await session_manager.create_session(
            parent_id="session:main",
            created_by="agent:agent_a",
            timeout_seconds=300,
        )

        # First fail the task
        await task_tools_agent_a.fail_task_session(
            task_session_id=task.session_id,
            reason="Task failed",
        )

        # Trying to finish should fail
        with pytest.raises(ValueError, match="已失败"):
            await task_tools_agent_a.finish_task_session(
                task_session_id=task.session_id,
                result="Should not work",
            )

    @pytest.mark.asyncio
    async def test_fail_already_finished_task_fails(self, session_manager, task_tools_agent_a):
        """Test that failing an already finished task raises an error."""
        parent = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        task = await session_manager.create_session(
            parent_id="session:main",
            created_by="agent:agent_a",
            timeout_seconds=300,
        )

        # First finish the task
        await task_tools_agent_a.finish_task_session(
            task_session_id=task.session_id,
            result="Task completed",
        )

        # Trying to fail should fail
        with pytest.raises(ValueError, match="已完成"):
            await task_tools_agent_a.fail_task_session(
                task_session_id=task.session_id,
                reason="Should not work",
            )

    @pytest.mark.asyncio
    async def test_fail_already_failed_task_fails(self, session_manager, task_tools_agent_a):
        """Test that failing an already failed task raises an error."""
        parent = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        task = await session_manager.create_session(
            parent_id="session:main",
            created_by="agent:agent_a",
            timeout_seconds=300,
        )

        # First fail should succeed
        await task_tools_agent_a.fail_task_session(
            task_session_id=task.session_id,
            reason="Task failed",
        )

        # Second fail should also fail
        with pytest.raises(ValueError, match="已失败"):
            await task_tools_agent_a.fail_task_session(
                task_session_id=task.session_id,
                reason="Duplicate fail",
            )
