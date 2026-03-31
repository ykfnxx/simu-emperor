"""Shared utilities for the agents module."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def write_llm_log(
    log_path: Path,
    *,
    event_id: str,
    session_id: str,
    iteration: int,
    model: str,
    request: dict,
    response: dict,
    duration_ms: float,
) -> None:
    """Append an LLM call record to a JSONL log file."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_id": event_id,
        "session_id": session_id,
        "iteration": iteration,
        "model": model,
        "duration_ms": duration_ms,
        "request": request,
        "response": response,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
