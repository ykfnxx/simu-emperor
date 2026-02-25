"""Tool executor with permission checking."""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any

from simu_emperor.agents.context_builder import SkillScope
from simu_emperor.agents.tools.models import ToolCall, ToolResult
from simu_emperor.agents.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class PermissionDeniedError(Exception):
    """Raised when tool execution is denied due to permission constraints."""

    pass


class ToolExecutor:
    """Executes tools with permission checking."""

    def __init__(self, registry: ToolRegistry, skill_scope: SkillScope) -> None:
        """Initialize executor.

        Args:
            registry: Tool registry containing tool definitions and handlers
            skill_scope: Permission scope for the current skill
        """
        self._registry = registry
        self._skill_scope = skill_scope

    def _check_field_permission(self, field_path: str) -> bool:
        """Check if a field path is within the skill scope.

        Args:
            field_path: Dot-notation field path (e.g., "population.total")

        Returns:
            True if access is permitted
        """
        # Check if field is in allowed fields
        if field_path in self._skill_scope.fields:
            return True

        # Check for wildcard matches (e.g., "commerce.*" matches "commerce.market_prosperity")
        for allowed in self._skill_scope.fields:
            if allowed.endswith(".*"):
                prefix = allowed[:-1]  # "commerce."
                if field_path.startswith(prefix):
                    return True

        return False

    def _check_province_permission(self, province_id: str) -> bool:
        """Check if a province is within the skill scope.

        Args:
            province_id: Province identifier

        Returns:
            True if access is permitted
        """
        if self._skill_scope.provinces == "all":
            return True
        if isinstance(self._skill_scope.provinces, list):
            return province_id in self._skill_scope.provinces
        return False

    def _check_national_permission(self, field_name: str) -> bool:
        """Check if a national-level field is within the skill scope.

        Args:
            field_name: National field name

        Returns:
            True if access is permitted
        """
        return field_name in self._skill_scope.national

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call with permission checking.

        Args:
            tool_call: Tool call request

        Returns:
            ToolResult with serialized result or error
        """
        tool_name = tool_call.tool_name
        handler = self._registry.get_handler(tool_name)

        if handler is None:
            error = f"Unknown tool: {tool_name}"
            logger.error(error)
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_name,
                result=None,
                error=error,
            )

        try:
            # Call handler (may be sync or async)
            if inspect.iscoroutinefunction(handler):
                result = await handler(**tool_call.arguments)
            else:
                result = handler(**tool_call.arguments)

            # Serialize result using model_dump if available
            serialized = self._serialize_result(result)

            logger.debug(f"Tool {tool_name} executed successfully")
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_name,
                result=serialized,
                error=None,
            )

        except PermissionDeniedError as e:
            error = f"Permission denied for tool {tool_name}: {e}"
            logger.warning(error)
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_name,
                result=None,
                error=error,
            )
        except Exception as e:
            error = f"Tool {tool_name} execution failed: {e}"
            logger.error(error, exc_info=True)
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_name,
                result=None,
                error=error,
            )

    async def execute_batch(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """Execute multiple tool calls in parallel.

        Args:
            tool_calls: List of tool call requests

        Returns:
            List of tool results in same order as input
        """
        tasks = [self.execute(call) for call in tool_calls]
        results = await asyncio.gather(*tasks)
        return list(results)

    def _serialize_result(self, value: Any) -> Any:
        """Serialize a result value to JSON-compatible format.

        Uses Pydantic's model_dump for model instances.
        """
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return {k: self._serialize_result(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._serialize_result(item) for item in value]
        if isinstance(value, (int, float, str, bool, type(None))):
            return value
        # Fallback: convert to string
        return str(value)
