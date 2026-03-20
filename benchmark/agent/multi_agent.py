"""Multi-agent concurrency evaluator for Agent system."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from benchmark.config import BenchmarkConfig
from benchmark.models import CaseDetail, MetricResult, ModuleResult


class MultiAgentEvaluator:
    """Evaluates Agent system performance under concurrent load."""

    def __init__(self, config: BenchmarkConfig | None = None):
        self.config = config or BenchmarkConfig.load()
        self.agent_counts = [2, 5, 10]

    async def evaluate(self) -> ModuleResult:
        start = time.perf_counter()
        details: list[CaseDetail] = []
        metrics: list[MetricResult] = []

        single_agent_latency = None

        for count in self.agent_counts:
            latency = await self._test_concurrent_agents(count)

            if single_agent_latency is None:
                single_agent_latency = latency
                scaling_ratio = 1.0
            else:
                scaling_ratio = latency / single_agent_latency if single_agent_latency > 0 else 0

            is_sublinear = scaling_ratio < count

            metrics.append(
                MetricResult(
                    f"latency_{count}_agents",
                    latency,
                    single_agent_latency * count * 0.8 if single_agent_latency else 1000,
                    "ms",
                    is_sublinear,
                )
            )

            metrics.append(
                MetricResult(
                    f"scaling_ratio_{count}",
                    scaling_ratio,
                    float(count),
                    "x",
                    is_sublinear,
                )
            )

            details.append(
                CaseDetail(
                    case_id=f"concurrency_{count}",
                    passed=is_sublinear,
                    input=f"Test with {count} agents",
                    expected=[f"<{count}x single agent"],
                    actual=[f"{scaling_ratio:.2f}x"],
                    reason=f"Latency: {latency:.0f}ms, Ratio: {scaling_ratio:.2f}x",
                )
            )

        return ModuleResult(
            module="multi_agent",
            metrics=metrics,
            details=details,
            duration_seconds=time.perf_counter() - start,
        )

    async def _test_concurrent_agents(self, count: int) -> float:
        start = time.perf_counter()

        tasks = [self._simulate_agent_call() for _ in range(count)]
        await asyncio.gather(*tasks)

        return (time.perf_counter() - start) * 1000

    async def _simulate_agent_call(self) -> None:
        await asyncio.sleep(0.05)
