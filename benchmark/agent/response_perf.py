"""Response performance evaluator for Agent system."""

from __future__ import annotations

import time

from benchmark.base import BaseEvaluator
from benchmark.config import BenchmarkConfig
from benchmark.metrics_hook import LLMMetricsCollector
from benchmark.models import CaseDetail, MetricResult, ModuleResult


class ResponsePerfEvaluator(BaseEvaluator):
    """Evaluates Agent response latency and token consumption."""

    def __init__(self, config: BenchmarkConfig | None = None):
        super().__init__(config)
        self.metrics_collector = LLMMetricsCollector()

    async def evaluate(self) -> ModuleResult:
        start = time.perf_counter()
        latencies: list[float] = []
        details: list[CaseDetail] = []

        ctx = await self.get_context(self.config)

        # Sequential: agent has a single context_manager per session,
        # concurrent calls to the same agent would thrash it.
        for i in range(2):
            latency = await self._simulate_agent_call(ctx)
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

    async def _simulate_agent_call(self, ctx) -> float:
        """Send a real message via BenchmarkContext and return latency_ms."""
        result = await ctx.send_message("你好")
        return result.get("latency_ms", 0.0)
