"""ReActLoop — reason-act-observe cycle driven by an LLM.

The loop repeats:
  1. Call LLM with system prompt + context + current observations
  2. If LLM returns tool calls → execute them, collect results, record to tape
  3. If LLM returns text only → treat as final response, break

Iteration and tool-call limits prevent runaway loops.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from simu_shared.constants import EventType
from simu_shared.models import TapeEvent
from simu_sdk.llm.base import LLMProvider, LLMResponse, ToolCall
from simu_sdk.tape.context import ContextWindow
from simu_sdk.tools.registry import ToolRegistry, ToolResult

if TYPE_CHECKING:
    from simu_sdk.client import ServerClient
    from simu_sdk.tape.manager import TapeManager

logger = logging.getLogger(__name__)


class ReActLoop:
    """Execute the ReAct (Reason → Act → Observe) loop."""

    def __init__(
        self,
        llm: LLMProvider,
        tools: ToolRegistry,
        max_iterations: int = 10,
        max_tool_calls: int = 20,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._max_iterations = max_iterations
        self._max_tool_calls = max_tool_calls

    async def run(
        self,
        system_prompt: str,
        event: TapeEvent,
        context: ContextWindow,
        tape: TapeManager | None = None,
        agent_id: str = "",
        server: ServerClient | None = None,
    ) -> ReActResult:
        """Run the loop and return the final result."""
        messages = self._build_initial_messages(event, context)
        tool_defs = self._tools.to_function_definitions() or None

        total_tool_calls = 0
        iterations = 0

        while iterations < self._max_iterations:
            iterations += 1

            response = await self._llm.call(
                messages=messages,
                tools=tool_defs,
                system=system_prompt,
            )

            if not response.has_tool_calls:
                return ReActResult(
                    content=response.content,
                    iterations=iterations,
                    tool_calls_count=total_tool_calls,
                )

            # Record assistant reasoning + tool calls to tape
            if tape:
                tape_evt = await self._record_tool_calls(
                    tape,
                    event,
                    response,
                    agent_id,
                )
                if server and tape_evt:
                    await server.push_tape_event(tape_evt)

            # Execute tool calls
            tool_results: list[dict[str, str]] = []
            for tc in response.tool_calls:
                if total_tool_calls >= self._max_tool_calls:
                    tool_results.append(
                        {
                            "tool_call_id": tc.id,
                            "output": "Error: tool call limit reached.",
                        }
                    )
                    continue

                total_tool_calls += 1
                result = await self._execute_tool(tc, event)
                tool_results.append(
                    {
                        "tool_call_id": tc.id,
                        "output": result.output,
                    }
                )

                # Record tool result to tape
                if tape:
                    tape_evt = await self._record_tool_result(
                        tape,
                        event,
                        tc,
                        result,
                        agent_id,
                    )
                    if server and tape_evt:
                        await server.push_tape_event(tape_evt)

                if result.ends_loop:
                    return ReActResult(
                        content=result.output,
                        iterations=iterations,
                        tool_calls_count=total_tool_calls,
                        ended_by_tool=tc.name,
                    )

            # Append assistant message + tool results for next iteration
            messages.append(self._assistant_message(response))
            tool_msgs = self._tool_results_message(tool_results)
            if isinstance(tool_msgs, list):
                messages.extend(tool_msgs)  # OpenAI: one message per tool call
            else:
                messages.append(tool_msgs)  # Anthropic: single user message

        # Max iterations reached
        return ReActResult(
            content="[Max iterations reached]",
            iterations=iterations,
            tool_calls_count=total_tool_calls,
        )

    # ------------------------------------------------------------------
    # Tape recording helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _record_tool_calls(
        tape: TapeManager,
        event: TapeEvent,
        response: LLMResponse,
        agent_id: str,
    ) -> TapeEvent:
        """Record the assistant's reasoning and tool calls to tape."""
        calls_summary = [{"name": tc.name, "arguments": tc.arguments} for tc in response.tool_calls]
        tape_event = TapeEvent(
            src=f"agent:{agent_id}",
            dst=[f"agent:{agent_id}"],
            event_type=EventType.TOOL_CALL,
            payload={
                "reasoning": response.content or "",
                "tool_calls": calls_summary,
            },
            session_id=event.session_id,
            parent_event_id=event.event_id,
        )
        await tape.append(tape_event)
        return tape_event

    @staticmethod
    async def _record_tool_result(
        tape: TapeManager,
        event: TapeEvent,
        tc: ToolCall,
        result: ToolResult,
        agent_id: str,
    ) -> TapeEvent:
        """Record a single tool result (observation) to tape."""
        tape_event = TapeEvent(
            src=f"agent:{agent_id}",
            dst=[f"agent:{agent_id}"],
            event_type=EventType.TOOL_RESULT,
            payload={
                "tool_name": tc.name,
                "output": result.output,
                "success": result.success,
            },
            session_id=event.session_id,
            parent_event_id=event.event_id,
        )
        await tape.append(tape_event)
        return tape_event

    # ------------------------------------------------------------------
    # Message construction
    # ------------------------------------------------------------------

    def _build_initial_messages(
        self,
        event: TapeEvent,
        context: ContextWindow,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []

        # Inject context summary if present
        if context.summary:
            messages.append(
                {
                    "role": "user",
                    "content": f"[Context summary]\n{context.summary}",
                }
            )

        # Inject recent tape events as context
        for tape_event in context.events:
            role = "assistant" if tape_event.src.startswith("agent:") else "user"
            content = tape_event.payload.get("content", "")
            if content:
                messages.append({"role": role, "content": content})

        # The triggering event
        messages.append(
            {
                "role": "user",
                "content": event.payload.get(
                    "content", json.dumps(event.payload, ensure_ascii=False)
                ),
            }
        )

        return messages

    def _assistant_message(self, response: LLMResponse) -> dict[str, Any]:
        if self._llm.message_format == "anthropic":
            return self._assistant_message_anthropic(response)
        return self._assistant_message_openai(response)

    def _tool_results_message(self, results: list[dict[str, str]]) -> dict[str, Any]:
        if self._llm.message_format == "anthropic":
            return self._tool_results_anthropic(results)
        return self._tool_results_openai(results)

    # --- Anthropic format ---

    @staticmethod
    def _assistant_message_anthropic(response: LLMResponse) -> dict[str, Any]:
        content_parts: list[Any] = []
        if response.content:
            content_parts.append({"type": "text", "text": response.content})
        for tc in response.tool_calls:
            content_parts.append(
                {
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,
                }
            )
        return {"role": "assistant", "content": content_parts}

    @staticmethod
    def _tool_results_anthropic(results: list[dict[str, str]]) -> dict[str, Any]:
        content_parts = []
        for r in results:
            content_parts.append(
                {
                    "type": "tool_result",
                    "tool_use_id": r["tool_call_id"],
                    "content": r["output"],
                }
            )
        return {"role": "user", "content": content_parts}

    # --- OpenAI format ---

    @staticmethod
    def _assistant_message_openai(response: LLMResponse) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": "assistant", "content": response.content or None}
        if response.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in response.tool_calls
            ]
        return msg

    @staticmethod
    def _tool_results_openai(results: list[dict[str, str]]) -> list[dict[str, str]]:
        """OpenAI returns tool results as separate messages per tool call."""
        return [
            {
                "role": "tool",
                "tool_call_id": r["tool_call_id"],
                "content": r["output"],
            }
            for r in results
        ]

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def _execute_tool(self, tc: ToolCall, event: TapeEvent) -> ToolResult:
        handler = self._tools.get_handler(tc.name)
        if handler is None:
            return ToolResult(output=f"Unknown tool: {tc.name}", success=False)
        try:
            output = await handler(tc.arguments, event)
            if isinstance(output, ToolResult):
                return output
            return ToolResult(output=str(output))
        except Exception as exc:
            logger.exception("Tool %s failed", tc.name)
            return ToolResult(output=f"Tool error: {exc}", success=False)


class ReActResult:
    """Outcome of a complete ReAct loop execution."""

    __slots__ = ("content", "iterations", "tool_calls_count", "ended_by_tool")

    def __init__(
        self,
        content: str,
        iterations: int,
        tool_calls_count: int,
        ended_by_tool: str | None = None,
    ) -> None:
        self.content = content
        self.iterations = iterations
        self.tool_calls_count = tool_calls_count
        self.ended_by_tool = ended_by_tool
