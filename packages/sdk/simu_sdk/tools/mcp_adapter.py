"""MCPToolAdapter — bridges MCP tool discovery with the agent's ToolRegistry.

Discovers tools from MCP servers via ``list_tools()``, converts them to
ToolRegistry-compatible definitions, and creates handlers that route
tool calls back to the appropriate MCP session.

Agent-side session management hooks are registered for tools that need
local state updates (send_message, create_task_session, finish_task_session).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Callable

from simu_sdk.tools.registry import ToolMeta, ToolResult

if TYPE_CHECKING:
    from simu_shared.models import TapeEvent

    from simu_sdk.mcp_client import MCPServerClient, _MCPSession
    from simu_sdk.tools.registry import ToolRegistry
    from simu_sdk.tools.standard import SessionStateManager

logger = logging.getLogger(__name__)

# Maximum nesting depth for task sessions
MAX_TASK_DEPTH = 5

# Tools that are internal infrastructure — never exposed to LLM
_INTERNAL_TOOLS = frozenset({
    "push_tape_event",
    "complete_invocation",
    "update_session_title",
})

# Parameters that the agent auto-injects (removed from LLM-visible schema)
_INJECTED_PARAMS: dict[str, set[str]] = {
    "send_message": {"session_id"},
    "create_task_session": {"parent_session_id", "depth"},
    "finish_task_session": {"task_session_id", "parent_session_id"},
}

# Tools that need agent-side session management hooks
_HOOKED_TOOLS = frozenset({
    "send_message",
    "create_task_session",
    "finish_task_session",
})


class MCPToolAdapter:
    """Discover MCP tools and register them with the agent's ToolRegistry.

    Replaces the hardcoded tool definitions in StandardTools with
    dynamically discovered MCP tool schemas.  Tools that need agent-side
    session management get pre/post hooks for parameter injection and
    state updates.
    """

    def __init__(
        self,
        mcp: MCPServerClient,
        session_state: SessionStateManager,
        agent_id: str = "",
    ) -> None:
        self._mcp = mcp
        self._session_state = session_state
        self._agent_id = agent_id
        # tool_name → MCP session (for routing calls)
        self._tool_sessions: dict[str, _MCPSession] = {}

    async def discover_and_register(self, registry: ToolRegistry) -> list[str]:
        """Discover MCP tools and register them in the ToolRegistry.

        Returns the list of registered tool names.
        """
        registered: list[str] = []

        simu_tools, role_tools = await self._mcp.list_tools()

        for tool in simu_tools:
            if tool.name in _INTERNAL_TOOLS:
                continue
            self._tool_sessions[tool.name] = self._mcp.get_session("simu")
            meta = self._to_tool_meta(tool)
            handler = self._create_handler(tool.name)
            registry.register_tool(meta, handler)
            registered.append(tool.name)

        for tool in role_tools:
            if tool.name in _INTERNAL_TOOLS:
                continue
            self._tool_sessions[tool.name] = self._mcp.get_session("role")
            meta = self._to_tool_meta(tool)
            handler = self._create_handler(tool.name)
            registry.register_tool(meta, handler)
            registered.append(tool.name)

        logger.info("Discovered %d MCP tools: %s", len(registered), ", ".join(registered))
        return registered

    # ------------------------------------------------------------------
    # Schema conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _to_tool_meta(tool: Any) -> ToolMeta:
        """Convert an MCP ``Tool`` object to a ``ToolMeta``."""
        schema = tool.inputSchema or {}
        properties = dict(schema.get("properties", {}))
        required = list(schema.get("required", []))

        # Remove auto-injected parameters from LLM-visible schema
        injected = _INJECTED_PARAMS.get(tool.name, set())
        for param in injected:
            properties.pop(param, None)
        required = [r for r in required if r not in injected]

        return ToolMeta(
            name=tool.name,
            description=tool.description or "",
            parameters=properties,
            required=tuple(required),
            category="mcp",
        )

    # ------------------------------------------------------------------
    # Handler creation
    # ------------------------------------------------------------------

    def _create_handler(self, tool_name: str) -> Callable:
        """Create a handler function for an MCP tool."""
        if tool_name == "send_message":
            return self._handle_send_message
        if tool_name == "create_task_session":
            return self._handle_create_task_session
        if tool_name == "finish_task_session":
            return self._handle_finish_task_session
        # Pure pass-through — call MCP directly
        return self._make_passthrough_handler(tool_name)

    def _make_passthrough_handler(self, tool_name: str) -> Callable:
        """Create a handler that forwards args directly to MCP."""
        session = self._tool_sessions[tool_name]

        async def handler(args: dict, event: TapeEvent) -> str:
            result = await session.call_tool(tool_name, args)
            if result.isError:
                from simu_sdk.mcp_client import MCPCallError

                raise MCPCallError(tool_name, result)
            return _extract_text(result)

        return handler

    # ------------------------------------------------------------------
    # Hooked handlers — MCP call + agent-side state management
    # ------------------------------------------------------------------

    async def _handle_send_message(
        self, args: dict, event: TapeEvent,
    ) -> str | ToolResult:
        """send_message with self-send guard and await_reply support."""
        recipients = args.get("recipients", [])

        # Self-send guard
        if self._agent_id and self._agent_id in recipients:
            return ToolResult(
                output=f"Error: cannot send a message to yourself ({self._agent_id}).",
                success=False,
            )

        # Inject session_id
        call_args = {**args, "session_id": event.session_id}

        session = self._tool_sessions["send_message"]
        result = await session.call_tool("send_message", call_args)
        if result.isError:
            from simu_sdk.mcp_client import MCPCallError

            raise MCPCallError("send_message", result)

        text = _extract_text(result)
        response = json.loads(text)

        if args.get("await_reply") and self._session_state:
            event_id = response.get("event_id", "")
            for r in recipients:
                awaiting = f"agent:{r}" if not r.startswith("agent:") else r
                self._session_state.add_pending_reply(
                    event.session_id,
                    event_id,
                    awaiting_from=awaiting,
                )
            return ToolResult(
                output="Message sent. Waiting for reply — session paused.",
                ends_loop=True,
            )
        return "Message sent."

    async def _handle_create_task_session(
        self, args: dict, event: TapeEvent,
    ) -> str | ToolResult:
        """create_task_session with session state management."""
        if self._session_state is None:
            return "Error: session state manager not available."

        current_depth = self._session_state.get_depth(event.session_id)
        if current_depth >= MAX_TASK_DEPTH:
            return f"Error: maximum task nesting depth ({MAX_TASK_DEPTH}) reached."

        # Inject parent_session_id and depth
        call_args = {
            **args,
            "parent_session_id": event.session_id,
            "depth": current_depth + 1,
        }

        session = self._tool_sessions["create_task_session"]
        result = await session.call_tool("create_task_session", call_args)
        if result.isError:
            from simu_sdk.mcp_client import MCPCallError

            raise MCPCallError("create_task_session", result)

        text = _extract_text(result)
        task_session_id = json.loads(text)["task_session_id"]

        # Register in session state
        self._session_state.register_task_session(
            task_session_id=task_session_id,
            parent_session_id=event.session_id,
            depth=current_depth + 1,
            goal=args.get("goal", ""),
        )
        self._session_state.add_pending_task(event.session_id, task_session_id)
        self._session_state.set_active_session(task_session_id)
        self._session_state.set_pending_enter(task_session_id)

        logger.info(
            "Created task session %s (parent=%s, depth=%d, goal=%s)",
            task_session_id,
            event.session_id,
            current_depth + 1,
            args.get("goal", ""),
        )
        return ToolResult(
            output=f"Task session created: {task_session_id}. Processing task now.",
            ends_loop=True,
        )

    async def _handle_finish_task_session(
        self, args: dict, event: TapeEvent,
    ) -> str | ToolResult:
        """finish_task_session with session state management.

        Handles both completion (status="completed") and failure
        (status="failed").
        """
        if self._session_state is None:
            return "Error: session state manager not available."

        parent_id = self._session_state.get_parent(event.session_id)
        if parent_id is None:
            return (
                "Error: only the task creator can finish a task session. "
                "You are a participant, not the creator of this task."
            )

        status = args.get("status", "completed")

        # Inject task_session_id and parent_session_id
        call_args = {
            "task_session_id": event.session_id,
            "parent_session_id": parent_id,
            "result": args.get("result", ""),
            "status": status,
        }

        session = self._tool_sessions["finish_task_session"]
        result = await session.call_tool("finish_task_session", call_args)
        if result.isError:
            from simu_sdk.mcp_client import MCPCallError

            raise MCPCallError("finish_task_session", result)

        # Update session state
        self._session_state.remove_pending_task(parent_id, event.session_id)
        self._session_state.set_active_session(parent_id)

        action = "completed" if status == "completed" else "failed"
        logger.info(
            "Task session %s %s, returning to %s",
            event.session_id, action, parent_id,
        )
        return ToolResult(
            output=f"Task {action}. Returning to parent session {parent_id}.",
            ends_loop=True,
        )


def _extract_text(result: Any) -> str:
    """Extract text content from an MCP ``CallToolResult``."""
    if not result.content:
        return ""
    parts = []
    for block in result.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "\n".join(parts)
