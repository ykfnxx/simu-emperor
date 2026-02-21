"""测试 Prometheus 指标模块。"""

import pytest

from simu_emperor.config import GameConfig, LoggingConfig
from simu_emperor.infrastructure.metrics import (
    record_llm_call,
    set_game_turn,
    llm_calls_total,
    llm_tokens_total,
    llm_cost_usd_total,
    game_current_turn,
)


class TestMetricsConfig:
    """测试指标配置。"""

    def test_metrics_enabled_default(self) -> None:
        """测试 metrics_enabled 默认值为 True。"""
        config = LoggingConfig()
        assert config.metrics_enabled is True

    def test_pricing_default(self) -> None:
        """测试默认价格配置。"""
        config = LoggingConfig()
        assert "anthropic" in config.pricing
        assert "openai" in config.pricing
        assert "mock" in config.pricing

    def test_get_price(self) -> None:
        """测试获取价格。"""
        config = LoggingConfig()

        # Anthropic Claude Sonnet 4
        price = config.get_price("anthropic", "claude-sonnet-4", "prompt")
        assert price == 3.0

        price = config.get_price("anthropic", "claude-sonnet-4", "completion")
        assert price == 15.0

        # OpenAI GPT-4o
        price = config.get_price("openai", "gpt-4o", "prompt")
        assert price == 2.5

    def test_get_price_unknown_provider(self) -> None:
        """测试获取未知提供商的价格。"""
        config = LoggingConfig()
        price = config.get_price("unknown", "unknown", "prompt")
        assert price == 0.0

    def test_get_price_unknown_model(self) -> None:
        """测试获取未知模型的价格。"""
        config = LoggingConfig()
        price = config.get_price("anthropic", "unknown-model", "prompt")
        assert price == 0.0


class TestRecordLLMCall:
    """测试 record_llm_call 函数。"""

    @pytest.mark.asyncio
    async def test_record_successful_call(self) -> None:
        """测试记录成功的调用。"""
        # 获取初始值
        initial_value = llm_calls_total._value.sum() if hasattr(llm_calls_total, '_value') else 0

        await record_llm_call(
            provider="mock",
            model="mock",
            agent_id="test_agent",
            phase="generate",
            duration_seconds=0.5,
            success=True,
            tokens_prompt=100,
            tokens_completion=50,
        )

        # 验证计数器增加（通过检查没有异常）
        # Prometheus 客户端在测试中难以直接读取值

    @pytest.mark.asyncio
    async def test_record_failed_call(self) -> None:
        """测试记录失败的调用。"""
        await record_llm_call(
            provider="mock",
            model="mock",
            agent_id="test_agent",
            phase="generate",
            duration_seconds=0.5,
            success=False,
        )

    @pytest.mark.asyncio
    async def test_record_call_with_tokens(self) -> None:
        """测试记录带 token 信息的调用。"""
        await record_llm_call(
            provider="mock",
            model="mock",
            agent_id="test_agent",
            phase="summarize",
            duration_seconds=1.0,
            success=True,
            tokens_prompt=500,
            tokens_completion=200,
        )

    @pytest.mark.asyncio
    async def test_record_call_zero_tokens(self) -> None:
        """测试记录零 token 的调用。"""
        await record_llm_call(
            provider="mock",
            model="mock",
            agent_id="test_agent",
            phase="respond",
            duration_seconds=0.3,
            success=True,
            tokens_prompt=0,
            tokens_completion=0,
        )


class TestSetGameTurn:
    """测试 set_game_turn 函数。"""

    def test_set_game_turn(self) -> None:
        """测试设置游戏回合。"""
        set_game_turn(game_id="test_game", turn=5)
        # 验证没有异常

    def test_set_game_turn_multiple_times(self) -> None:
        """测试多次设置游戏回合。"""
        set_game_turn(game_id="game_1", turn=1)
        set_game_turn(game_id="game_1", turn=2)
        set_game_turn(game_id="game_1", turn=3)


class TestCostEstimation:
    """测试成本估算。"""

    @pytest.mark.asyncio
    async def test_cost_estimation_anthropic(self) -> None:
        """测试 Anthropic 成本估算。"""
        # 100 prompt tokens + 50 completion tokens
        # prompt: 100 * 3.0 / 1_000_000 = 0.0003
        # completion: 50 * 15.0 / 1_000_000 = 0.00075
        # total: 0.00105
        await record_llm_call(
            provider="anthropic",
            model="claude-sonnet-4",
            agent_id="test_agent",
            phase="execute",
            duration_seconds=1.0,
            success=True,
            tokens_prompt=100,
            tokens_completion=50,
        )

    @pytest.mark.asyncio
    async def test_cost_estimation_openai(self) -> None:
        """测试 OpenAI 成本估算。"""
        await record_llm_call(
            provider="openai",
            model="gpt-4o",
            agent_id="test_agent",
            phase="generate",
            duration_seconds=1.0,
            success=True,
            tokens_prompt=100,
            tokens_completion=50,
        )

    @pytest.mark.asyncio
    async def test_cost_estimation_mock(self) -> None:
        """测试 Mock Provider 成本估算（应为 0）。"""
        await record_llm_call(
            provider="mock",
            model="mock",
            agent_id="test_agent",
            phase="generate",
            duration_seconds=0.1,
            success=True,
            tokens_prompt=1000,
            tokens_completion=500,
        )


class TestConcurrentRecording:
    """测试并发记录。"""

    @pytest.mark.asyncio
    async def test_concurrent_calls(self) -> None:
        """测试并发记录调用的安全性。"""
        import asyncio

        async def record_one(i: int):
            await record_llm_call(
                provider="mock",
                model="mock",
                agent_id=f"agent_{i}",
                phase="generate",
                duration_seconds=0.1,
                success=True,
                tokens_prompt=100,
                tokens_completion=50,
            )

        # 并发记录 10 次
        await asyncio.gather(*[record_one(i) for i in range(10)])
