"""Memory retrieval evaluator for Memory system."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from benchmark.base import BaseEvaluator
from benchmark.config import BenchmarkConfig
from benchmark.models import CaseDetail, MetricResult, ModuleResult


class RetrievalEvaluator(BaseEvaluator):
    """Evaluates Memory system retrieval quality using Recall@K and MRR.

    Injects test events into tape.jsonl (grouped by session), then uses
    SegmentSearcher to search by keyword matching. Scores against known
    relevant event IDs.
    """

    def __init__(self, config: BenchmarkConfig | None = None):
        super().__init__(config)

    async def evaluate(self) -> ModuleResult:
        start = time.perf_counter()

        ctx = await self.get_context(self.config)

        test_data = self._load_test_data()
        inject_events = test_data.get("inject_events", [])
        queries = test_data.get("test_queries", [])

        # Group events by session_id and inject each group into its own tape
        sessions: dict[str, list[dict]] = {}
        for evt in inject_events:
            sid = evt.get("session_id", "default")
            sessions.setdefault(sid, []).append(evt)

        for session_id, session_events in sessions.items():
            await ctx.inject_memory_events(
                session_id=f"bench_retrieval:{session_id}",
                events=session_events,
                agent_id="governor_zhili",
            )

        details: list[CaseDetail] = []
        recall_scores: list[float] = []
        mrr_scores: list[float] = []
        latencies: list[float] = []

        for query in queries:
            q_start = time.perf_counter()
            segments = await ctx.search_tape_segments(query["query"])
            latency = (time.perf_counter() - q_start) * 1000
            latencies.append(latency)

            # Extract event IDs ranked by per-event keyword relevance
            retrieved_ids = self._rank_events_by_relevance(segments, query["query"])

            relevant_ids = set(query.get("relevant_event_ids", []))
            top_k = retrieved_ids[:5]
            top_k_set = set(top_k)

            recall = len(relevant_ids & top_k_set) / len(relevant_ids) if relevant_ids else 0
            recall_scores.append(recall)

            mrr = 0.0
            for i, eid in enumerate(retrieved_ids):
                if eid in relevant_ids:
                    mrr = 1.0 / (i + 1)
                    break
            mrr_scores.append(mrr)

            details.append(
                CaseDetail(
                    case_id=query.get("id", query["query"][:20]),
                    passed=recall > 0,
                    input=query["query"],
                    expected=list(relevant_ids),
                    actual=top_k,
                    reason=f"Recall@5: {recall:.2f}, MRR: {mrr:.2f}",
                )
            )

        avg_recall = sum(recall_scores) / len(recall_scores) * 100 if recall_scores else 0
        avg_mrr = sum(mrr_scores) / len(mrr_scores) if mrr_scores else 0
        sorted_lat = sorted(latencies)
        p95_idx = min(int(len(sorted_lat) * 0.95), len(sorted_lat) - 1)
        p95_latency = sorted_lat[p95_idx] if sorted_lat else 0

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

    def _load_test_data(self) -> dict[str, Any]:
        path = Path(__file__).parent.parent / "data" / "memory_events.json"
        if not path.exists():
            return {"inject_events": [], "test_queries": []}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _rank_events_by_relevance(
        segments: list[dict[str, Any]], query: str
    ) -> list[str]:
        """Rank individual events by keyword overlap with query, across all segments."""
        import re

        # Build query n-grams (2, 3, 4-char) for matching
        clean_q = re.sub(r'[？！。，、：；\s]+', '', query)
        query_ngrams: set[str] = set()
        for n in (2, 3, 4):
            for i in range(max(0, len(clean_q) - n + 1)):
                query_ngrams.add(clean_q[i:i + n])

        scored: list[tuple[str, float]] = []
        seen: set[str] = set()

        for seg in segments:
            seg_score = seg.get("relevance_score", 0.0)
            for evt in seg.get("events", []):
                payload = evt.get("payload", {})
                eid = payload.get("benchmark_event_id", "") or evt.get("event_id", "")
                if not eid or eid in seen:
                    continue
                seen.add(eid)

                content = payload.get("message", "")
                clean_c = re.sub(r'[？！。，、：；\s]+', '', content)

                # Build content n-grams and count overlap with query
                content_ngrams: set[str] = set()
                for n in (2, 3, 4):
                    for i in range(max(0, len(clean_c) - n + 1)):
                        content_ngrams.add(clean_c[i:i + n])

                overlap = len(query_ngrams & content_ngrams)
                event_score = seg_score + overlap * 0.15

                scored.append((eid, event_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [eid for eid, _ in scored]
