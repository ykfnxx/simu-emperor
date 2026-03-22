"""Cross-session consistency evaluator for Memory system."""

from __future__ import annotations

import time
import uuid
from typing import Any

from benchmark.base import BaseEvaluator
from benchmark.config import BenchmarkConfig
from benchmark.models import CaseDetail, MetricResult, ModuleResult


class CrossSessionEvaluator(BaseEvaluator):
    """Evaluates Memory system consistency across sessions using Jaccard similarity."""

    def __init__(self, config: BenchmarkConfig | None = None):
        super().__init__(config)
        self.query_runs = 3

    async def evaluate(self) -> ModuleResult:
        start = time.perf_counter()

        ctx = await self.get_context(self.config)
        agent_id = "governor_zhili"

        # Inject events into multiple sessions so cross-session search has data
        for i in range(3):
            session_id = f"bench_cross_{i}:{uuid.uuid4().hex[:8]}"
            await ctx.inject_memory_events(
                session_id=session_id,
                events=self._build_session_events(i),
                agent_id=agent_id,
            )

        test_queries = [
            "直隶省今年的税收情况如何？",
            "最近有哪些灾害？",
            "拨款记录",
        ]

        details: list[CaseDetail] = []
        consistency_scores: list[float] = []

        for query in test_queries:
            results = []
            for _ in range(self.query_runs):
                segments = await ctx.search_tape_segments(query)
                event_ids = set()
                for seg in segments:
                    for evt in seg.get("events", []):
                        eid = evt.get("event_id", "")
                        if eid:
                            event_ids.add(eid)
                results.append(event_ids)

            similarities = []
            for i in range(len(results)):
                for j in range(i + 1, len(results)):
                    intersection = len(results[i] & results[j])
                    union = len(results[i] | results[j])
                    sim = intersection / union if union > 0 else 1.0
                    similarities.append(sim)

            avg_similarity = sum(similarities) / len(similarities) if similarities else 1.0
            consistency_scores.append(avg_similarity)

            details.append(
                CaseDetail(
                    case_id=query[:20],
                    passed=avg_similarity >= 0.9,
                    input=query,
                    expected=[">= 90% consistency"],
                    actual=[f"{avg_similarity * 100:.0f}%"],
                    reason=f"Jaccard similarity: {avg_similarity:.2f}",
                )
            )

        avg_consistency = (
            (sum(consistency_scores) / len(consistency_scores)) * 100 if consistency_scores else 0
        )

        metrics = [
            MetricResult(
                "cross_session_consistency",
                avg_consistency,
                90.0,
                "%",
                avg_consistency >= 90,
            ),
            MetricResult(
                "queries_tested",
                float(len(test_queries)),
                10,
                "count",
                True,
            ),
        ]

        return ModuleResult(
            module="cross_session",
            metrics=metrics,
            details=details,
            duration_seconds=time.perf_counter() - start,
        )

    @staticmethod
    def _build_session_events(session_index: int) -> list[dict[str, Any]]:
        """Build events for a session (different content per session index)."""
        base = [
            {"type": "chat", "payload": {"message": f"直隶省税收报告（第{session_index + 1}期）"}},
            {"type": "chat", "payload": {"message": f"灾害情况汇报（第{session_index + 1}期）"}},
            {"type": "chat", "payload": {"message": f"拨款执行情况（第{session_index + 1}期）"}},
        ]
        return base
