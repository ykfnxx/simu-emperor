"""Agent Service unit tests."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from simu_emperor.config import GameConfig
from simu_emperor.application.agent_service import AgentService


@pytest.fixture
def mock_settings(tmp_path: Path) -> GameConfig:
    """Create mock game settings."""
    settings = MagicMock(spec=GameConfig)
    settings.data_dir = tmp_path
    settings.llm = MagicMock()
    settings.llm.provider = "mock"
    settings.llm.api_key = "test-key"
    return settings


@pytest.fixture
def mock_event_bus():
    """Create mock event bus."""
    return MagicMock()


@pytest.fixture
def mock_llm_provider():
    """Create mock LLM provider."""
    return MagicMock()


@pytest.fixture
def mock_repository():
    """Create mock repository."""
    return AsyncMock()


@pytest.fixture
def mock_session_manager():
    """Create mock session manager."""
    return MagicMock()


class TestAgentService:
    """Test AgentService."""

    def test_init(self, mock_settings, mock_event_bus, mock_llm_provider, mock_repository, mock_session_manager):
        """Test agent service initialization."""
        service = AgentService(
            settings=mock_settings,
            event_bus=mock_event_bus,
            llm_provider=mock_llm_provider,
            repository=mock_repository,
            session_manager=mock_session_manager,
        )

        assert service.settings == mock_settings
        assert service.event_bus == mock_event_bus
        assert service.llm_provider == mock_llm_provider
        assert not service.is_initialized

    async def test_initialize_agents_default(self, mock_settings, mock_event_bus, mock_llm_provider, mock_repository, mock_session_manager):
        """Test initializing default agents."""
        with patch("simu_emperor.agents.manager.AgentManager") as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_mgr_cls.return_value = mock_mgr
            mock_mgr.initialize_agent = MagicMock(return_value=True)
            mock_mgr.get_active_agents = MagicMock(return_value=AgentService.DEFAULT_AGENTS)

            service = AgentService(
                settings=mock_settings,
                event_bus=mock_event_bus,
                llm_provider=mock_llm_provider,
                repository=mock_repository,
                session_manager=mock_session_manager,
            )

            await service.initialize_agents()

            assert service.is_initialized
            assert service.agent_manager == mock_mgr
            assert mock_mgr.initialize_agent.call_count == len(AgentService.DEFAULT_AGENTS)

    async def test_initialize_agents_custom_list(self, mock_settings, mock_event_bus, mock_llm_provider, mock_repository, mock_session_manager):
        """Test initializing custom agent list."""
        with patch("simu_emperor.agents.manager.AgentManager") as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_mgr_cls.return_value = mock_mgr
            mock_mgr.initialize_agent = MagicMock(return_value=True)

            service = AgentService(
                settings=mock_settings,
                event_bus=mock_event_bus,
                llm_provider=mock_llm_provider,
                repository=mock_repository,
                session_manager=mock_session_manager,
            )

            custom_agents = ["governor_zhili", "minister_of_revenue"]
            await service.initialize_agents(custom_agents)

            assert mock_mgr.initialize_agent.call_count == len(custom_agents)
            for agent_id in custom_agents:
                mock_mgr.initialize_agent.assert_any_call(agent_id)

    async def test_initialize_agents_idempotent(self, mock_settings, mock_event_bus, mock_llm_provider, mock_repository, mock_session_manager):
        """Test that initializing twice doesn't recreate manager."""
        with patch("simu_emperor.agents.manager.AgentManager") as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_mgr_cls.return_value = mock_mgr
            mock_mgr.initialize_agent = MagicMock(return_value=True)

            service = AgentService(
                settings=mock_settings,
                event_bus=mock_event_bus,
                llm_provider=mock_llm_provider,
                repository=mock_repository,
                session_manager=mock_session_manager,
            )

            await service.initialize_agents()
            first_manager = service.agent_manager

            await service.initialize_agents()
            second_manager = service.agent_manager

            assert first_manager == second_manager

    async def test_get_available_agents(self, mock_settings, mock_event_bus, mock_llm_provider, mock_repository, mock_session_manager):
        """Test getting available agents."""
        mock_mgr = MagicMock()
        mock_mgr.get_active_agents = MagicMock(return_value=["governor_zhili", "minister_of_revenue"])
        service = AgentService(
            settings=mock_settings,
            event_bus=mock_event_bus,
            llm_provider=mock_llm_provider,
            repository=mock_repository,
            session_manager=mock_session_manager,
        )
        service.agent_manager = mock_mgr

        result = await service.get_available_agents()

        assert result == ["governor_zhili", "minister_of_revenue"]

    async def test_get_available_agents_no_manager(self, mock_settings, mock_event_bus, mock_llm_provider, mock_repository, mock_session_manager):
        """Test getting available agents when manager not initialized."""
        service = AgentService(
            settings=mock_settings,
            event_bus=mock_event_bus,
            llm_provider=mock_llm_provider,
            repository=mock_repository,
            session_manager=mock_session_manager,
        )

        result = await service.get_available_agents()

        assert result == []

    async def test_get_active_agents(self, mock_settings, mock_event_bus, mock_llm_provider, mock_repository, mock_session_manager):
        """Test getting active agents."""
        mock_mgr = MagicMock()
        mock_mgr.get_active_agents = MagicMock(return_value=["governor_zhili"])
        service = AgentService(
            settings=mock_settings,
            event_bus=mock_event_bus,
            llm_provider=mock_llm_provider,
            repository=mock_repository,
            session_manager=mock_session_manager,
        )
        service.agent_manager = mock_mgr

        result = await service.get_active_agents()

        assert result == ["governor_zhili"]

    async def test_is_agent_available_true(self, mock_settings, mock_event_bus, mock_llm_provider, mock_repository, mock_session_manager):
        """Test checking if agent is available returns True."""
        mock_mgr = MagicMock()
        mock_mgr.get_active_agents = MagicMock(return_value=["governor_zhili", "minister_of_revenue"])
        service = AgentService(
            settings=mock_settings,
            event_bus=mock_event_bus,
            llm_provider=mock_llm_provider,
            repository=mock_repository,
            session_manager=mock_session_manager,
        )
        service.agent_manager = mock_mgr

        result = await service.is_agent_available("governor_zhili")

        assert result is True

    async def test_is_agent_available_false(self, mock_settings, mock_event_bus, mock_llm_provider, mock_repository, mock_session_manager):
        """Test checking if agent is available returns False."""
        mock_mgr = MagicMock()
        mock_mgr.get_active_agents = MagicMock(return_value=["governor_zhili"])
        service = AgentService(
            settings=mock_settings,
            event_bus=mock_event_bus,
            llm_provider=mock_llm_provider,
            repository=mock_repository,
            session_manager=mock_session_manager,
        )
        service.agent_manager = mock_mgr

        result = await service.is_agent_available("unknown_agent")

        assert result is False

    def test_get_agent(self, mock_settings, mock_event_bus, mock_llm_provider, mock_repository, mock_session_manager):
        """Test getting agent instance."""
        mock_agent = MagicMock()
        mock_mgr = MagicMock()
        mock_mgr.get_agent = MagicMock(return_value=mock_agent)
        service = AgentService(
            settings=mock_settings,
            event_bus=mock_event_bus,
            llm_provider=mock_llm_provider,
            repository=mock_repository,
            session_manager=mock_session_manager,
        )
        service.agent_manager = mock_mgr

        result = service.get_agent("governor_zhili")

        assert result == mock_agent
        mock_mgr.get_agent.assert_called_once_with("governor_zhili")

    async def test_stop_all(self, mock_settings, mock_event_bus, mock_llm_provider, mock_repository, mock_session_manager):
        """Test stopping all agents."""
        mock_mgr = MagicMock()
        service = AgentService(
            settings=mock_settings,
            event_bus=mock_event_bus,
            llm_provider=mock_llm_provider,
            repository=mock_repository,
            session_manager=mock_session_manager,
        )
        service.agent_manager = mock_mgr

        await service.stop_all()

        mock_mgr.stop_all.assert_called_once()

    def test_normalize_agent_id(self, mock_settings, mock_event_bus, mock_llm_provider, mock_repository, mock_session_manager):
        """Test agent ID normalization."""
        service = AgentService(
            settings=mock_settings,
            event_bus=mock_event_bus,
            llm_provider=mock_llm_provider,
            repository=mock_repository,
            session_manager=mock_session_manager,
        )

        assert service._normalize_agent_id("agent:governor_zhili") == "governor_zhili"
        assert service._normalize_agent_id("governor_zhili") == "governor_zhili"

    def test_default_agents_list(self):
        """Test default agents constant."""
        expected = [
            "governor_zhili",
            "governor_fujian",
            "governor_huguang",
            "governor_jiangnan",
            "governor_jiangxi",
            "governor_shaanxi",
            "governor_shandong",
            "governor_sichuan",
            "governor_zhejiang",
            "minister_of_revenue",
        ]
        assert AgentService.DEFAULT_AGENTS == expected
