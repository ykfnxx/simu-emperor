"""MCPClientPlugin — handles outbound actions after the pipeline."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TYPE_CHECKING

from bub.hookspecs import hookimpl

if TYPE_CHECKING:
    from simu_sdk.mcp_client import MCPServerClient
    from simu_sdk.tape.context import ContextManager
    from simu_sdk.tools.standard import SessionStateManager

logger = logging.getLogger(__name__)


class MCPClientPlugin:
    """Handles outbound dispatch — routing responses, posting messages,
    completing invocations, and updating session summaries.

    Uses MCPServerClient for all server communication via MCP protocol.
    """

    def __init__(
        self,
        mcp: MCPServerClient,
        agent_id: str,
        session_state: SessionStateManager,
        context_manager: ContextManager,
    ) -> None:
        self._mcp = mcp
        self._agent_id = agent_id
        self._session_state = session_state
        self._context_manager = context_manager
        self._background_tasks: set[asyncio.Task] = set()

    @hookimpl
    async def save_state(
        self, session_id: str, state: dict, message: Any, model_output: str,
    ) -> None:
        """Push response to server and update session summary."""
        response_event = state.get("response_event")
        if response_event is None:
            return

        event = state.get("_inbound_event", message)
        ended_by_tool = state.get("ended_by_tool")

        # Route RESPONSE to destination agents for agent-to-agent replies.
        # Only when the ReAct loop ended naturally (text output).
        should_route = (
            ended_by_tool is None
            and event.src.startswith("agent:")
            and event.src != f"agent:{self._agent_id}"
        )
        await self._mcp.push_tape_event(response_event, route=should_route)

        # Update session summary in background (prevent GC from swallowing exceptions)
        task = asyncio.create_task(self._update_summary(session_id))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        # Send response to player (non-task sessions, natural endings only)
        if (
            model_output
            and not session_id.startswith("task:")
            and ended_by_tool is None
        ):
            await self._mcp.post_message(
                recipients=["player"],
                message=model_output,
                session_id=session_id,
            )

        # Complete invocation
        invocation_id = getattr(event, "invocation_id", None)
        if invocation_id:
            await self._mcp.complete_invocation(invocation_id)

    async def _update_summary(self, session_id: str) -> None:
        try:
            await self._context_manager.update_session_summary(session_id, [])
        except Exception:
            logger.warning("Failed to update session summary for %s", session_id, exc_info=True)
