"""Tool registry with @tool decorator for auto-discovery.

Usage:
    class MyAgent(SimuAgent):
        @tool(name="greet", description="Say hello", parameters={"name": {"type": "string"}})
        async def greet(self, args: dict, event: TapeEvent) -> str:
            return f"Hello {args['name']}"
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class ToolMeta:
    """Metadata attached to a tool-decorated method."""

    name: str
    description: str
    parameters: dict[str, Any]
    category: str = "action"
    required: tuple[str, ...] = ()


@dataclass
class ToolResult:
    """Return value from a tool execution."""

    output: str
    success: bool = True
    ends_loop: bool = False


_TOOL_ATTR = "_tool_meta"


def tool(
    name: str,
    description: str,
    parameters: dict[str, Any] | None = None,
    category: str = "action",
) -> Callable:
    """Decorator that marks a method as a registered tool.

    The decorated method must have signature:
        async def method(self, args: dict, event: TapeEvent) -> str
    """

    def decorator(func: Callable) -> Callable:
        setattr(
            func,
            _TOOL_ATTR,
            ToolMeta(
                name=name,
                description=description,
                parameters=parameters or {},
                category=category,
            ),
        )
        return func

    return decorator


class ToolRegistry:
    """Discovers @tool-decorated methods from provider objects.

    Provides lookup by name and conversion to LLM function-calling format.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolMeta] = {}
        self._handlers: dict[str, Callable] = {}

    def register_provider(self, provider: object) -> None:
        """Scan *provider* for @tool-decorated methods and register them."""
        for _, method in inspect.getmembers(provider, predicate=inspect.ismethod):
            meta: ToolMeta | None = getattr(method, _TOOL_ATTR, None)
            if meta is not None:
                self._tools[meta.name] = meta
                self._handlers[meta.name] = method

    def register_tool(self, meta: ToolMeta, handler: Callable) -> None:
        """Register a single tool with its handler directly."""
        self._tools[meta.name] = meta
        self._handlers[meta.name] = handler

    def get(self, name: str) -> ToolMeta | None:
        return self._tools.get(name)

    def get_handler(self, name: str) -> Callable | None:
        return self._handlers.get(name)

    def list_names(self) -> list[str]:
        return list(self._tools)

    def to_function_definitions(self) -> list[dict[str, Any]]:
        """Convert registered tools to OpenAI-compatible function definitions."""
        definitions: list[dict[str, Any]] = []
        for meta in self._tools.values():
            params: dict[str, Any] = {
                "type": "object",
                "properties": meta.parameters,
            }
            if meta.required:
                params["required"] = list(meta.required)
            definitions.append(
                {
                    "type": "function",
                    "function": {
                        "name": meta.name,
                        "description": meta.description,
                        "parameters": params,
                    },
                }
            )
        return definitions
