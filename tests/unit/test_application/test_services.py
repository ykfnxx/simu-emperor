"""Application Services container tests."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from simu_emperor.config import GameConfig


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


@pytest.mark.asyncio
class TestApplicationServices:
    """Test ApplicationServices container."""

    async def test_resolve_memory_dir_from_config(self, mock_settings):
        """Test memory directory resolution from config."""
        # Test when memory_dir is configured
        from simu_emperor.application.services import ApplicationServices
        result = ApplicationServices._resolve_memory_dir(mock_settings)
        assert result == Path(mock_settings.memory.memory_dir)

    async def test_resolve_memory_dir_default(self, mock_settings):
        """Test default memory directory resolution."""
        from simu_emperor.application.services import ApplicationServices
        # Test when memory_dir is not configured
        mock_settings.memory = None
        result = ApplicationServices._resolve_memory_dir(mock_settings)
        assert result == mock_settings.data_dir / "memory"
