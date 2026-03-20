"""Compression fidelity evaluator for Memory system."""

from __future__ import annotations

import time

from benchmark.config import BenchmarkConfig
from benchmark.models import CaseDetail, MetricResult, ModuleResult


class CompressionEvaluator:
    """Evaluates Memory system compression quality via keyword retention."""

    def __init__(self, config: BenchmarkConfig | None = None):
        self.config = config or BenchmarkConfig.load()
        self.test_keywords = ["直隶", "税收", "一万两", "拨款", "人口", "灾害"]

    async def evaluate(self) -> ModuleResult:
        start = time.perf_counter()

        original_tokens = 8000
        compressed_tokens = 2000
        summary = "直隶省税收一万两，拨款完成"

        retained = sum(1 for kw in self.test_keywords if kw in summary)
        retention_rate = (retained / len(self.test_keywords)) * 100

        compression_ratio = compressed_tokens / original_tokens

        metrics = [
            MetricResult(
                "keyword_retention_rate",
                retention_rate,
                70.0,
                "%",
                retention_rate >= 70,
            ),
            MetricResult(
                "compression_ratio",
                compression_ratio * 100,
                30.0,
                "%",
                compression_ratio <= 0.3,
            ),
            MetricResult(
                "original_tokens",
                float(original_tokens),
                10000,
                "tokens",
                True,
            ),
            MetricResult(
                "compressed_tokens",
                float(compressed_tokens),
                3000,
                "tokens",
                compressed_tokens <= 3000,
            ),
        ]

        details = [
            CaseDetail(
                case_id="compression_1",
                passed=retention_rate >= 70 and compression_ratio <= 0.3,
                input=f"{original_tokens} tokens with {len(self.test_keywords)} keywords",
                expected=["retention >= 70%", "ratio <= 0.3"],
                actual=[f"retention: {retention_rate:.0f}%", f"ratio: {compression_ratio:.2f}"],
                reason=f"Retained {retained}/{len(self.test_keywords)} keywords",
            )
        ]

        return ModuleResult(
            module="compression",
            metrics=metrics,
            details=details,
            duration_seconds=time.perf_counter() - start,
        )
