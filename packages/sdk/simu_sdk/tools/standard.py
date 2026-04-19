"""Session state manager for task dispatch and message blocking.

The StandardTools class has been replaced by MCPToolAdapter, which
discovers tools dynamically from MCP servers via list_tools().
This module retains only the SessionStateManager used by the agent's
state machine and the MCP adapter hooks.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Maximum nesting depth for task sessions
MAX_TASK_DEPTH = 5


# ---------------------------------------------------------------------------
# Session state manager — tracks pending tasks, replies, and context
# ---------------------------------------------------------------------------


class SessionStateManager:
    """Tracks per-session state for task dispatch and message blocking.

    Manages:
      - pending_tasks: set of unfinished task sub-session IDs per session
      - pending_replies: set of message IDs awaiting reply per session
      - message_queue: events queued while session is blocked
      - session hierarchy: parent/child relationships and nesting depth
      - active session: which session the agent's ReAct loop should target
    """

    def __init__(self) -> None:
        self._pending_tasks: dict[str, set[str]] = {}  # session_id → {task_session_ids}
        self._pending_replies: dict[
            str, dict[str, str]
        ] = {}  # session_id → {msg_id: awaiting_from}
        self._message_queue: dict[str, list[Any]] = {}  # session_id → [events]
        self._parents: dict[str, str] = {}  # task_session_id → parent_session_id
        self._depths: dict[str, int] = {}  # session_id → depth (0 for root)
        self._goals: dict[str, str] = {}  # task_session_id → goal description
        self._active_session: str | None = None
        self._pending_enter: str | None = None  # task session to enter after pipeline

    def is_blocked(self, session_id: str) -> bool:
        """Check if a session is blocked (has pending tasks or replies)."""
        has_tasks = bool(self._pending_tasks.get(session_id))
        has_replies = bool(self._pending_replies.get(session_id))
        return has_tasks or has_replies

    # -- Pending tasks --

    def add_pending_task(self, session_id: str, task_session_id: str) -> None:
        self._pending_tasks.setdefault(session_id, set()).add(task_session_id)

    def remove_pending_task(self, session_id: str, task_session_id: str) -> None:
        tasks = self._pending_tasks.get(session_id)
        if tasks:
            tasks.discard(task_session_id)

    # -- Pending replies --

    def add_pending_reply(
        self,
        session_id: str,
        message_id: str,
        awaiting_from: str = "",
    ) -> None:
        self._pending_replies.setdefault(session_id, {})[message_id] = awaiting_from

    def remove_pending_reply(self, session_id: str, message_id: str) -> None:
        replies = self._pending_replies.get(session_id)
        if replies:
            replies.pop(message_id, None)

    def clear_reply_from(self, session_id: str, sender: str) -> bool:
        """Clear a pending reply matched by sender. Returns True if cleared."""
        replies = self._pending_replies.get(session_id)
        if not replies:
            return False
        for msg_id, awaiting in list(replies.items()):
            if awaiting == sender:
                replies.pop(msg_id)
                return True
        return False

    # -- Message queue --

    def enqueue_message(self, session_id: str, event: Any) -> None:
        self._message_queue.setdefault(session_id, []).append(event)

    def drain_queue(self, session_id: str) -> list[Any]:
        return self._message_queue.pop(session_id, [])

    # -- Session hierarchy --

    def register_task_session(
        self,
        task_session_id: str,
        parent_session_id: str,
        depth: int,
        goal: str = "",
    ) -> None:
        self._parents[task_session_id] = parent_session_id
        self._depths[task_session_id] = depth
        if goal:
            self._goals[task_session_id] = goal

    def get_parent(self, session_id: str) -> str | None:
        return self._parents.get(session_id)

    def get_depth(self, session_id: str) -> int:
        return self._depths.get(session_id, 0)

    def get_goal(self, session_id: str) -> str:
        return self._goals.get(session_id, "")

    # -- Active session --

    def set_active_session(self, session_id: str) -> None:
        self._active_session = session_id

    def get_active_session(self) -> str | None:
        return self._active_session

    # -- Pending task entry (set by create_task_session, consumed by _run_pipeline) --

    def set_pending_enter(self, task_session_id: str) -> None:
        """Signal that a new task session should be entered after pipeline completes."""
        self._pending_enter = task_session_id

    def consume_pending_enter(self) -> str | None:
        """Return and clear the pending task session ID, if any."""
        task_id = getattr(self, "_pending_enter", None)
        self._pending_enter = None
        return task_id
