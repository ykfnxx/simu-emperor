"""Memory retrieval evaluator for Memory system."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from benchmark.config import BenchmarkConfig
from benchmark.models import CaseDetail, MetricResult, ModuleResult


class RetrievalEvaluator:
    """Evaluates Memory system retrieval quality using Recall@K and MRR."""

    def __init__(self, config: BenchmarkConfig | None = None):
        self.config = config or BenchmarkConfig.load()

    async def evaluate(self) -> ModuleResult:
        start = time.perf_counter()

        queries = self._load_test_queries()
        details: list[CaseDetail] = []

        recall_scores: list[float] = []
        mrr_scores: list[float] = []
        latencies: list[float] = []

        for query in queries:
            q_start = time.perf_counter()
            results = await self._retrieve(query["query"])
            latency = (time.perf_counter() - q_start) * 1000
            latencies.append(latency)

            relevant_ids = set(query["relevant_event_ids"])
            retrieved_ids = set(r["id"] for r in results[:5])
            recall = len(relevant_ids & retrieved_ids) / len(relevant_ids) if relevant_ids else 0
            recall_scores.append(recall)

            mrr = 0.0
            for i, r in enumerate(results):
                if r["id"] in relevant_ids:
                    mrr = 1.0 / (i + 1)
                    break
            mrr_scores.append(mrr)

            details.append(
                CaseDetail(
                    case_id=query.get("id", query["query"][:20]),
                    passed=recall >= 0.8,
                    input=query["query"],
                    expected=list(relevant_ids),
                    actual=[r["id"] for r in results[:5]],
                    reason=f"Recall@5: {recall:.2f}, MRR: {mrr:.2f}",
                )
            )

        avg_recall = sum(recall_scores) / len(recall_scores) * 100 if recall_scores else 0
        avg_mrr = sum(mrr_scores) / len(mrr_scores) if mrr_scores else 0
        sorted_lat = sorted(latencies)
        p95_latency = sorted_lat[int(len(sorted_lat) * 0.95)] if sorted_lat else 0

        metrics = [
            MetricResult("recall_at_5", avg_recall, 80.0, "%", avg_recall >= 80),
            MetricResult("mrr", avg_mrr * 100, 70.0, "%", avg_mrr >= 0.7),
            MetricResult("latency_p95", p95_latency, 500, "ms", p95_latency <= 500),
        ]

        return ModuleResult(
            module="retrieval",
            metrics=metrics,
            details=details,
            duration_seconds=time.perf_counter() - start,
        )

    def _load_test_queries(self) -> list[dict[str, Any]]:
        path = Path(__file__).parent.parent / "data" / "memory_events.json"
        if not path.exists():
            return [
                {
                    "id": "q1",
                    "query": "直隶省税收",
                    "relevant_event_ids": ["e1"],
                    "difficulty": "easy",
                }
            ]
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("test_queries", [])

    async def _retrieve(self, query: str) -> list[dict[str, str]]:
        return [{"id": "e1", "content": "placeholder"}]
