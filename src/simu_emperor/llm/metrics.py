"""Prometheus metrics for LLM monitoring (V4.3)"""

from prometheus_client import Counter, Histogram, Gauge

# LLM 请求总数
llm_requests_total = Counter(
    "llm_requests_total",
    "Total LLM requests",
    ["provider", "model", "task_type", "status"],
)

# LLM 请求延迟
llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "LLM request duration in seconds",
    ["provider", "model", "task_type"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

# Token 使用量
llm_tokens_used_total = Counter(
    "llm_tokens_used_total",
    "Total tokens used",
    ["provider", "model", "task_type", "token_type"],
)

# 活跃请求数
llm_active_requests = Gauge(
    "llm_active_requests",
    "Number of active LLM requests",
    ["provider", "model"],
)
