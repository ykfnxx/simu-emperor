"""Tests for TaskMonitor."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from simu_emperor.session import SessionManager
from simu_emperor.session.task_monitor import TaskMonitor


@pytest.fixture
def mock_event_bus():
    return AsyncMock()


@pytest.fixture
def mock_llm_provider():
    return MagicMock()


@pytest.fixture
def mock_tape_metadata_mgr():
    return AsyncMock()


@pytest.fixture
def mock_tape_writer():
    writer = MagicMock()
    writer._get_tape_path = MagicMock(return_value="/tmp/test/tape.jsonl")
    return writer


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
async def task_monitor(session_manager, mock_event_bus):
    monitor = TaskMonitor(
        session_manager=session_manager,
        event_bus=mock_event_bus,
        check_interval=0.1,
    )
    return monitor


class TestTaskMonitor:
    """Test cases for TaskMonitor."""

    @pytest.mark.asyncio
    async def test_start_and_stop(self, task_monitor):
        await task_monitor.start()
        assert task_monitor._running is True
        assert task_monitor._task is not None

        await task_monitor.stop()
        assert task_monitor._running is False

    @pytest.mark.asyncio
    async def test_detect_timeout(self, task_monitor, session_manager):
        parent = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        task = await session_manager.create_session(
            parent_id="session:main",
            created_by="agent:test",
            timeout_seconds=-10,
        )

        # Task sessions start as ACTIVE, set to WAITING_REPLY for timeout monitoring
        await session_manager.update_session(
            task.session_id,
            timeout_at=past_time,
            status="WAITING_REPLY",
        )

        await task_monitor._check_timeouts()

        task_monitor.event_bus.send_event.assert_called_once()
        call_args = task_monitor.event_bus.send_event.call_args
        event = call_args[0][0]

        assert event.type == "task_timeout"
        assert event.session_id == task.session_id
        assert "agent:test" in event.dst

    @pytest.mark.asyncio
    async def test_no_timeout_for_active_session(self, task_monitor, session_manager):
        await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        await task_monitor._check_timeouts()

        task_monitor.event_bus.send_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_duplicate_timeout_notification(self, task_monitor, session_manager):
        parent = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        task = await session_manager.create_session(
            parent_id="session:main",
            created_by="agent:test",
            timeout_seconds=-10,
        )

        # Task sessions start as ACTIVE, set to WAITING_REPLY for timeout monitoring
        await session_manager.update_session(
            task.session_id,
            timeout_at=past_time,
            status="WAITING_REPLY",
        )

        await task_monitor._check_timeouts()
        assert task_monitor.event_bus.send_event.call_count == 1

        await task_monitor._check_timeouts()
        assert task_monitor.event_bus.send_event.call_count == 1
