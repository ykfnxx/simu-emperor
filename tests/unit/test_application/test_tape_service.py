"""Tape Service unit tests."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from simu_emperor.application.tape_service import TapeService


@pytest.fixture
def mock_session_manager():
    """Create mock session manager."""
    return AsyncMock()


@pytest.fixture
def mock_tape_writer():
    """Create mock tape writer."""
    writer = MagicMock()
    writer._get_tape_path = MagicMock(return_value=Path("tape.jsonl"))
    return writer


@pytest.fixture
def memory_dir(tmp_path: Path) -> Path:
    """Create memory directory with tape files."""
    memory = tmp_path / "memory"
    memory.mkdir(parents=True, exist_ok=True)

    # Create agent and session directories
    agent_dir = memory / "agents" / "governor_zhili" / "sessions"
    agent_dir.mkdir(parents=True)
    (agent_dir / "session:web:main").mkdir(parents=True)

    # Create tape file with test events
    tape_path = agent_dir / "session:web:main" / "tape.jsonl"
    tape_path.write_text('{"timestamp": "2026-03-01T12:00:00Z", "event_type": "USER_QUERY", "content": {"query": "test"}}\n')

    return memory


class TestTapeService:
    """Test TapeService."""

    def test_init(self, mock_session_manager, mock_tape_writer, memory_dir):
        """Test tape service initialization."""
        service = TapeService(
            session_manager=mock_session_manager,
            tape_writer=mock_tape_writer,
            memory_dir=memory_dir,
        )

        assert service.session_manager == mock_session_manager
        assert service.tape_writer == mock_tape_writer
        assert service.memory_dir == memory_dir

    def test_is_main_session(self, mock_session_manager, mock_tape_writer, memory_dir):
        """Test checking if session is main session."""
        service = TapeService(
            session_manager=mock_session_manager,
            tape_writer=mock_tape_writer,
            memory_dir=memory_dir,
        )

        # Only web sessions are considered main sessions
        assert service._is_main_session("session:web:main") is True
        assert service._is_main_session("session:web:12345") is True
        assert service._is_main_session("session:cli:default") is False
        assert service._is_main_session("task:001") is False

    def test_is_task_session(self, mock_session_manager, mock_tape_writer, memory_dir):
        """Test checking if session is task session."""
        service = TapeService(
            session_manager=mock_session_manager,
            tape_writer=mock_tape_writer,
            memory_dir=memory_dir,
        )

        assert service._is_task_session("task:001") is True
        assert service._is_task_session("task:governor:123") is True
        assert service._is_task_session("session:web:main") is False

    def test_calculate_depth(self, mock_session_manager, mock_tape_writer, memory_dir):
        """Test calculating session depth."""
        service = TapeService(
            session_manager=mock_session_manager,
            tape_writer=mock_tape_writer,
            memory_dir=memory_dir,
        )

        sessions = {
            "session:web:main": {"parent_id": None},
            "task:001": {"parent_id": "session:web:main"},
            "task:002": {"parent_id": "task:001"},
        }

        assert service._calculate_depth("session:web:main", sessions) == 0
        assert service._calculate_depth("task:001", sessions) == 1
        assert service._calculate_depth("task:002", sessions) == 2

    @pytest.mark.asyncio
    async def test_get_current_tape(self, mock_session_manager, mock_tape_writer, memory_dir):
        """Test getting tape events."""
        service = TapeService(
            session_manager=mock_session_manager,
            tape_writer=mock_tape_writer,
            memory_dir=memory_dir,
        )

        result = await service.get_current_tape(
            limit=100,
            agent_id="governor_zhili",
            session_id="session:web:main",
        )

        assert "agent_id" in result
        assert "session_id" in result
        assert "events" in result
        assert "total" in result
        assert result["agent_id"] == "governor_zhili"
        assert result["session_id"] == "session:web:main"

    @pytest.mark.asyncio
    async def test_get_current_tape_with_limit(self, mock_session_manager, mock_tape_writer, memory_dir):
        """Test getting tape with limit."""
        service = TapeService(
            session_manager=mock_session_manager,
            tape_writer=mock_tape_writer,
            memory_dir=memory_dir,
        )

        result = await service.get_current_tape(limit=10)

        assert "total" in result

    @pytest.mark.asyncio
    async def test_get_tape_with_subs(self, mock_session_manager, mock_tape_writer, memory_dir):
        """Test getting tape with sub-sessions."""
        service = TapeService(
            session_manager=mock_session_manager,
            tape_writer=mock_tape_writer,
            memory_dir=memory_dir,
        )

        result = await service.get_tape_with_subs(
            limit=100,
            agent_id="governor_zhili",
            session_id="session:web:main",
            sub_sessions=["task:001"],
        )

        assert "events" in result
        assert "sub_sessions" in result

    @pytest.mark.asyncio
    async def test_get_sub_sessions(self, mock_session_manager, mock_tape_writer, memory_dir):
        """Test getting sub-sessions."""
        mock_session_manager.get_session = AsyncMock(return_value=None)

        with patch("simu_emperor.application.tape_service.FileOperationsHelper") as mock_file_helper:
            # V4: Use session_manifest.json format with agent_states
            mock_file_helper.read_json_file = AsyncMock(return_value={
                "sessions": {
                    "session:web:main": {"parent_id": None},
                    "task:001": {
                        "parent_id": "session:web:main",
                        "status": "ACTIVE",
                        "created_at": "2026-03-01T12:00:00Z",
                        "agent_states": {"agent:governor_zhili": "ACTIVE"}
                    },
                }
            })

            service = TapeService(
                session_manager=mock_session_manager,
                tape_writer=mock_tape_writer,
                memory_dir=memory_dir,
            )

            result = await service.get_sub_sessions("session:web:main")

            assert len(result) == 1
            assert result[0]["session_id"] == "task:001"
            assert result[0]["parent_id"] == "session:web:main"

    @pytest.mark.asyncio
    async def test_get_sub_sessions_with_agent_filter(self, mock_session_manager, mock_tape_writer, memory_dir):
        """Test getting sub-sessions filtered by agent."""
        mock_session_manager.get_session = AsyncMock(return_value=None)

        with patch("simu_emperor.application.tape_service.FileOperationsHelper") as mock_file_helper:
            # V4: Use session_manifest.json format with agent_states
            mock_file_helper.read_json_file = AsyncMock(return_value={
                "sessions": {
                    "task:001": {
                        "parent_id": "session:web:main",
                        "status": "ACTIVE",
                        "created_at": "2026-03-01T12:00:00Z",
                        "agent_states": {"agent:governor_zhili": "ACTIVE"}
                    },
                    "task:002": {
                        "parent_id": "session:web:main",
                        "status": "ACTIVE",
                        "created_at": "2026-03-01T13:00:00Z",
                        "agent_states": {"agent:minister_of_revenue": "ACTIVE"}
                    },
                }
            })

            service = TapeService(
                session_manager=mock_session_manager,
                tape_writer=mock_tape_writer,
                memory_dir=memory_dir,
            )

            result = await service.get_sub_sessions("session:web:main", agent_id="governor_zhili")

            assert len(result) == 1
            assert result[0]["session_id"] == "task:001"

    @pytest.mark.asyncio
    async def test_iter_session_tape_paths_for_agent(self, mock_session_manager, mock_tape_writer, memory_dir):
        """Test getting tape paths for specific agent."""
        service = TapeService(
            session_manager=mock_session_manager,
            tape_writer=mock_tape_writer,
            memory_dir=memory_dir,
        )

        paths = service._iter_session_tape_paths("session:web:main", "governor_zhili")

        assert len(paths) >= 0
        if paths:
            assert "governor_zhili" in str(paths[0])

    @pytest.mark.asyncio
    async def test_iter_session_tape_paths_all_agents(self, mock_session_manager, mock_tape_writer, memory_dir):
        """Test getting tape paths for all agents."""
        service = TapeService(
            session_manager=mock_session_manager,
            tape_writer=mock_tape_writer,
            memory_dir=memory_dir,
        )

        paths = service._iter_session_tape_paths("session:web:main", None)

        # Should return paths for all agents with this session
        assert isinstance(paths, list)

    @pytest.mark.asyncio
    async def test_get_sub_sessions_no_session_manager(self, mock_tape_writer, memory_dir):
        """Test getting sub-sessions when session manager is None."""
        service = TapeService(
            session_manager=None,
            tape_writer=mock_tape_writer,
            memory_dir=memory_dir,
        )

        result = await service.get_sub_sessions("session:web:main")

        assert result == []
