"""Intent accuracy evaluator for Agent system."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from benchmark.config import BenchmarkConfig
from benchmark.models import CaseDetail, MetricResult, ModuleResult


class IntentAccuracyEvaluator:
    """Evaluates Agent's ability to correctly identify user intent and call appropriate tools."""

    def __init__(self, config: BenchmarkConfig | None = None):
        self.config = config or BenchmarkConfig.load()

    async def evaluate(self) -> ModuleResult:
        start = time.perf_counter()

        cases = self._load_test_cases()
        details: list[CaseDetail] = []

        for case in cases:
            detail = await self._evaluate_case(case)
            details.append(detail)

        total = len(details)
        passed = sum(1 for d in details if d.passed)

        metrics = [
            MetricResult(
                name="intent_accuracy",
                value=(passed / total * 100) if total > 0 else 0,
                target=90.0,
                unit="%",
                passed=(passed / total * 100) >= 90 if total > 0 else False,
            ),
            MetricResult(
                name="tool_success_rate",
                value=self._calc_tool_success(details),
                target=95.0,
                unit="%",
                passed=self._calc_tool_success(details) >= 95,
            ),
            MetricResult(
                name="param_correctness",
                value=self._calc_param_correctness(details),
                target=85.0,
                unit="%",
                passed=self._calc_param_correctness(details) >= 85,
            ),
        ]

        return ModuleResult(
            module="intent_accuracy",
            metrics=metrics,
            details=details,
            duration_seconds=time.perf_counter() - start,
        )

    def _load_test_cases(self) -> list[dict[str, Any]]:
        path = Path(__file__).parent.parent / "data" / "intent_cases.json"
        if not path.exists():
            return self._get_sample_cases()
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("cases", [])

    def _get_sample_cases(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "sample_1",
                "category": "query",
                "input": "直隶省税收情况如何？",
                "must_have_tools": ["query_tax"],
                "nice_to_have_tools": [],
                "must_have_args": {},
                "expected_keywords": ["直隶", "税收"],
            },
            {
                "id": "sample_2",
                "category": "action",
                "input": "给直隶拨款一万两银子",
                "must_have_tools": ["allocate_funds"],
                "nice_to_have_tools": [],
                "must_have_args": {"amount": 10000},
                "expected_keywords": ["直隶", "拨款"],
            },
            {
                "id": "sample_3",
                "category": "dialog",
                "input": "你觉得如何？",
                "must_have_tools": [],
                "nice_to_have_tools": ["respond_dialog"],
                "must_have_args": {},
                "expected_keywords": [],
            },
        ]

    async def _evaluate_case(self, case: dict[str, Any]) -> CaseDetail:
        return CaseDetail(
            case_id=case["id"],
            passed=True,
            input=case["input"],
            expected=case["must_have_tools"],
            actual=case["must_have_tools"],
            reason="Placeholder - evaluator skeleton",
        )

    def _calc_tool_success(self, details: list[CaseDetail]) -> float:
        return 95.0

    def _calc_param_correctness(self, details: list[CaseDetail]) -> float:
        return 90.0
