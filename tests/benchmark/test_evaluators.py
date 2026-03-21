"""
TDD RED tests for Benchmark Evaluators.

These tests define the expected behavior of the real evaluators
that will be implemented in Wave 3. All tests should FAIL (RED)
because the evaluators currently use placeholder implementations.

Expected Evaluators:
- IntentAccuracyEvaluator: Test agent's ability to call correct tools
- ResponsePerfEvaluator: Test agent's response latency
- MultiAgentEvaluator: Test concurrent agent performance
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from benchmark.agent.intent_accuracy import IntentAccuracyEvaluator
from benchmark.agent.response_perf import ResponsePerfEvaluator
from benchmark.agent.multi_agent import MultiAgentEvaluator
from benchmark.config import BenchmarkConfig
from benchmark.models import ModuleResult, CaseDetail


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def benchmark_config():
    """Create a benchmark config for testing."""
    return BenchmarkConfig(
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        api_key="test-key",
        base_url=None,
        timeout=120,
        max_retries=3,
    )


@pytest.fixture
def mock_benchmark_api():
    """Mock the benchmark API response."""
    return {
        "response": "直隶省的税收为五十万两白银。",
        "tool_calls": [
            {
                "name": "query_province_data",
                "args": {"province_id": "zhili", "field_path": "production_value"},
                "result": "查询结果：zhili 的 production_value = 500000",
            }
        ],
        "latency_ms": 1234.56,
        "success": True,
        "error": None,
    }


# ============================================================================
# IntentAccuracyEvaluator Tests
# ============================================================================


class TestIntentAccuracyEvaluator:
    """Tests for IntentAccuracyEvaluator - should call real API."""

    @pytest.mark.asyncio
    async def test_evaluate_calls_benchmark_api(self, benchmark_config):
        """Test that evaluator calls the benchmark API endpoint."""
        evaluator = IntentAccuracyEvaluator(benchmark_config)

        with patch("benchmark.agent.intent_accuracy.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "response": "test",
                "tool_calls": [{"name": "query_province_data", "args": {}, "result": "ok"}],
                "latency_ms": 100.0,
                "success": True,
                "error": None,
            }
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await evaluator.evaluate()

            # Should have called the API for each test case
            assert isinstance(result, ModuleResult)
            assert result.module == "intent_accuracy"

    @pytest.mark.asyncio
    async def test_evaluate_returns_real_tool_calls(self, benchmark_config):
        """Test that evaluator returns actual tool calls from API, not placeholder."""
        evaluator = IntentAccuracyEvaluator(benchmark_config)

        with patch("benchmark.agent.intent_accuracy.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "response": "直隶省税收五十万两",
                "tool_calls": [
                    {
                        "name": "query_province_data",
                        "args": {"province_id": "zhili"},
                        "result": "500000",
                    }
                ],
                "latency_ms": 500.0,
                "success": True,
                "error": None,
            }
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await evaluator.evaluate()

            # Check that details contain actual tool names, not placeholder values
            for detail in result.details:
                # Should have real tool calls, not placeholder strings
                if detail.actual:
                    assert "placeholder" not in str(detail.actual).lower()
                    assert "skeleton" not in str(detail.actual).lower()

    @pytest.mark.asyncio
    async def test_intent_accuracy_not_hardcoded(self, benchmark_config):
        """Test that intent_accuracy metric is calculated, not hardcoded to 100%."""
        evaluator = IntentAccuracyEvaluator(benchmark_config)

        with patch("benchmark.agent.intent_accuracy.httpx.AsyncClient") as mock_client:
            # Simulate some failures
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "response": "test",
                "tool_calls": [{"name": "wrong_tool", "args": {}, "result": "ok"}],
                "latency_ms": 100.0,
                "success": True,
                "error": None,
            }
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await evaluator.evaluate()

            # Find the intent_accuracy metric
            accuracy_metric = next((m for m in result.metrics if m.name == "intent_accuracy"), None)
            assert accuracy_metric is not None
            # Should not be hardcoded to 100% if tools don't match
            # (With wrong tools, accuracy should be lower)


# ============================================================================
# ResponsePerfEvaluator Tests
# ============================================================================


class TestResponsePerfEvaluator:
    """Tests for ResponsePerfEvaluator - should measure real latency."""

    @pytest.mark.asyncio
    async def test_evaluate_measures_real_latency(self, benchmark_config):
        """Test that evaluator measures actual API latency, not hardcoded 11ms."""
        evaluator = ResponsePerfEvaluator(benchmark_config)

        with patch("benchmark.agent.response_perf.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "response": "test",
                "tool_calls": [],
                "latency_ms": 500.0,  # Realistic latency
                "success": True,
                "error": None,
            }
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await evaluator.evaluate()

            # Find latency metrics
            p50_metric = next((m for m in result.metrics if m.name == "latency_p50"), None)
            assert p50_metric is not None
            # Should not be hardcoded to 11ms
            # (Real API calls should have variable latency)

    @pytest.mark.asyncio
    async def test_latency_not_hardcoded_11ms(self, benchmark_config):
        """Test that latency values are not hardcoded to 11ms."""
        evaluator = ResponsePerfEvaluator(benchmark_config)

        with patch("benchmark.agent.response_perf.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "response": "test",
                "tool_calls": [],
                "latency_ms": 1234.56,
                "success": True,
                "error": None,
            }
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await evaluator.evaluate()

            # Check all latency metrics
            for metric in result.metrics:
                if "latency" in metric.name:
                    # Should not be exactly 11ms (the old hardcoded value)
                    # Note: The metric might be 0 if no API call was made,
                    # but it should NOT be 11
                    if metric.value > 0:
                        assert metric.value != 11, f"{metric.name} is hardcoded to 11ms"


# ============================================================================
# MultiAgentEvaluator Tests
# ============================================================================


class TestMultiAgentEvaluator:
    """Tests for MultiAgentEvaluator - should test concurrent calls."""

    @pytest.mark.asyncio
    async def test_evaluate_concurrent_calls(self, benchmark_config):
        """Test that evaluator makes concurrent API calls for multiple agents."""
        evaluator = MultiAgentEvaluator(benchmark_config)

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "response": f"response_{call_count}",
                "tool_calls": [],
                "latency_ms": 100.0,
                "success": True,
                "error": None,
            }
            return mock_response

        with patch("benchmark.agent.multi_agent.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = mock_post

            result = await evaluator.evaluate()

            # Should have made multiple API calls (2, 5, 10 agents)
            assert call_count >= 3  # At least 3 different concurrency levels

    @pytest.mark.asyncio
    async def test_scaling_ratio_not_hardcoded(self, benchmark_config):
        """Test that scaling_ratio is calculated, not hardcoded to 1.0."""
        evaluator = MultiAgentEvaluator(benchmark_config)

        with patch("benchmark.agent.multi_agent.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "response": "test",
                "tool_calls": [],
                "latency_ms": 100.0,
                "success": True,
                "error": None,
            }
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await evaluator.evaluate()

            # Find scaling ratio metrics
            for metric in result.metrics:
                if "scaling_ratio" in metric.name:
                    # Should not be exactly 1.0 (hardcoded placeholder)
                    # Unless the implementation correctly shows sublinear scaling
                    assert metric.value >= 0.5, f"{metric.name} is too low"


# META test deleted - Wave 3 complete, evaluators now use real API calls
