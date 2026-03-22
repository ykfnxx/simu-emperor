"""Application Services container tests."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from simu_emperor.config import GameConfig


@pytest.fixture
def mock_settings(tmp_path: Path) -> GameConfig:
    """Create mock game settings."""
    settings = MagicMock(spec=GameConfig)
    settings.db_path = "game.db"
    settings.data_dir = tmp_path
    settings.log_dir = tmp_path / "logs"
    settings.llm = MagicMock()
    settings.llm.provider = "mock"
    settings.llm.api_key = "test-key"
    settings.llm.get_model = MagicMock(return_value="gpt-4")
    settings.llm.api_base = None
    settings.memory = MagicMock()
    settings.memory.memory_dir = str(tmp_path / "memory")
    return settings


@pytest.mark.asyncio
class TestApplicationServices:
    """Test ApplicationServices container."""

    async def test_resolve_memory_dir_from_config(self, mock_settings):
        """Test memory directory resolution from config."""
        from simu_emperor.application.services import ApplicationServices
        result = ApplicationServices._resolve_memory_dir(mock_settings)
        assert result == Path(mock_settings.memory.memory_dir)

    async def test_resolve_memory_dir_default(self, mock_settings):
        """Test default memory directory resolution."""
        from simu_emperor.application.services import ApplicationServices
        mock_settings.memory = None
        result = ApplicationServices._resolve_memory_dir(mock_settings)
        assert result == mock_settings.data_dir / "memory"

    @patch("simu_emperor.persistence.init_database")
    @patch("simu_emperor.memory.tape_metadata.TapeMetadataManager")
    @patch("simu_emperor.memory.tape_writer.TapeWriter")
    @patch("simu_emperor.session.manager.SessionManager")
    async def test_create_initializes_all_services(
        self, mock_session_mgr, mock_tape_writer, mock_tape_metadata_mgr, mock_init_db, mock_settings
    ):
        """Test create() factory initializes all services."""
        from simu_emperor.application.services import ApplicationServices

        # Setup mocks
        mock_conn = AsyncMock()
        mock_init_db.return_value = mock_conn
        mock_session_mgr.return_value.get_session = AsyncMock(return_value=None)
        mock_session_mgr.return_value.create_session = AsyncMock()

        services = await ApplicationServices.create(mock_settings)

        # All services should be initialized
        assert services.game_service is not None
        assert services.session_service is not None
        assert services.agent_service is not None
        assert services.group_chat_service is not None
        assert services.message_service is not None
        assert services.tape_service is not None

        # Cleanup
        await services.shutdown()

    @patch("simu_emperor.persistence.init_database")
    @patch("simu_emperor.persistence.close_database")
    @patch("simu_emperor.memory.tape_metadata.TapeMetadataManager")
    @patch("simu_emperor.memory.tape_writer.TapeWriter")
    @patch("simu_emperor.session.manager.SessionManager")
    async def test_start_and_shutdown(
        self, mock_session_mgr, mock_tape_writer, mock_tape_metadata_mgr, mock_close_db, mock_init_db, mock_settings
    ):
        """Test start() and shutdown() lifecycle methods."""
        from simu_emperor.application.services import ApplicationServices

        mock_conn = AsyncMock()
        mock_init_db.return_value = mock_conn
        mock_session_mgr.return_value.get_session = AsyncMock(return_value=None)
        mock_session_mgr.return_value.create_session = AsyncMock()

        services = await ApplicationServices.create(mock_settings)

        # Mock initialize methods
        services.game_service.initialize = AsyncMock()
        services.agent_service.initialize_agents = AsyncMock()
        services.game_service.shutdown = AsyncMock()
        services.agent_service.stop_all = AsyncMock()

        await services.start()
        services.game_service.initialize.assert_called_once()

        await services.shutdown()
        services.game_service.shutdown.assert_called_once()

    @patch("simu_emperor.persistence.init_database")
    @patch("simu_emperor.memory.tape_metadata.TapeMetadataManager")
    @patch("simu_emperor.memory.tape_writer.TapeWriter")
    @patch("simu_emperor.session.manager.SessionManager")
    async def test_property_accessors(
        self, mock_session_mgr, mock_tape_writer, mock_tape_metadata_mgr, mock_init_db, mock_settings
    ):
        """Test property accessors for infrastructure components."""
        from simu_emperor.application.services import ApplicationServices

        mock_conn = AsyncMock()
        mock_init_db.return_value = mock_conn
        mock_session_mgr.return_value.get_session = AsyncMock(return_value=None)
        mock_session_mgr.return_value.create_session = AsyncMock()

        services = await ApplicationServices.create(mock_settings)

        assert services.event_bus is not None
        assert services.repository is not None
        assert services.session_manager is not None

        await services.shutdown()
