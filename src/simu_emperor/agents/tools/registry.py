"""Decorator-based tool registration system.

Replaces imperative _register_* methods with declarative @tool decorators.
"""

import functools
import logging
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Structured result from tool execution.

    Replaces emoji-prefix string checking (startswith("✅")).
    """

    output: str
    success: bool = True
    side_effect: Any = None  # e.g., an Event to add to tape
    ends_loop: bool = False
    creates_task: bool = False
    closes_task: bool = False  # finish_task_session / fail_task_session


@dataclass
class ToolMeta:
    """Metadata attached to a method by the @tool decorator."""

    name: str
    description: str
    parameters: dict
    category: str = "action"


def tool(name: str, description: str, parameters: dict, category: str = "action") -> Callable:
    """Decorator that marks a method as a registered tool.

    Usage::

        @tool(name="query_data", description="...", parameters={...}, category="query")
        async def query_data(self, args: dict, event: Event) -> str:
            ...
    """

    def decorator(fn: Callable) -> Callable:
        meta = ToolMeta(
            name=name, description=description, parameters=parameters, category=category
        )
        fn._tool_meta = meta

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await fn(*args, **kwargs)

        wrapper._tool_meta = meta
        return wrapper

    return decorator


class ToolProvider:
    """Base class for tool handler groups. Subclass and use @tool decorators."""

    pass


class ToolRegistry:
    """Discovers @tool-decorated methods from providers and manages tools.

    Replaces the old imperative ToolRegistry (tool_registry.py).
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolMeta] = {}
        self._handlers: dict[str, Callable] = {}

    def register_provider(self, provider: ToolProvider) -> None:
        """Auto-discover all @tool-decorated methods from a provider.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        for attr_name in dir(provider):
            if attr_name.startswith("__"):
                continue
            method = getattr(provider, attr_name, None)
            if method is None:
                continue
            meta = getattr(method, "_tool_meta", None)
            if not isinstance(meta, ToolMeta):
                continue
            if meta.name in self._tools:
                raise ValueError(f"Duplicate tool: {meta.name}")
            self._tools[meta.name] = meta
            self._handlers[meta.name] = method

    def get(self, name: str) -> ToolMeta | None:
        """Get tool metadata by name."""
        return self._tools.get(name)

    def get_handler(self, name: str) -> Callable | None:
        """Get tool handler by name."""
        return self._handlers.get(name)

    def to_function_definitions(self) -> list[dict]:
        """Export all tools as LLM Function Calling format."""
        return [
            {
                "name": meta.name,
                "description": meta.description,
                "parameters": meta.parameters,
            }
            for meta in self._tools.values()
        ]

    def list_by_category(self, category: str) -> list[ToolMeta]:
        """List tools by category."""
        return [m for m in self._tools.values() if m.category == category]

    def list_all(self) -> list[ToolMeta]:
        """List all registered tools."""
        return list(self._tools.values())

    def register_tool(self, name: str, meta: "ToolMeta", handler: Callable) -> None:
        """Manually register a tool (for cases not covered by @tool decorator)."""
        if name in self._tools:
            raise ValueError(f"Duplicate tool: {name}")
        self._tools[name] = meta
        self._handlers[name] = handler
