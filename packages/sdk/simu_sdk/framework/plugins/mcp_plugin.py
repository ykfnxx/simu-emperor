"""MCPClientPlugin — handles outbound actions after the pipeline."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TYPE_CHECKING

from simu_sdk.framework.hooks import hookimpl

if TYPE_CHECKING:
    from simu_sdk.client import ServerClient
    from simu_sdk.tape.context import ContextManager
    from simu_sdk.tools.standard import SessionStateManager

logger = logging.getLogger(__name__)


class MCPClientPlugin:
    """Handles outbound dispatch — routing responses, posting messages,
    completing invocations, and updating session summaries.

    In V6 Phase 1 this still uses the ServerClient HTTP callbacks.
    In Phase 2+ this will be replaced with MCP client calls.
    """

    def __init__(
        self,
        server: ServerClient,
        agent_id: str,
        session_state: SessionStateManager,
        context_manager: ContextManager,
    ) -> None:
        self._server = server
        self._agent_id = agent_id
        self._session_state = session_state
        self._context_manager = context_manager

    @hookimpl
    async def dispatch_outbound(
        self, envelope: Any, session_id: str, state: Any, result: Any,
    ) -> None:
        """Route response to server, post to player, complete invocation."""
        event = envelope.payload
        response_event = state.response_event
        if response_event is None:
            return

        # Route RESPONSE to destination agents for agent-to-agent replies.
        # Only when the ReAct loop ended naturally (text output).
        should_route = (
            state.ended_by_tool is None
            and event.src.startswith("agent:")
            and event.src != f"agent:{self._agent_id}"
        )
        await self._server.push_tape_event(response_event, route=should_route)

        # Update session summary in background
        asyncio.create_task(self._update_summary(session_id))

        # Send response to player (non-task sessions, natural endings only)
        if (
            state.response_content
            and not session_id.startswith("task:")
            and state.ended_by_tool is None
        ):
            await self._server.post_message(
                recipients=["player"],
                message=state.response_content,
                session_id=session_id,
            )

        # Complete invocation
        invocation_id = getattr(event, "invocation_id", None)
        if invocation_id:
            await self._server.complete_invocation(invocation_id)

    async def _update_summary(self, session_id: str) -> None:
        try:
            await self._context_manager.update_session_summary(session_id, [])
        except Exception:
            logger.warning("Failed to update session summary for %s", session_id, exc_info=True)
