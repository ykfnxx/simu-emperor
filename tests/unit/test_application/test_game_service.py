"""Game Service unit tests."""

import pytest
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from simu_emperor.config import GameConfig
from simu_emperor.application.game_service import GameService
from simu_emperor.engine.models.base_data import NationData


@pytest.fixture
def mock_settings(tmp_path: Path) -> GameConfig:
    """Create mock game settings."""
    settings = MagicMock(spec=GameConfig)
    settings.data_dir = tmp_path
    settings.log_dir = tmp_path / "logs"
    settings.llm = MagicMock()
    settings.llm.provider = "mock"
    settings.llm.api_key = "test-key"
    settings.memory = MagicMock()
    settings.memory.memory_dir = str(tmp_path / "memory")
    return settings


@pytest.fixture
def mock_repository():
    """Create mock repository with V4 flat structure."""
    repo = AsyncMock()
    repo.load_state = AsyncMock(return_value={
        "turn": 5,
        "imperial_treasury": 100000,
        "provinces": {
            "zhili": {
                "province_id": "zhili",
                "name": "直隶",
                "production_value": 100000,
                "population": 1000000,
                "fixed_expenditure": 50000,
                "stockpile": 1200000,
            }
        },
    })
    repo.get_current_turn = AsyncMock(return_value=5)
    return repo


@pytest.fixture
def mock_event_bus():
    """Create mock event bus."""
    return MagicMock()


@pytest.fixture
def mock_llm_provider():
    """Create mock LLM provider."""
    return MagicMock()


@pytest.fixture
def memory_dir(tmp_path: Path) -> Path:
    """Create memory directory."""
    return tmp_path / "memory"


