"""SimuReActPlugin — executes the ReAct loop within the Bub pipeline."""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from simu_shared.constants import EventType
from simu_shared.models import TapeEvent
from bub.hookspecs import hookimpl
from simu_sdk.react import ReActLoop
from simu_sdk.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from simu_sdk.llm.base import LLMProvider
    from simu_sdk.mcp_client import MCPServerClient
    from simu_sdk.tape.manager import TapeManager

logger = logging.getLogger(__name__)


class SimuReActPlugin:
    """Runs the ReAct (Reason-Act-Observe) loop as the ``run_model`` hook.

    Wraps the existing ReActLoop, feeding it the context and prompt
    assembled by earlier plugins, and stores the result in state.
    """

    def __init__(
        self,
        llm: LLMProvider,
        tools: ToolRegistry,
        tape: TapeManager,
        mcp: MCPServerClient,
        agent_id: str,
        max_iterations: int = 10,
        max_tool_calls: int = 20,
    ) -> None:
        self._react_loop = ReActLoop(llm, tools, max_iterations, max_tool_calls)
        self._tape = tape
        self._mcp = mcp
        self._agent_id = agent_id

    @hookimpl
    async def run_model(self, prompt: str | list[dict], session_id: str, state: dict) -> str:
        """Execute the ReAct loop and populate state with results."""
        from simu_sdk.tape.context import ContextWindow

        event = state.get("_inbound_event")

        # Build ContextWindow from state
        context = ContextWindow(
            events=state.get("context_events", []),
            summary=state.get("context_summary", ""),
            total_events=len(state.get("context_events", [])),
        )

        system_prompt = prompt if isinstance(prompt, str) else ""

        result = await self._react_loop.run(
            system_prompt=system_prompt,
            event=event,
            context=context,
            tape=self._tape,
            agent_id=self._agent_id,
            server=self._mcp,
        )

        # Store result in state for downstream hooks
        state["response_content"] = result.content
        state["ended_by_tool"] = result.ended_by_tool

        # Build response event
        response_event = TapeEvent(
            src=f"agent:{self._agent_id}",
            dst=[event.src],
            event_type=EventType.RESPONSE,
            payload={"content": result.content},
            session_id=session_id,
            parent_event_id=event.event_id,
            root_event_id=getattr(event, "root_event_id", None) or event.event_id,
            invocation_id=getattr(event, "invocation_id", None),
        )
        state["response_event"] = response_event

        # Signal task session creation
        if result.ended_by_tool == "create_task_session":
            state["new_task_session"] = True

        return result.content
