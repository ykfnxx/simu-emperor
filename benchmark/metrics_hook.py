from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Callable
import statistics


@dataclass
class LLMMetrics:
    call_count: int = 0
    total_latency_ms: float = 0.0
    latencies: list[float] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0


class LLMMetricsCollector:
    def __init__(self):
        self._metrics = LLMMetrics()
        self._original_call: Callable | None = None
        self._is_collecting = False

    def start_collection(self, provider: Any) -> None:
        if self._is_collecting:
            return
        self._original_call = getattr(provider, "call_with_functions", None)
        if self._original_call is None:
            raise AttributeError("Provider does not expose 'call_with_functions'")
        original_method = self._original_call

        async def wrapped_method(*args, **kwargs):
            start = time.perf_counter()
            result = await original_method(*args, **kwargs)  # type: ignore[misc]
            latency_ms = (time.perf_counter() - start) * 1000.0

            self._metrics.call_count += 1
            self._metrics.latencies.append(latency_ms)
            self._metrics.total_latency_ms += latency_ms

            usage = getattr(result, "usage", None)
            if usage is not None:
                in_tokens = getattr(usage, "input_tokens", None)
                out_tokens = getattr(usage, "output_tokens", None)
                if in_tokens is None:
                    in_tokens = getattr(usage, "prompt_tokens", None)
                if out_tokens is None:
                    out_tokens = getattr(usage, "completion_tokens", None)
                if in_tokens is not None:
                    self._metrics.total_input_tokens += int(in_tokens)
                if out_tokens is not None:
                    self._metrics.total_output_tokens += int(out_tokens)

            return result

        provider.call_with_functions = wrapped_method  # type: ignore[assignment]
        self._is_collecting = True

    def stop_collection(self, provider: Any) -> None:
        if not self._is_collecting:
            return
        if self._original_call is not None:
            provider.call_with_functions = self._original_call  # type: ignore[assignment]
        self._original_call = None
        self._is_collecting = False

    def get_metrics(self) -> LLMMetrics:
        return self._metrics

    def reset(self) -> None:
        self._metrics = LLMMetrics()

    def get_latency_percentiles(self) -> dict[str, float]:
        if not self._metrics.latencies:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        lat = sorted(self._metrics.latencies)

        def percentile(p: float) -> float:
            if not lat:
                return 0.0
            idx = int(len(lat) * (p / 100.0))
            if idx >= len(lat):
                idx = len(lat) - 1
            return lat[idx]

        return {
            "p50": statistics.median(lat),
            "p95": percentile(95),
            "p99": percentile(99),
        }
