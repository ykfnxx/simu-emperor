"""Data models for the framework pipeline.

Plugins pass state through ``SimuTurnState`` — a typed dataclass instead
of a raw dict, providing IDE completion and type safety.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SimuTurnState:
    """Accumulated state passed between pipeline hooks.

    Each plugin contributes fields during ``load_state`` and reads them
    during ``build_prompt`` / ``run_model`` / ``save_state``.
    """

    session_id: str = ""

    # SimuTapePlugin: tape events for the current session
    tape_events: list[Any] = field(default_factory=list)

    # SimuContextPlugin: context window (summary + recent events)
    context_summary: str = ""
    context_events: list[Any] = field(default_factory=list)

    # SimuContextPlugin: system prompt
    system_prompt: str = ""

    # SimuReActPlugin: available tool definitions
    available_tools: list[dict] = field(default_factory=list)

    # SimuMemoryPlugin: retrieved memories
    relevant_memories: list[Any] = field(default_factory=list)

    # Filled by run_model
    response_content: str = ""
    response_event: Any = None
    ended_by_tool: str | None = None

    # Session transition flags (set by tools during run_model)
    new_task_session_id: str | None = None
    drain_queue_after: bool = False
