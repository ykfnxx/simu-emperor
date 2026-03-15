"""
Unit tests for WebGameInstance

Tests the simplified WebGameInstance after V4 refactoring.
WebGameInstance now only manages lifecycle, all business logic is delegated to ApplicationServices.
"""

import pytest
from pydantic import BaseModel

from simu_emperor.adapters.web.game_instance import WebGameInstance


class MockLLMConfig(BaseModel):
    """Mock LLM 配置"""
    provider: str = "mock"
    api_key: str = "test_key"
    api_base: str | None = None
    model: str = "mock-model"


class TestWebGameInstance:
    """测试 WebGameInstance 类 (V4 重构后)"""

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

    def test_initialization(self, settings):
        """测试初始化"""
        instance = WebGameInstance(settings)

        assert instance.settings == settings
        assert instance._running is False
        assert instance.services is None

    @pytest.mark.asyncio
    async def test_shutdown_when_not_running(self, settings):
        """测试未运行时关闭"""
        instance = WebGameInstance(settings)

        # 未运行时关闭不应该抛出异常
        await instance.shutdown()

        assert instance._running is False

    def test_is_running_property(self, settings):
        """测试 is_running 属性"""
        instance = WebGameInstance(settings)

        assert instance.is_running is False

    # Full integration tests are skipped - they belong in integration/ directory
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
