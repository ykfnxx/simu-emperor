"""
Unit tests for Telegram session management
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from simu_emperor.adapters.telegram.session import GameSession, SessionManager


@pytest.fixture
def mock_settings():
    """Mock game settings"""
    settings = MagicMock()
    settings.data_dir = Path("/tmp/test_data")
    settings.log_dir = Path("/tmp/test_logs")
    settings.telegram = MagicMock()
    settings.telegram.session_timeout_hours = 24
    settings.telegram.max_sessions = 100
    return settings


@pytest.fixture
def mock_bot_application():
    """Mock Telegram Bot Application"""
    app = MagicMock()
    app.bot = MagicMock()
    app.bot.send_message = AsyncMock()
    return app


@pytest.fixture
def mock_llm_provider():
    """Mock LLM Provider"""
    provider = MagicMock()
    return provider


@pytest.mark.asyncio
async def test_game_session_creation(mock_settings, mock_bot_application, mock_llm_provider):
    """Test GameSession creation"""
    session = GameSession(
        chat_id=123,
        settings=mock_settings,
        bot_application=mock_bot_application,
        llm_provider=mock_llm_provider,
    )

    assert session.chat_id == 123
    assert session.player_id == "player:telegram:123"
    assert session.settings == mock_settings
    assert session.bot_application == mock_bot_application
    assert session.llm_provider == mock_llm_provider
    assert session.db_path.endswith("sessions/telegram_123.db")
    assert not session._running


@pytest.mark.asyncio
async def test_game_session_lifecycle(mock_settings, mock_bot_application, mock_llm_provider):
    """Test GameSession start and shutdown"""
    session = GameSession(
        chat_id=123,
        settings=mock_settings,
        bot_application=mock_bot_application,
        llm_provider=mock_llm_provider,
    )

    # Mock the dependencies
    with patch("simu_emperor.adapters.telegram.session.init_database") as mock_init_db:
        mock_conn = AsyncMock()
        mock_init_db.return_value = mock_conn

        with patch("simu_emperor.adapters.telegram.session.GameRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.load_state = AsyncMock(
                return_value={"provinces": [{"province_id": "zhili"}]}
            )  # Already has data
            mock_repo_cls.return_value = mock_repo

            with patch("simu_emperor.adapters.telegram.session.FileEventLogger") as mock_logger_cls:
                mock_logger = MagicMock()
                mock_logger_cls.return_value = mock_logger

                with patch("simu_emperor.adapters.telegram.session.EventBus") as mock_bus_cls:
                    mock_bus = MagicMock()
                    mock_bus.subscribe = MagicMock()
                    mock_bus_cls.return_value = mock_bus

                    with patch("simu_emperor.adapters.telegram.session.Calculator") as mock_calc:
                        mock_calc_instance = MagicMock()
                        mock_calc_instance.start = MagicMock()
                        mock_calc.return_value = mock_calc_instance

                        with patch(
                            "simu_emperor.adapters.telegram.session.AgentManager"
                        ) as mock_mgr:
                            mock_mgr_instance = MagicMock()
                            mock_mgr_instance.initialize_agent = MagicMock(return_value=True)
                            mock_mgr_instance.add_agent = MagicMock()
                            mock_mgr_instance._active_agents = {}
                            mock_mgr.return_value = mock_mgr_instance

                            await session.start()

                            assert session._running
                            assert session.event_bus is not None
                            assert session.repository is not None
                            assert session.calculator is not None
                            assert session.agent_manager is not None

                            await session.shutdown()
                            assert not session._running


@pytest.mark.asyncio
async def test_session_manager_get_session(mock_settings, mock_bot_application, mock_llm_provider):
    """Test SessionManager.get_session creates new session"""
    manager = SessionManager(mock_settings, mock_bot_application, mock_llm_provider)

    # Mock GameSession.start
    with patch.object(GameSession, "start", new=AsyncMock()):
        session = await manager.get_session(123)

        assert session.chat_id == 123
        assert 123 in manager._sessions
        assert 123 in manager._last_access
        assert manager.active_count == 1


@pytest.mark.asyncio
async def test_session_manager_reuse_session(
    mock_settings, mock_bot_application, mock_llm_provider
):
    """Test SessionManager.get_session reuses existing session"""
    manager = SessionManager(mock_settings, mock_bot_application, mock_llm_provider)

    # Mock GameSession.start
    with patch.object(GameSession, "start", new=AsyncMock()):
        session1 = await manager.get_session(123)
        session2 = await manager.get_session(123)

        assert session1 is session2
        assert manager.active_count == 1


@pytest.mark.asyncio
async def test_session_manager_multiple_sessions(
    mock_settings, mock_bot_application, mock_llm_provider
):
    """Test SessionManager handles multiple sessions"""
    manager = SessionManager(mock_settings, mock_bot_application, mock_llm_provider)

    # Mock GameSession.start
    with patch.object(GameSession, "start", new=AsyncMock()):
        session1 = await manager.get_session(123)
        session2 = await manager.get_session(456)

        assert session1 is not session2
        assert manager.active_count == 2


@pytest.mark.asyncio
async def test_session_manager_shutdown_all(mock_settings, mock_bot_application, mock_llm_provider):
    """Test SessionManager.shutdown_all"""
    manager = SessionManager(mock_settings, mock_bot_application, mock_llm_provider)

    # Mock GameSession
    with patch.object(GameSession, "start", new=AsyncMock()):
        with patch.object(GameSession, "shutdown", new=AsyncMock()) as mock_shutdown:
            await manager.get_session(123)
            await manager.get_session(456)

            await manager.shutdown_all()

            assert mock_shutdown.call_count == 2
            assert manager.active_count == 0


@pytest.mark.asyncio
async def test_session_manager_max_sessions_limit(
    mock_settings, mock_bot_application, mock_llm_provider
):
    """Test SessionManager respects max_sessions limit"""
    mock_settings.telegram.max_sessions = 2
    manager = SessionManager(mock_settings, mock_bot_application, mock_llm_provider)

    # Mock GameSession
    with patch.object(GameSession, "start", new=AsyncMock()):
        with patch.object(GameSession, "shutdown", new=AsyncMock()):
            await manager.get_session(1)
            await manager.get_session(2)
            assert manager.active_count == 2

            # Adding a 3rd session should remove the oldest (session 1)
            await manager.get_session(3)
            assert manager.active_count == 2
            assert 1 not in manager._sessions  # Oldest removed


@pytest.mark.asyncio
async def test_game_session_response_handler(
    mock_settings, mock_bot_application, mock_llm_provider
):
    """Test GameSession._on_response sends message to Telegram"""
    session = GameSession(
        chat_id=123,
        settings=mock_settings,
        bot_application=mock_bot_application,
        llm_provider=mock_llm_provider,
    )

    # Mock event bus
    session.event_bus = MagicMock()

    from simu_emperor.event_bus.event import Event
    from simu_emperor.event_bus.event_types import EventType

    event = Event(
        src="agent:governor_zhili",
        dst=[session.player_id],
        type=EventType.RESPONSE,
        payload={"narrative": "你好，陛下！"},
        session_id=session.session_id,
    )

    await session._on_response(event)

    # Verify bot.send_message was called
    mock_bot_application.bot.send_message.assert_called_once()
    call_args = mock_bot_application.bot.send_message.call_args
    assert call_args[1]["chat_id"] == 123
    assert "governor_zhili" in call_args[1]["text"]
    assert "你好，陛下！" in call_args[1]["text"]
