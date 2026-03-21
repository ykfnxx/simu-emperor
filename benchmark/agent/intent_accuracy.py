"""Intent accuracy evaluator for Agent system."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from benchmark.config import BenchmarkConfig
from benchmark.models import CaseDetail, MetricResult, ModuleResult


class IntentAccuracyEvaluator:
    """Evaluates Agent's ability to correctly identify user intent and call appropriate tools."""

    def __init__(self, config: BenchmarkConfig | None = None):
        self.config = config or BenchmarkConfig.load()
        self.api_base_url = os.getenv("BENCHMARK_API_URL", "http://localhost:8000")

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

    async def _call_api(self, message: str) -> dict[str, Any]:
        """Call the benchmark API endpoint and return the response data."""
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(
                f"{self.api_base_url}/api/benchmark/agent/chat",
                json={
                    "agent_id": "governor_zhili",
                    "message": message,
                },
            )
            response.raise_for_status()
            return response.json()

    async def _evaluate_case(self, case: dict[str, Any]) -> CaseDetail:
        """Evaluate a single test case by calling the API and checking tool calls."""
        try:
            api_response = await self._call_api(case["input"])

            actual_tool_calls = api_response.get("tool_calls", [])
            actual_tools = [tc.get("name", "") for tc in actual_tool_calls if tc.get("name")]

            must_have = set(case.get("must_have_tools", []))

            actual_set = set(actual_tools)
            must_have_matched = must_have.issubset(actual_set) if must_have else True
            passed = must_have_matched

            if passed:
                reason = f"All required tools called: {actual_tools}"
            else:
                missing = must_have - actual_set
                reason = f"Missing required tools: {missing}. Got: {actual_tools}"

            must_have_args = case.get("must_have_args", {})
            self._check_args_correctness(actual_tool_calls, must_have_args)

            return CaseDetail(
                case_id=case["id"],
                passed=passed,
                input=case["input"],
                expected=list(must_have),
                actual=actual_tools,
                reason=reason,
            )

        except Exception as e:
            return CaseDetail(
                case_id=case["id"],
                passed=False,
                input=case["input"],
                expected=case.get("must_have_tools", []),
                actual=[],
                reason=f"API call failed: {str(e)}",
            )

    def _check_args_correctness(
        self, tool_calls: list[dict[str, Any]], expected_args: dict[str, Any]
    ) -> bool:
        """Check if the expected arguments are present in the tool calls."""
        if not expected_args:
            return True

        for tool_call in tool_calls:
            args = tool_call.get("args", {})
            for key, expected_value in expected_args.items():
                if key in args:
                    actual_value = args[key]
                    if isinstance(expected_value, (int, float)) and isinstance(
                        actual_value, (int, float)
                    ):
                        if abs(actual_value - expected_value) < 0.01 * abs(expected_value):
                            return True
                    elif actual_value == expected_value:
                        return True
        return False

    def _calc_tool_success(self, details: list[CaseDetail]) -> float:
        """Calculate the percentage of cases where tool calls were successful."""
        if not details:
            return 0.0

        successful = sum(1 for d in details if d.passed)
        return (successful / len(details)) * 100

    def _calc_param_correctness(self, details: list[CaseDetail]) -> float:
        """Calculate parameter correctness based on matched cases."""
        if not details:
            return 0.0

        correct = sum(1 for d in details if d.passed)
        return (correct / len(details)) * 100
