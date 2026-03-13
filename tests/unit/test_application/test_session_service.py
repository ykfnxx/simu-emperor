"""Session Service unit tests."""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from simu_emperor.application.session_service import SessionService, utcnow


@pytest.fixture
def mock_session_manager():
    """Create mock session manager."""
    manager = AsyncMock()
    manager.create_session = AsyncMock()
    manager.get_session = AsyncMock()
    return manager


@pytest.fixture
def mock_manifest_index():
    """Create mock manifest index."""
    return MagicMock()


@pytest.fixture
def memory_dir(tmp_path: Path) -> Path:
    """Create memory directory."""
    return tmp_path / "memory"


@pytest.fixture
def mock_agent_service():
    """Create mock agent service."""
    service = AsyncMock()
    service.get_available_agents = AsyncMock(return_value=["governor_zhili", "minister_of_revenue"])
    return service


class TestSessionService:
    """Test SessionService."""

    def test_init(self, mock_session_manager, mock_manifest_index, memory_dir):
        """Test session service initialization."""
        service = SessionService(
            session_manager=mock_session_manager,
            manifest_index=mock_manifest_index,
            memory_dir=memory_dir,
        )

        assert service.session_manager == mock_session_manager
        assert service.manifest_index == mock_manifest_index
        assert service.memory_dir == memory_dir
        assert service.main_session_id == "session:web:main"

    async def test_create_session(self, mock_session_manager, mock_manifest_index, memory_dir):
        """Test creating a new session."""
        mock_session_manager.create_session = AsyncMock(return_value=MagicMock(
            session_id="session:web:governor_zhili:20260301120000:abc123",
        ))

        service = SessionService(
            session_manager=mock_session_manager,
            manifest_index=mock_manifest_index,
            memory_dir=memory_dir,
        )

        result = await service.create_session("Test Session", "governor_zhili")

        assert "session_id" in result
        assert result["title"] == "Test Session"
        assert result["agent_id"] == "governor_zhili"
        assert result["is_current"] is True
        mock_session_manager.create_session.assert_called_once()

    async def test_create_session_default_title(self, mock_session_manager, mock_manifest_index, memory_dir):
        """Test creating session with default title."""
        mock_session_manager.create_session = AsyncMock()

        service = SessionService(
            session_manager=mock_session_manager,
            manifest_index=mock_manifest_index,
            memory_dir=memory_dir,
        )

        result = await service.create_session(None, "governor_zhili")

        assert "title" in result
        assert "会话" in result["title"] or "直隶巡抚" in result["title"]

    async def test_select_session(self, mock_session_manager, mock_manifest_index, memory_dir):
        """Test selecting an existing session."""
        # Setup mock to return session
        mock_session = MagicMock()
        mock_session.session_id = "session:web:existing:123456:abc"
        mock_session_manager.get_session = AsyncMock(return_value=mock_session)

        service = SessionService(
            session_manager=mock_session_manager,
            manifest_index=mock_manifest_index,
            memory_dir=memory_dir,
        )

        # Pre-populate session title
        service._session_titles["session:web:existing:123456:abc"] = "Existing Session"

        with patch.object(service, "list_agent_sessions", new=AsyncMock(return_value=[
            {
                "agent_id": "governor_zhili",
                "sessions": [
                    {"session_id": "session:web:existing:123456:abc", "is_current": False}
                ]
            }
        ])):
            result = await service.select_session("session:web:existing:123456:abc", "governor_zhili")

            assert result["session_id"] == "session:web:existing:123456:abc"
            assert result["agent_id"] == "governor_zhili"
            assert result["is_current"] is True

    async def test_select_session_auto_detect_agent(self, mock_session_manager, mock_manifest_index, memory_dir):
        """Test selecting session with auto-detected agent."""
        mock_session = MagicMock()
        mock_session_manager.get_session = AsyncMock(return_value=mock_session)

        service = SessionService(
            session_manager=mock_session_manager,
            manifest_index=mock_manifest_index,
            memory_dir=memory_dir,
        )

        with patch.object(service, "list_agent_sessions", new=AsyncMock(return_value=[
            {
                "agent_id": "minister_of_revenue",
                "sessions": [
                    {"session_id": "session:web:revenue:123456:def", "is_current": False}
                ]
            }
        ])):
            result = await service.select_session("session:web:revenue:123456:def", None)

            assert result["agent_id"] == "minister_of_revenue"

    async def test_select_session_not_found(self, mock_session_manager, mock_manifest_index, memory_dir):
        """Test selecting non-existent session raises error."""
        mock_session_manager.get_session = AsyncMock(return_value=None)

        service = SessionService(
            session_manager=mock_session_manager,
            manifest_index=mock_manifest_index,
            memory_dir=memory_dir,
        )

        with patch.object(service, "list_agent_sessions", new=AsyncMock(return_value=[])):
            with pytest.raises(ValueError, match="Session not found"):
                await service.select_session("session:web:nonexistent", None)

    async def test_get_session_for_agent(self, mock_session_manager, mock_manifest_index, memory_dir):
        """Test getting current session for agent."""
        service = SessionService(
            session_manager=mock_session_manager,
            manifest_index=mock_manifest_index,
            memory_dir=memory_dir,
        )

        # Set up a binding
        service._current_session_by_agent["governor_zhili"] = "session:web:custom"

        result = await service.get_session_for_agent("governor_zhili")

        assert result == "session:web:custom"

    async def test_get_session_for_agent_default(self, mock_session_manager, mock_manifest_index, memory_dir):
        """Test getting session returns default for unknown agent."""
        service = SessionService(
            session_manager=mock_session_manager,
            manifest_index=mock_manifest_index,
            memory_dir=memory_dir,
        )

        result = await service.get_session_for_agent("unknown_agent")

        assert result == "session:web:main"

    async def test_list_agent_sessions(self, mock_session_manager, mock_manifest_index, memory_dir):
        """Test listing sessions grouped by agent."""
        with patch("simu_emperor.application.session_service.FileOperationsHelper") as mock_file_helper:
            mock_file_helper.read_json_file = AsyncMock(return_value={
                "sessions": {
                    "session:web:main": {
                        "created_at": "2026-03-01T12:00:00Z",
                        "event_count": 10,
                        "agents": {"governor_zhili": {}}
                    },
                    "session:web:custom:123": {
                        "created_at": "2026-03-01T13:00:00Z",
                        "event_count": 5,
                        "agents": {"minister_of_revenue": {}}
                    }
                }
            })

            service = SessionService(
                session_manager=mock_session_manager,
                manifest_index=mock_manifest_index,
                memory_dir=memory_dir,
            )

            result = await service.list_agent_sessions()

            assert len(result) == 2
            agent_ids = {group["agent_id"] for group in result}
            assert "governor_zhili" in agent_ids
            assert "minister_of_revenue" in agent_ids
            # Verify agent_name is included
            agent_names = {group["agent_name"] for group in result}
            assert "直隶巡抚" in agent_names
            assert "户部尚书" in agent_names

    async def test_set_current_context(self, mock_session_manager, mock_manifest_index, memory_dir):
        """Test setting current context."""
        service = SessionService(
            session_manager=mock_session_manager,
            manifest_index=mock_manifest_index,
            memory_dir=memory_dir,
        )

        service.set_current_context("governor_zhili", "session:web:new_context")

        assert service._current_session_by_agent["governor_zhili"] == "session:web:new_context"

    def test_extract_title_from_id(self, mock_session_manager, mock_manifest_index, memory_dir):
        """Test extracting title from session ID."""
        service = SessionService(
            session_manager=mock_session_manager,
            manifest_index=mock_manifest_index,
            memory_dir=memory_dir,
        )

        assert service._extract_title_from_id("session:web:main") == "主会话"
        assert "session:web:custom" in service._extract_title_from_id("session:web:custom:123456")

    async def test_list_sessions_all(self, mock_session_manager, mock_manifest_index, memory_dir):
        """Test listing all sessions."""
        with patch("simu_emperor.application.session_service.FileOperationsHelper") as mock_file_helper:
            mock_file_helper.read_json_file = AsyncMock(return_value={
                "sessions": {
                    "session:web:main": {
                        "created_at": "2026-03-01T12:00:00Z",
                        "event_count": 10,
                        "agents": {"governor_zhili": {}}
                    }
                }
            })

            service = SessionService(
                session_manager=mock_session_manager,
                manifest_index=mock_manifest_index,
                memory_dir=memory_dir,
            )

            result = await service.list_sessions()

            assert len(result) >= 1

    def test_utcnow(self):
        """Test utcnow helper returns aware datetime."""
        result = utcnow()
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc
