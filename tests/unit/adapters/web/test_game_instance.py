"""
Unit tests for WebGameInstance
"""

import pytest
from pathlib import Path
from pydantic import BaseModel

from simu_emperor.adapters.web.game_instance import WebGameInstance


class MockLLMConfig(BaseModel):
    """Mock LLM 配置"""
    provider: str = "mock"
    api_key: str = "test_key"
    api_base: str | None = None
    model: str = "mock-model"


class TestWebGameInstance:
    """测试 WebGameInstance 类"""

    @pytest.fixture
    def settings(self, tmp_path):
        """创建测试配置"""
        class MockSettings:
            def __init__(self, tmp_path):
                self.data_dir = tmp_path / "data"
                self.data_dir.mkdir(parents=True, exist_ok=True)
                self.log_dir = tmp_path / "logs"
                self.log_dir.mkdir(parents=True, exist_ok=True)
                self.llm = MockLLMConfig()

        return MockSettings(tmp_path)

    def test_create_llm_provider_mock(self, settings):
        """测试创建 Mock LLM Provider"""
        instance = WebGameInstance(settings)
        provider = instance.create_llm_provider()

        # 检查 provider 不为 None
        assert provider is not None
        assert hasattr(provider, 'call')

    def test_initialization(self, settings):
        """测试初始化"""
        instance = WebGameInstance(settings)

        assert instance.settings == settings
        assert instance.player_id == "player:web"
        assert instance.session_id == "session:web:main"
        assert instance._running is False
        assert instance.event_bus is None
        assert instance.repository is None
        assert instance.calculator is None
        assert instance.agent_manager is None

    @pytest.mark.asyncio
    async def test_shutdown_when_not_running(self, settings):
        """测试未运行时关闭"""
        instance = WebGameInstance(settings)

        # 未运行时关闭不应该抛出异常
        await instance.shutdown()

        assert instance._running is False

    # 跳过耗时的完整集成测试
    # 这些测试应该在 integration/ 目录中进行
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Full initialization requires integration test environment")
    async def test_start_and_shutdown(self, settings):
        """测试启动和关闭（集成测试）"""
        pass

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Full initialization requires integration test environment")
    async def test_start_already_running(self, settings):
        """测试重复启动"""
        pass

    def test_db_path(self, settings):
        """测试数据库路径"""
        instance = WebGameInstance(settings)

        expected_path = str(settings.data_dir / "game.db")
        assert instance.db_path == expected_path
