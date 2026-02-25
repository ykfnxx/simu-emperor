"""Tool registry for managing available tools."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from .models import Tool

logger = logging.getLogger(__name__)

# Type alias for tool handler functions
ToolHandler = Callable[..., Any]


class ToolRegistry:
    """Registry for managing tools and their handlers."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, tool: Tool, handler: ToolHandler) -> None:
        """Register a tool with its handler function.

        Args:
            tool: Tool definition
            handler: Async or sync function to execute the tool
        """
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool: {tool.name}")
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler
        logger.debug(f"Registered tool: {tool.name}")

    def get_tool(self, name: str) -> Tool | None:
        """Get tool definition by name."""
        return self._tools.get(name)

    def get_handler(self, name: str) -> ToolHandler | None:
        """Get tool handler by name."""
        return self._handlers.get(name)

    def list_tools(self) -> list[Tool]:
        """List all registered tools."""
        return list(self._tools.values())

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def to_openai_schema(self) -> list[dict[str, Any]]:
        """Convert all tools to OpenAI function calling schema.

        Returns:
            List of tool definitions in OpenAI format
        """
        schemas = []
        for tool in self._tools.values():
            properties: dict[str, Any] = {}
            required: list[str] = []

            for param in tool.parameters:
                prop: dict[str, Any] = {
                    "type": param.type,
                    "description": param.description,
                }
                if param.enum is not None:
                    prop["enum"] = param.enum
                properties[param.name] = prop

                if param.required:
                    required.append(param.name)

            schema = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
            schemas.append(schema)

        return schemas
