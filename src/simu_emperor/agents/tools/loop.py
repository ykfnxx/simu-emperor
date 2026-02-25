"""Tool call loop for iterative LLM-tool interaction."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from simu_emperor.agents.tools.executor import ToolExecutor
from simu_emperor.agents.tools.models import ToolCallResponse, ToolResult

logger = logging.getLogger(__name__)


class FunctionCallLLMClient(Protocol):
    """Protocol for LLM clients that support function calling."""

    async def generate_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ToolCallResponse:
        """Generate response with optional tool calling support."""
        ...


class ToolCallLoop:
    """Orchestrates iterative LLM-tool interaction loop."""

    def __init__(
        self,
        llm_client: FunctionCallLLMClient,
        executor: ToolExecutor,
        max_iterations: int = 5,
    ) -> None:
        """Initialize the tool call loop.

        Args:
            llm_client: LLM client with function calling support
            executor: Tool executor for running tool calls
            max_iterations: Maximum number of LLM-tool iterations (default 5)
        """
        self._llm_client = llm_client
        self._executor = executor
        self._max_iterations = max_iterations

    async def run(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> str:
        """Run the tool call loop until completion.

        The loop continues until:
        1. LLM returns a response without tool calls, or
        2. Maximum iterations reached

        Args:
            messages: Initial conversation messages
            tools: Available tools in OpenAI schema format

        Returns:
            Final text response from the LLM
        """
        current_messages = list(messages)
        iteration = 0

        while iteration < self._max_iterations:
            iteration += 1
            logger.debug(f"Tool call loop iteration {iteration}/{self._max_iterations}")

            # Call LLM
            response = await self._llm_client.generate_with_tools(
                messages=current_messages,
                tools=tools,
            )

            # If no tool calls, return the content
            if not response.has_tool_calls:
                logger.debug(f"Loop completed after {iteration} iteration(s)")
                return response.content or ""

            # Log tool calls
            tool_names = [tc.tool_name for tc in response.tool_calls or []]
            logger.info(f"Iteration {iteration}: LLM requested tools: {tool_names}")

            # Execute tool calls
            results = await self._executor.execute_batch(response.tool_calls or [])

            # Add assistant message with tool calls
            assistant_message = self._build_assistant_message(response)
            current_messages.append(assistant_message)

            # Add tool result messages
            for result in results:
                tool_message = self._build_tool_message(result)
                current_messages.append(tool_message)

        # Max iterations reached
        logger.warning(f"Tool call loop reached max iterations ({self._max_iterations})")

        # Get final response without tools
        final_response = await self._llm_client.generate_with_tools(
            messages=current_messages,
            tools=None,  # No tools to force text response
        )
        return final_response.content or ""

    def _build_assistant_message(self, response: ToolCallResponse) -> dict[str, Any]:
        """Build assistant message from ToolCallResponse in OpenAI format."""
        message: dict[str, Any] = {"role": "assistant"}

        if response.content:
            message["content"] = response.content

        if response.tool_calls:
            # Convert to OpenAI tool_calls format
            tool_calls = []
            for tc in response.tool_calls:
                tool_calls.append({
                    "id": tc.call_id,
                    "type": "function",
                    "function": {
                        "name": tc.tool_name,
                        "arguments": tc.arguments,
                    },
                })
            message["tool_calls"] = tool_calls

        return message

    def _build_tool_message(self, result: ToolResult) -> dict[str, Any]:
        """Build tool result message in OpenAI format."""
        content: Any
        if result.error:
            content = {"error": result.error}
        else:
            content = result.result

        return {
            "role": "tool",
            "tool_call_id": result.call_id,
            "content": content,
        }
