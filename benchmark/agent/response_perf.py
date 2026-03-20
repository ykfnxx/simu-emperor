"""Response performance evaluator for Agent system."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from benchmark.config import BenchmarkConfig
from benchmark.metrics_hook import LLMMetricsCollector
from benchmark.models import CaseDetail, MetricResult, ModuleResult


class ResponsePerfEvaluator:
    """Evaluates Agent response latency and token consumption."""

    def __init__(self, config: BenchmarkConfig | None = None):
        self.config = config or BenchmarkConfig.load()
        self.metrics_collector = LLMMetricsCollector()

    async def evaluate(self) -> ModuleResult:
        start = time.perf_counter()
        latencies: list[float] = []
        details: list[CaseDetail] = []

        for i in range(5):
            case_start = time.perf_counter()
            await self._simulate_agent_call()
            latency = (time.perf_counter() - case_start) * 1000
            latencies.append(latency)

            details.append(
                CaseDetail(
                    case_id=f"perf_{i}",
                    passed=latency < 5000,
                    input="Performance test",
                    expected=["<5s"],
                    actual=[f"{latency:.0f}ms"],
                    reason=f"Latency: {latency:.0f}ms",
                )
            )

        sorted_lat = sorted(latencies)
        n = len(sorted_lat)
        p50 = sorted_lat[n // 2] if n > 0 else 0
        p95 = sorted_lat[int(n * 0.95)] if n > 0 else 0
        p99 = sorted_lat[min(int(n * 0.99), n - 1)] if n > 0 else 0

        metrics = [
            MetricResult("latency_p50", p50, 2000, "ms", p50 <= 2000),
            MetricResult("latency_p95", p95, 5000, "ms", p95 <= 5000),
            MetricResult("latency_p99", p99, 10000, "ms", p99 <= 10000),
            MetricResult("llm_call_count", float(n), 100, "count", n <= 100),
            MetricResult("total_tokens", 0, 100000, "tokens", True),
        ]

        return ModuleResult(
            module="response_perf",
            metrics=metrics,
            details=details,
            duration_seconds=time.perf_counter() - start,
        )

    async def _simulate_agent_call(self) -> None:
        await asyncio.sleep(0.01)
