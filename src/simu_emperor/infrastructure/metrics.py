"""Prometheus 指标模块。"""
from __future__ import annotations

import asyncio
from functools import lru_cache

from prometheus_client import Counter, Gauge, Histogram, REGISTRY

# Counter: 调用次数
llm_calls_total = Counter(
    'llm_calls_total',
    'Total LLM API calls',
    ['provider', 'model', 'agent_id', 'phase', 'status'],
    registry=REGISTRY,
)

# Histogram: 延迟分布（自动计算 P50/P90/P95/P99）
llm_call_duration_seconds = Histogram(
    'llm_call_duration_seconds',
    'LLM call duration in seconds',
    ['provider', 'model', 'agent_id', 'phase'],
    buckets=[0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0],
    registry=REGISTRY,
)

# Counter: Token 消耗
llm_tokens_total = Counter(
    'llm_tokens_total',
    'Total tokens consumed',
    ['provider', 'model', 'type'],  # type: prompt | completion
    registry=REGISTRY,
)

# Counter: 累计成本（使用 Counter 而非 Gauge）
llm_cost_usd_total = Counter(
    'llm_cost_usd_total',
    'Total estimated cost in USD',
    ['provider', 'model'],
    registry=REGISTRY,
)

# Gauge: 当前回合
game_current_turn = Gauge(
    'game_current_turn',
    'Current game turn',
    ['game_id'],
    registry=REGISTRY,
)

# 异步锁（确保并发安全）
_lock = asyncio.Lock()


def _get_pricing_config():
    """获取价格配置（延迟加载，避免循环导入）。"""
    from simu_emperor.config import GameConfig
    config = GameConfig()
    return config.logging


async def record_llm_call(
    provider: str,
    model: str,
    agent_id: str,
    phase: str,
    duration_seconds: float,
    success: bool,
    tokens_prompt: int = 0,
    tokens_completion: int = 0,
) -> None:
    """记录一次 LLM 调用到 Prometheus 指标。

    Args:
        provider: LLM 提供商（anthropic/openai/mock）
        model: 模型名称
        agent_id: Agent ID
        phase: 调用阶段（summarize/respond/execute/stream）
        duration_seconds: 调用耗时（秒）
        success: 是否成功
        tokens_prompt: Prompt token 数
        tokens_completion: Completion token 数
    """
    async with _lock:
        status = "success" if success else "error"

        # 1. 调用次数
        llm_calls_total.labels(
            provider=provider,
            model=model,
            agent_id=agent_id,
            phase=phase,
            status=status,
        ).inc()

        # 2. 延迟分布
        llm_call_duration_seconds.labels(
            provider=provider,
            model=model,
            agent_id=agent_id,
            phase=phase,
        ).observe(duration_seconds)

        # 3. Token 消耗
        if tokens_prompt > 0:
            llm_tokens_total.labels(
                provider=provider,
                model=model,
                type="prompt",
            ).inc(tokens_prompt)

        if tokens_completion > 0:
            llm_tokens_total.labels(
                provider=provider,
                model=model,
                type="completion",
            ).inc(tokens_completion)

        # 4. 成本估算
        if tokens_prompt > 0 or tokens_completion > 0:
            config = _get_pricing_config()
            prompt_price = config.get_price(provider, model, "prompt")
            completion_price = config.get_price(provider, model, "completion")

            cost = (
                tokens_prompt * prompt_price / 1_000_000 +
                tokens_completion * completion_price / 1_000_000
            )

            if cost > 0:
                llm_cost_usd_total.labels(
                    provider=provider,
                    model=model,
                ).inc(cost)


def set_game_turn(game_id: str, turn: int) -> None:
    """设置当前游戏回合。

    Args:
        game_id: 游戏 ID
        turn: 当前回合数
    """
    game_current_turn.labels(game_id=game_id).set(turn)
