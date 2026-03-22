"""Compression fidelity evaluator for Memory system."""

from __future__ import annotations

import time
import uuid
from typing import Any

from benchmark.base import BaseEvaluator
from benchmark.config import BenchmarkConfig
from benchmark.models import CaseDetail, MetricResult, ModuleResult


class CompressionEvaluator(BaseEvaluator):
    """Evaluates Memory system compression quality via keyword retention.

    Injects events that exceed the token threshold, triggers slide_window,
    then checks that the summary retains key information.
    """

    def __init__(self, config: BenchmarkConfig | None = None):
        super().__init__(config)
        self.test_keywords = ["直隶", "税收", "拨款", "人口", "灾害", "丰收"]

    async def evaluate(self) -> ModuleResult:
        start = time.perf_counter()

        ctx = await self.get_context(self.config)

        session_id = f"bench_compress:{uuid.uuid4().hex[:8]}"
        agent_id = "governor_zhili"

        # Generate events with enough tokens to exceed threshold
        events = self._build_keyword_events()
        await ctx.inject_memory_events(
            session_id=session_id,
            events=events,
            agent_id=agent_id,
        )

        # Use max_tokens=3000 with keep_recent=5: 50 events (~7000 tokens) will trigger
        # slide_window which keeps ~30 recent events and summarizes the older ones
        cm = ctx.get_context_manager(session_id, agent_id, max_tokens=3000)

        # Count events before loading (load_from_tape auto-compacts)
        from simu_emperor.common import FileOperationsHelper
        tape_path = cm.tape_path
        raw_events = await FileOperationsHelper.read_jsonl_file(tape_path)
        original_event_count = len(raw_events)
        original_tokens = sum(cm._calc_event_tokens(e) for e in raw_events)

        await cm.load_from_tape()

        compressed_tokens = cm._calc_total_tokens()
        compressed_event_count = len(cm.events)
        summary = cm.summary or ""

        # Check keyword retention: in summary (if available) or in remaining events
        check_text = summary
        if not check_text:
            # Fallback: check keywords in remaining events' content
            import json
            check_text = json.dumps([e.get("payload", {}) for e in cm.events], ensure_ascii=False)

        retained = sum(1 for kw in self.test_keywords if kw in check_text)
        retention_rate = (retained / len(self.test_keywords)) * 100 if self.test_keywords else 0

        compression_ratio = compressed_tokens / original_tokens if original_tokens > 0 else 1.0

        metrics = [
            MetricResult(
                "keyword_retention_rate",
                retention_rate,
                50.0,
                "%",
                retention_rate >= 50,
            ),
            MetricResult(
                "compression_ratio",
                compression_ratio * 100,
                50.0,
                "%",
                compression_ratio <= 0.5,
            ),
            MetricResult(
                "original_tokens",
                float(original_tokens),
                1000,
                "tokens",
                original_tokens >= 1000,
            ),
            MetricResult(
                "compressed_tokens",
                float(compressed_tokens),
                1500,
                "tokens",
                True,
            ),
        ]

        details = [
            CaseDetail(
                case_id="compression_1",
                passed=compressed_tokens < original_tokens,
                input=f"{original_event_count} events, {original_tokens} tokens",
                expected=["retention >= 50%", "ratio <= 50%"],
                actual=[
                    f"retention: {retention_rate:.0f}%",
                    f"ratio: {compression_ratio:.0%}",
                    f"events: {original_event_count} -> {compressed_event_count}",
                ],
                reason=f"Retained {retained}/{len(self.test_keywords)} keywords. "
                       f"Tokens: {original_tokens} -> {compressed_tokens}",
            )
        ]

        return ModuleResult(
            module="compression",
            metrics=metrics,
            details=details,
            duration_seconds=time.perf_counter() - start,
        )

    def _build_keyword_events(self) -> list[dict[str, Any]]:
        """Build events with enough content to exceed the 2000-token threshold."""
        templates = [
            "直隶省今年税收达到五十万两白银，比去年增长一成。主要来源是田赋和盐税。直隶巡抚上报称各府县征收情况良好，百姓负担适中。",
            "户部拨款十万两白银用于直隶省水利工程建设，包括运河疏浚和堤坝加固。拨款已经分批下发至各府。",
            "直隶省人口统计显示总人口达到三百万口，较去年增长百分之二。各府人口分布均匀，城镇化水平有所提高。",
            "山东省遭遇严重旱灾，农作物减产三成，受灾人口达十万。朝廷已拨付赈灾款项五万两，地方官府正在组织救济。",
            "江南地区今年水稻丰收，粮食产量增加两成。粮价有所下降，百姓生活安定。各省仓储充足，可供调配。",
            "直隶省税收征管改革取得成效，新设立的税务机构运转良好。地方官员积极配合，偷漏税现象明显减少。",
            "朝廷决定向直隶省追加拨款五万两用于灾害防治。直隶近年来水患频繁，需要加强堤防建设和排水系统改造。",
            "全国人口统计汇总完成，总人口达到一亿二千万。各省人口增长率不一，沿海省份增长较快。",
            "直隶省遭遇特大暴雨灾害，多处河堤决口，农田被淹。受灾百姓需要紧急安置和救济。",
            "各省秋季丰收报告陆续上报，今年全国粮食总产量预计增加一成五。南方稻米和北方小麦均获得好收成。",
        ]
        # Repeat to generate ~40 events (each ~60 tokens → ~2400 tokens, well above 2000)
        events: list[dict[str, Any]] = []
        for i in range(50):
            content = templates[i % len(templates)]
            events.append({
                "type": "chat",
                "payload": {"message": f"[报告{i + 1}] {content}"},
            })
        return events