@pytest.mark.asyncio
class TestGameService:
    """Test GameService."""

    async def test_initialize(self, mock_settings, mock_repository, mock_event_bus, mock_llm_provider, memory_dir):
        """Test game service initialization."""
        with patch("simu_emperor.engine.engine.Engine") as mock_engine_cls, \
             patch("simu_emperor.engine.tick_coordinator.TickCoordinator") as mock_tick_coord_cls, \
             patch("simu_emperor.common.utils.file_utils.FileOperationsHelper") as mock_file_helper:

            # Setup mocks
            mock_engine = MagicMock()
            mock_engine_cls.return_value = mock_engine
            mock_tick_coord = MagicMock()
            mock_tick_coord.start = AsyncMock()
            mock_tick_coord_cls.return_value = mock_tick_coord
            mock_file_helper.read_json_file = AsyncMock(return_value=None)

            service = GameService(
                settings=mock_settings,
                repository=mock_repository,
                event_bus=mock_event_bus,
                llm_provider=mock_llm_provider,
                memory_dir=memory_dir,
            )

            await service.initialize()

            assert service.is_running
            assert service.engine == mock_engine
            assert service.tick_coordinator == mock_tick_coord
            mock_tick_coord.start.assert_called_once()

    async def test_shutdown(self, mock_settings, mock_repository, mock_event_bus, mock_llm_provider, memory_dir):
        """Test game service shutdown."""
        service = GameService(
            settings=mock_settings,
            repository=mock_repository,
            event_bus=mock_event_bus,
            llm_provider=mock_llm_provider,
            memory_dir=memory_dir,
        )

        # Mock tick coordinator
        mock_tick_coord = MagicMock()
        mock_tick_coord.stop = AsyncMock()
        service._tick_coordinator = mock_tick_coord
        service._running = True

        await service.shutdown()

        assert not service.is_running
        mock_tick_coord.stop.assert_called_once()

    async def test_get_overview(self, mock_settings, mock_repository, mock_event_bus, mock_llm_provider, memory_dir):
        """Test getting empire overview (V4 format)."""
        service = GameService(
            settings=mock_settings,
            repository=mock_repository,
            event_bus=mock_event_bus,
            llm_provider=mock_llm_provider,
            memory_dir=memory_dir,
        )

        overview = await service.get_overview()

        assert overview["turn"] == 5
        assert overview["treasury"] == 100000
        assert overview["population"] == 1000000
        assert overview["province_count"] == 1
        # V4: no military or happiness fields

    async def test_get_overview_empty_state(self, mock_settings, mock_event_bus, mock_llm_provider, memory_dir):
        """Test getting overview with empty state (V4 format)."""
        mock_repo = AsyncMock()
        mock_repo.load_state = AsyncMock(return_value={})

        service = GameService(
            settings=mock_settings,
            repository=mock_repo,
            event_bus=mock_event_bus,
            llm_provider=mock_llm_provider,
            memory_dir=memory_dir,
        )

        overview = await service.get_overview()

        assert overview["turn"] == 0
        assert overview["treasury"] == 0
        assert overview["population"] == 0
        assert overview["province_count"] == 0
        # V4: no military or happiness fields

    async def test_get_overview_no_repository(self, mock_settings, mock_event_bus, mock_llm_provider, memory_dir):
        """Test getting overview when repository is None."""
        service = GameService(
            settings=mock_settings,
            repository=None,
            event_bus=mock_event_bus,
            llm_provider=mock_llm_provider,
            memory_dir=memory_dir,
        )

        overview = await service.get_overview()

        assert overview["turn"] == 0
        assert overview["treasury"] == 0
        assert overview["population"] == 0

    async def test_load_initial_state_from_file(self, mock_settings, mock_repository, mock_event_bus, mock_llm_provider, memory_dir):
        """Test loading initial state from JSON config."""
        with patch("simu_emperor.application.game_service.FileOperationsHelper") as mock_file_helper:
            # Mock config file
            mock_file_helper.read_json_file = AsyncMock(return_value={
                "nation": {
                    "turn": 10,
                    "base_tax_rate": "0.15",
                    "tribute_rate": "0.85",
                    "imperial_treasury": "500000",
                },
                "provinces": {
                    "zhili": {
                        "province_id": "zhili",
                        "name": "直隶",
                        "production_value": "200000",
                        "population": "3000000",
                        "fixed_expenditure": "60000",
                        "stockpile": "1500000",
                    }
                }
            })

            service = GameService(
                settings=mock_settings,
                repository=mock_repository,
                event_bus=mock_event_bus,
                llm_provider=mock_llm_provider,
                memory_dir=memory_dir,
            )

            state = await service._load_initial_state()

            assert state.turn == 10
            assert state.base_tax_rate == Decimal("0.15")
            assert state.tribute_rate == Decimal("0.85")
            assert state.imperial_treasury == Decimal("500000")
            assert "zhili" in state.provinces
            assert state.provinces["zhili"].name == "直隶"

    async def test_load_initial_state_fallback(self, mock_settings, mock_repository, mock_event_bus, mock_llm_provider, memory_dir):
        """Test loading initial state with fallback when config missing."""
        with patch("simu_emperor.application.game_service.FileOperationsHelper") as mock_file_helper:
            mock_file_helper.read_json_file = AsyncMock(return_value=None)

            service = GameService(
                settings=mock_settings,
                repository=mock_repository,
                event_bus=mock_event_bus,
                llm_provider=mock_llm_provider,
                memory_dir=memory_dir,
            )

            state = await service._load_initial_state()

            assert state.turn == 0
            assert state.base_tax_rate == Decimal("0.10")
            assert "zhili" in state.provinces

    async def test_get_state_from_engine(self, mock_settings, mock_repository, mock_event_bus, mock_llm_provider, memory_dir):
        """Test getting state from engine."""
        expected_state = NationData(
            turn=5,
            base_tax_rate=Decimal("0.10"),
            imperial_treasury=Decimal("100000"),
            provinces={},
        )

        service = GameService(
            settings=mock_settings,
            repository=mock_repository,
            event_bus=mock_event_bus,
            llm_provider=mock_llm_provider,
            memory_dir=memory_dir,
        )

        # Mock engine
        mock_engine = MagicMock()
        mock_engine.get_state = MagicMock(return_value=expected_state)
        service._engine = mock_engine

        state = await service.get_state()

        assert state == expected_state
        mock_engine.get_state.assert_called_once()

    async def test_calculate_overview_with_nested_base_data(self, mock_settings, mock_repository, mock_event_bus, mock_llm_provider, memory_dir):
        """Test overview calculation with nested base_data structure (V4 format)."""
        mock_repo = AsyncMock()
        mock_repo.load_state = AsyncMock(return_value={
            "base_data": {
                "turn": 8,
                "imperial_treasury": 200000,
                "provinces": {
                    "zhejiang": {
                        "province_id": "zhejiang",
                        "name": "浙江",
                        "production_value": 150000,
                        "population": 500000,
                        "fixed_expenditure": 40000,
                        "stockpile": 800000,
                    }
                },
            }
        })

        service = GameService(
            settings=mock_settings,
            repository=mock_repo,
            event_bus=mock_event_bus,
            llm_provider=mock_llm_provider,
            memory_dir=memory_dir,
        )

        overview = await service.get_overview()

        assert overview["turn"] == 8
        assert overview["treasury"] == 200000
        assert overview["population"] == 500000
        assert overview["province_count"] == 1
        # V4: no military or happiness fields

    async def test_get_overview_with_deltas(self, mock_settings, mock_repository, mock_event_bus, mock_llm_provider, memory_dir):
        """Test getting empire overview with delta values."""
        service = GameService(
            settings=mock_settings,
            repository=mock_repository,
            event_bus=mock_event_bus,
            llm_provider=mock_llm_provider,
            memory_dir=memory_dir,
        )

        # Mock engine with delta values
        from decimal import Decimal
        mock_engine = MagicMock()
        mock_engine.get_province_delta = MagicMock(side_effect=lambda province_id, field: {
            ("_nation", "imperial_treasury"): Decimal("5000"),
            ("_nation", "population"): Decimal("50000"),
        }.get((province_id, field), Decimal("0")))
        service._engine = mock_engine

        overview = await service.get_overview()

        assert overview["turn"] == 5
        assert overview["treasury"] == 100000
        assert overview["population"] == 1000000
        assert overview["province_count"] == 1
        assert overview["treasury_delta"] == 5000
        assert overview["population_delta"] == 50000
