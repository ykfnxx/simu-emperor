"""Tests for SessionManager."""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from simu_emperor.session import SessionManager, Session, MAX_TASK_DEPTH


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
async def session_manager(tmp_path, mock_llm_provider, mock_tape_metadata_mgr, mock_tape_writer):
    manager = SessionManager(
        memory_dir=tmp_path,
        llm_provider=mock_llm_provider,
        tape_metadata_mgr=mock_tape_metadata_mgr,
        tape_writer=mock_tape_writer,
    )
    return manager


class TestSessionManager:
    """Test cases for SessionManager."""

    @pytest.mark.asyncio
    async def test_create_main_session(self, session_manager):
        session = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        assert session.session_id == "session:main"
        assert session.parent_id is None
        assert session.status == "ACTIVE"
        assert session.created_by == "player"
        assert session.is_task is False

    @pytest.mark.asyncio
    async def test_create_task_session(self, session_manager):
        parent = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        task = await session_manager.create_session(
            parent_id="session:main",
            created_by="agent:test",
            timeout_seconds=300,
        )

        assert task.parent_id == "session:main"
        # Task sessions start as ACTIVE, only become WAITING_REPLY when async calls are made
        assert task.status == "ACTIVE"
        assert task.created_by == "agent:test"
        assert task.timeout_at is not None
        assert task.is_task is True
        assert "task:" in task.session_id

        assert task.session_id in parent.child_ids

    @pytest.mark.asyncio
    async def test_nesting_depth_limit(self, session_manager):
        current_id = "session:main"
        await session_manager.create_session(
            session_id=current_id,
            created_by="player",
        )

        for i in range(MAX_TASK_DEPTH):
            task = await session_manager.create_session(
                parent_id=current_id,
                created_by=f"agent:test{i}",
            )
            current_id = task.session_id

        with pytest.raises(ValueError, match="Task nesting depth exceeded"):
            await session_manager.create_session(
                parent_id=current_id,
                created_by="agent:test",
            )

    @pytest.mark.asyncio
    async def test_parent_not_found(self, session_manager):
        with pytest.raises(ValueError, match="Parent session not found"):
            await session_manager.create_session(
                parent_id="nonexistent",
                created_by="agent:test",
            )

    @pytest.mark.asyncio
    async def test_get_session(self, session_manager):
        await session_manager.create_session(
            session_id="session:test",
            created_by="player",
        )

        session = await session_manager.get_session("session:test")
        assert session is not None
        assert session.session_id == "session:test"

        nonexistent = await session_manager.get_session("nonexistent")
        assert nonexistent is None

    @pytest.mark.asyncio
    async def test_update_session(self, session_manager):
        await session_manager.create_session(
            session_id="session:test",
            created_by="player",
        )

        await session_manager.update_session(
            "session:test",
            status="FINISHED",
        )

        session = await session_manager.get_session("session:test")
        assert session.status == "FINISHED"

    @pytest.mark.asyncio
    async def test_get_parent_chain(self, session_manager):
        await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        task1 = await session_manager.create_session(
            session_id="task:1",
            parent_id="session:main",
            created_by="agent:test",
        )

        task2 = await session_manager.create_session(
            session_id="task:2",
            parent_id="task:1",
            created_by="agent:test",
        )

        chain = session_manager.get_parent_chain("task:2")
        assert len(chain) == 2
        assert chain[0].session_id == "task:1"
        assert chain[1].session_id == "session:main"

    @pytest.mark.asyncio
    async def test_calculate_depth(self, session_manager):
        await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        assert session_manager._calculate_depth("session:main") == 0

        task1 = await session_manager.create_session(
            session_id="task:1",
            parent_id="session:main",
            created_by="agent:test",
        )
        assert session_manager._calculate_depth("task:1") == 1

        task2 = await session_manager.create_session(
            session_id="task:2",
            parent_id="task:1",
            created_by="agent:test",
        )
        assert session_manager._calculate_depth("task:2") == 2

    @pytest.mark.asyncio
    async def test_get_waiting_sessions(self, session_manager):
        await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        task1 = await session_manager.create_session(
            parent_id="session:main",
            created_by="agent:test1",
        )

        task2 = await session_manager.create_session(
            parent_id="session:main",
            created_by="agent:test2",
        )

        # Task sessions start as ACTIVE, set to WAITING_REPLY to test the query
        await session_manager.update_session(task1.session_id, status="WAITING_REPLY")
        await session_manager.update_session(task2.session_id, status="WAITING_REPLY")

        waiting = session_manager.get_waiting_sessions()
        assert len(waiting) == 2
        assert all(s.status == "WAITING_REPLY" for s in waiting)

    @pytest.mark.asyncio
    async def test_remove_from_waiting_list(self, session_manager):
        parent = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        task = await session_manager.create_session(
            parent_id="session:main",
            created_by="agent:test",
        )

        parent.waiting_for_tasks = [task.session_id]
        await session_manager.save_manifest()

        is_empty, new_list = await session_manager.remove_from_waiting_list(
            "session:main",
            task.session_id,
        )

        assert is_empty is True
        assert len(new_list) == 0

    @pytest.mark.asyncio
    async def test_remove_from_waiting_list_partial(self, session_manager):
        parent = await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        task1 = await session_manager.create_session(
            session_id="task:1",
            parent_id="session:main",
            created_by="agent:test1",
        )

        task2 = await session_manager.create_session(
            session_id="task:2",
            parent_id="session:main",
            created_by="agent:test2",
        )

        parent.waiting_for_tasks = [task1.session_id, task2.session_id]
        await session_manager.save_manifest()

        is_empty, new_list = await session_manager.remove_from_waiting_list(
            "session:main",
            task1.session_id,
        )

        assert is_empty is False
        assert task2.session_id in new_list
        assert task1.session_id not in new_list

    @pytest.mark.asyncio
    async def test_set_agent_state(self, session_manager):
        """Test setting per-agent state."""
        await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        await session_manager.set_agent_state("session:main", "agent:test1", "WAITING_REPLY")

        session = await session_manager.get_session("session:main")
        assert session.agent_states == {"agent:test1": "WAITING_REPLY"}

    @pytest.mark.asyncio
    async def test_get_agent_state_lazy_initialization(self, session_manager):
        """Test that get_agent_state lazy-initializes agents to ACTIVE."""
        await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        # First access should lazy-initialize to ACTIVE
        state = await session_manager.get_agent_state("session:main", "agent:test1")
        assert state == "ACTIVE"

        session = await session_manager.get_session("session:main")
        assert session.agent_states == {"agent:test1": "ACTIVE"}

    @pytest.mark.asyncio
    async def test_get_agent_state_existing(self, session_manager):
        """Test getting existing agent state."""
        await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        # Set a specific state
        await session_manager.set_agent_state("session:main", "agent:test1", "WAITING_REPLY")

        # Get the state
        state = await session_manager.get_agent_state("session:main", "agent:test1")
        assert state == "WAITING_REPLY"

    @pytest.mark.asyncio
    async def test_get_agent_state_session_not_found(self, session_manager):
        """Test getting agent state from non-existent session."""
        state = await session_manager.get_agent_state("nonexistent", "agent:test1")
        assert state is None

    @pytest.mark.asyncio
    async def test_per_agent_state_independence(self, session_manager):
        """Test that each agent has independent state in a session."""
        await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        # Agent1 is waiting for reply
        await session_manager.set_agent_state("session:main", "agent:test1", "WAITING_REPLY")

        # Agent2 is still active (lazy initialization)
        state2 = await session_manager.get_agent_state("session:main", "agent:test2")
        assert state2 == "ACTIVE"

        session = await session_manager.get_session("session:main")
        assert session.agent_states == {
            "agent:test1": "WAITING_REPLY",
            "agent:test2": "ACTIVE",
        }

    @pytest.mark.asyncio
    async def test_agent_id_normalization(self, session_manager):
        """Test that agent IDs are normalized to 'agent:' prefix."""
        await session_manager.create_session(
            session_id="session:main",
            created_by="player",
        )

        # Set without 'agent:' prefix
        await session_manager.set_agent_state("session:main", "test1", "WAITING_REPLY")

        session = await session_manager.get_session("session:main")
        assert "agent:test1" in session.agent_states

        # Get without 'agent:' prefix should also work
        state = await session_manager.get_agent_state("session:main", "test1")
        assert state == "WAITING_REPLY"


class TestSession:
    """Test cases for Session dataclass."""

    def test_is_task_property(self):
        main_session = Session(
            session_id="session:main",
            created_by="player",
        )
        assert main_session.is_task is False

        task_session = Session(
            session_id="task:test",
            parent_id="session:main",
            created_by="agent:test",
        )
        assert task_session.is_task is True

    def test_to_dict_and_from_dict(self):
        original = Session(
            session_id="session:test",
            parent_id="session:main",
            status="WAITING_REPLY",
            created_by="agent:test",
            timeout_at=datetime.now(timezone.utc),
            root_event_id="evt_123",
            waiting_for_tasks=["task:1", "task:2"],
        )

        data = original.to_dict()
        restored = Session.from_dict("session:test", data)

        assert restored.session_id == original.session_id
        assert restored.parent_id == original.parent_id
        assert restored.status == original.status
        assert restored.created_by == original.created_by
        assert restored.timeout_at is not None
        assert restored.root_event_id == original.root_event_id
        assert restored.waiting_for_tasks == original.waiting_for_tasks
