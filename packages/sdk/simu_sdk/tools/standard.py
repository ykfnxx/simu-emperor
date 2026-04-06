"""Standard tools built into the SDK — communication and task management.

Tools:
  1. send_message — send a message to other agents or the player
  2. query_state — query game state from the Server
  3. create_task_session — create a task sub-session for focused work
  4. finish_task_session — complete the current task session with a result
  5. fail_task_session — mark the current task session as failed
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from simu_sdk.tools.registry import tool

if TYPE_CHECKING:
    from simu_shared.models import TapeEvent

    from simu_sdk.client import ServerClient

logger = logging.getLogger(__name__)

# Maximum nesting depth for task sessions
MAX_TASK_DEPTH = 5


class StandardTools:
    """Communication and task management tool set.

    Requires a ``ServerClient`` instance and a reference to the agent's
    session state manager for task session support.
    """

    def __init__(
        self,
        server: ServerClient,
        session_state: SessionStateManager | None = None,
    ) -> None:
        self._server = server
        self._session_state = session_state

    @tool(
        name="send_message",
        description=(
            "Send a message to other agents or the player. "
            "Set await_reply=true when you need a response before continuing, "
            "e.g. asking a question, issuing a command that requires confirmation, "
            "or requesting information from another agent."
        ),
        parameters={
            "recipients": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Target agent IDs or 'player'.",
            },
            "message": {
                "type": "string",
                "description": "Message content.",
            },
            "await_reply": {
                "type": "boolean",
                "description": (
                    "If true, the current session will wait for a reply before "
                    "processing new messages. Use for questions, commands, or "
                    "any scenario requiring a response."
                ),
                "default": False,
            },
        },
        category="communication",
    )
    async def send_message(self, args: dict, event: TapeEvent) -> str:
        event_id = await self._server.post_message(
            recipients=args["recipients"],
            message=args["message"],
            session_id=event.session_id,
        )
        if args.get("await_reply") and self._session_state:
            self._session_state.add_pending_reply(event.session_id, event_id)
        return "Message sent."

    @tool(
        name="query_state",
        description="Query game state from the Server.",
        parameters={
            "path": {
                "type": "string",
                "description": "State path, e.g. 'imperial_treasury', 'provinces.zhili'.",
            },
        },
        category="communication",
    )
    async def query_state(self, args: dict, event: TapeEvent) -> str:
        import json

        result = await self._server.query_state(path=args.get("path", ""))
        return json.dumps(result, ensure_ascii=False, default=str)

    @tool(
        name="create_task_session",
        description=(
            "Create a task sub-session for focused work on a specific goal. "
            "The task is assigned to yourself. After creation, your context "
            "switches to the new task session. Use finish_task_session or "
            "fail_task_session when done. Task sessions can be nested up to "
            "5 levels deep."
        ),
        parameters={
            "goal": {
                "type": "string",
                "description": "What the task should accomplish — the acceptance criteria.",
            },
            "description": {
                "type": "string",
                "description": "Detailed description of the task.",
            },
            "constraints": {
                "type": "string",
                "description": "Constraints or requirements for task execution.",
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Maximum time in seconds for this task (default: 300).",
                "default": 300,
            },
        },
        category="session",
    )
    async def create_task_session(self, args: dict, event: TapeEvent) -> str:
        if self._session_state is None:
            return "Error: session state manager not available."

        current_depth = self._session_state.get_depth(event.session_id)
        if current_depth >= MAX_TASK_DEPTH:
            return f"Error: maximum task nesting depth ({MAX_TASK_DEPTH}) reached."

        task_session_id = await self._server.create_task_session(
            parent_session_id=event.session_id,
            goal=args["goal"],
            description=args.get("description", ""),
            constraints=args.get("constraints", ""),
            timeout_seconds=args.get("timeout_seconds", 300),
            depth=current_depth + 1,
        )

        # Register the new task session in state manager
        self._session_state.register_task_session(
            task_session_id=task_session_id,
            parent_session_id=event.session_id,
            depth=current_depth + 1,
        )

        # Mark parent as waiting for this task
        self._session_state.add_pending_task(event.session_id, task_session_id)

        # Switch context to the new task session
        self._session_state.set_active_session(task_session_id)

        logger.info(
            "Created task session %s (parent=%s, depth=%d, goal=%s)",
            task_session_id, event.session_id, current_depth + 1, args["goal"],
        )
        return f"Task session created: {task_session_id}. Context switched to task session."

    @tool(
        name="finish_task_session",
        description=(
            "Complete the current task session with a result. The result will "
            "be sent to the parent session. Context switches back to the parent."
        ),
        parameters={
            "result": {
                "type": "string",
                "description": "The outcome/result of the completed task.",
            },
        },
        category="session",
    )
    async def finish_task_session(self, args: dict, event: TapeEvent) -> str:
        if self._session_state is None:
            return "Error: session state manager not available."

        parent_id = self._session_state.get_parent(event.session_id)
        if parent_id is None:
            return "Error: not in a task session, or parent session unknown."

        await self._server.finish_task_session(
            task_session_id=event.session_id,
            parent_session_id=parent_id,
            result=args["result"],
            status="completed",
        )

        # Remove from parent's pending tasks
        self._session_state.remove_pending_task(parent_id, event.session_id)

        # Switch context back to parent
        self._session_state.set_active_session(parent_id)

        logger.info("Finished task session %s, returning to %s", event.session_id, parent_id)
        return f"Task completed. Context switched back to parent session {parent_id}."

    @tool(
        name="fail_task_session",
        description=(
            "Mark the current task session as failed. The reason will be "
            "sent to the parent session. Context switches back to the parent."
        ),
        parameters={
            "reason": {
                "type": "string",
                "description": "Why the task failed.",
            },
        },
        category="session",
    )
    async def fail_task_session(self, args: dict, event: TapeEvent) -> str:
        if self._session_state is None:
            return "Error: session state manager not available."

        parent_id = self._session_state.get_parent(event.session_id)
        if parent_id is None:
            return "Error: not in a task session, or parent session unknown."

        await self._server.finish_task_session(
            task_session_id=event.session_id,
            parent_session_id=parent_id,
            result=args["reason"],
            status="failed",
        )

        # Remove from parent's pending tasks
        self._session_state.remove_pending_task(parent_id, event.session_id)

        # Switch context back to parent
        self._session_state.set_active_session(parent_id)

        logger.info("Failed task session %s, returning to %s", event.session_id, parent_id)
        return f"Task failed. Context switched back to parent session {parent_id}."


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
        self._pending_replies: dict[str, set[str]] = {}  # session_id → {message_ids}
        self._message_queue: dict[str, list[Any]] = {}  # session_id → [events]
        self._parents: dict[str, str] = {}  # task_session_id → parent_session_id
        self._depths: dict[str, int] = {}  # session_id → depth (0 for root)
        self._active_session: str | None = None

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

    def add_pending_reply(self, session_id: str, message_id: str) -> None:
        self._pending_replies.setdefault(session_id, set()).add(message_id)

    def remove_pending_reply(self, session_id: str, message_id: str) -> None:
        replies = self._pending_replies.get(session_id)
        if replies:
            replies.discard(message_id)

    # -- Message queue --

    def enqueue_message(self, session_id: str, event: Any) -> None:
        self._message_queue.setdefault(session_id, []).append(event)

    def drain_queue(self, session_id: str) -> list[Any]:
        return self._message_queue.pop(session_id, [])

    # -- Session hierarchy --

    def register_task_session(
        self, task_session_id: str, parent_session_id: str, depth: int,
    ) -> None:
        self._parents[task_session_id] = parent_session_id
        self._depths[task_session_id] = depth

    def get_parent(self, session_id: str) -> str | None:
        return self._parents.get(session_id)

    def get_depth(self, session_id: str) -> int:
        return self._depths.get(session_id, 0)

    # -- Active session --

    def set_active_session(self, session_id: str) -> None:
        self._active_session = session_id

    def get_active_session(self) -> str | None:
        return self._active_session
