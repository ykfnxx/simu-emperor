"""
测试 Mock LLM 提供商
"""

import pytest

from simu_emperor.llm.mock import MockProvider


class TestMockProvider:
    """测试 MockProvider 类"""

    @pytest.fixture
    def provider(self):
        """创建 MockProvider 实例"""
        return MockProvider(response="Test response")

    @pytest.mark.asyncio
    async def test_call(self, provider):
        """测试调用"""
        response = await provider.call("Hello")

        assert response == "Test response"
        assert provider.call_count == 1

    @pytest.mark.asyncio
    async def test_call_multiple_times(self, provider):
        """测试多次调用"""
        await provider.call("Test 1")
        await provider.call("Test 2")
        await provider.call("Test 3")

        assert provider.call_count == 3

    def test_set_response(self, provider):
        """测试设置响应"""
        provider.set_response("New response")

        assert provider.response == "New response"

    @pytest.mark.asyncio
    async def test_set_response_affects_call(self, provider):
        """测试设置响应影响调用"""
        await provider.call("Test")
        assert provider.call_count == 1

        provider.set_response("Different response")

        response = await provider.call("Test")
        assert response == "Different response"
        assert provider.call_count == 2

    def test_reset(self, provider):
        """测试重置"""
        provider.call_count = 10

        provider.reset()

        assert provider.call_count == 0
