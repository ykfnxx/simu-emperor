"""MCPServerClient — MCP-based client for Agent-to-Server communication.

Replaces the HTTP callback methods on ServerClient with MCP tool calls
via Streamable HTTP transport. Connects to:
  - /mcp/simu — game interaction tools
  - /mcp/role — role/agent query tools

Lifecycle operations (register, heartbeat, SSE) remain on ServerClient.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from simu_shared.models import TapeEvent

logger = logging.getLogger(__name__)

_MAX_RECONNECT_ATTEMPTS = 3


class MCPCallError(Exception):
    """Raised when an MCP tool call returns an error."""

    def __init__(self, tool_name: str, result: Any) -> None:
        self.tool_name = tool_name
        self.result = result
        text = _extract_text(result)
        super().__init__(f"MCP tool '{tool_name}' failed: {text}")


def _extract_text(result: Any) -> str:
    """Extract text content from a CallToolResult."""
    if not result.content:
        return ""
    parts = []
    for block in result.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "\n".join(parts)


class _MCPSession:
    """Manages a single MCP session with its transport context managers."""

    def __init__(self, url: str, headers: dict[str, str]) -> None:
        self._url = url
        self._headers = headers
        self._session: ClientSession | None = None
        self._contexts: list[Any] = []

    @property
    def connected(self) -> bool:
        return self._session is not None

    async def open(self) -> None:
        """Establish the MCP session."""
        transport_cm = streamablehttp_client(self._url, headers=self._headers, timeout=120)
        read, write, _ = await transport_cm.__aenter__()
        self._contexts.append(transport_cm)
        session_cm = ClientSession(read, write)
        self._session = await session_cm.__aenter__()
        self._contexts.append(session_cm)
        await self._session.initialize()

    async def close(self) -> None:
        """Tear down the session and all transport contexts."""
        for cm in reversed(self._contexts):
            try:
                await cm.__aexit__(None, None, None)
            except Exception:
                pass
        self._contexts.clear()
        self._session = None

    async def call_tool(self, tool: str, args: dict[str, Any]) -> Any:
        """Call a tool, reconnecting once on connection failure."""
        for attempt in range(_MAX_RECONNECT_ATTEMPTS):
            if not self.connected:
                try:
                    await self.open()
                except Exception:
                    if attempt == _MAX_RECONNECT_ATTEMPTS - 1:
                        raise
                    logger.warning("MCP reconnect attempt %d failed for %s", attempt + 1, self._url)
                    continue

            try:
                return await self._session.call_tool(tool, args)
            except asyncio.CancelledError:
                # CancelledError (BaseException) can escape from anyio cancel
                # scopes inside the MCP transport when the HTTP request times
                # out.  Treat it as a connection failure and try to reconnect.
                logger.warning("MCP call cancelled for %s, reconnecting...", tool)
                await self.close()
                if attempt == _MAX_RECONNECT_ATTEMPTS - 1:
                    raise
            except Exception:
                logger.warning("MCP call failed for %s, reconnecting...", tool)
                await self.close()
                if attempt == _MAX_RECONNECT_ATTEMPTS - 1:
                    raise

        raise RuntimeError(f"MCP call to {tool} failed after {_MAX_RECONNECT_ATTEMPTS} attempts")


class MCPServerClient:
    """Agent's MCP connection to the Server.

    Manages two MCP sessions (simu + role) over Streamable HTTP.
    Sessions auto-reconnect on connection failure.
    Authentication is via X-Agent-Id / X-Callback-Token headers.
    """

    def __init__(self, server_url: str, agent_id: str, agent_token: str) -> None:
        base_url = server_url.rstrip("/")
        self._agent_id = agent_id
        headers = {
            "X-Agent-Id": agent_id,
            "X-Callback-Token": agent_token,
        }
        self._simu = _MCPSession(f"{base_url}/mcp/simu", headers)
        self._role = _MCPSession(f"{base_url}/mcp/role", headers)

    async def connect(self) -> None:
        """Establish MCP sessions to both simu and role servers."""
        try:
            await self._simu.open()
            await self._role.open()
        except Exception:
            # Clean up any partially established connections
            await self.close()
            raise
        logger.info("MCP sessions established for agent %s", self._agent_id)

    async def close(self) -> None:
        """Tear down MCP sessions."""
        await self._simu.close()
        await self._role.close()

    # ------------------------------------------------------------------
    # Internal call helpers
    # ------------------------------------------------------------------

    async def _call_simu(self, tool: str, args: dict[str, Any]) -> str:
        result = await self._simu.call_tool(tool, args)
        if result.isError:
            raise MCPCallError(tool, result)
        return _extract_text(result)

    async def _call_role(self, tool: str, args: dict[str, Any]) -> str:
        result = await self._role.call_tool(tool, args)
        if result.isError:
            raise MCPCallError(tool, result)
        return _extract_text(result)

    # ------------------------------------------------------------------
    # Game interaction (simu-mcp)
    # ------------------------------------------------------------------

    async def query_state(self, path: str = "") -> dict[str, Any]:
        text = await self._call_simu("query_state", {"path": path})
        return json.loads(text)

    async def post_message(
        self,
        recipients: list[str],
        message: str,
        session_id: str,
    ) -> str:
        text = await self._call_simu("send_message", {
            "recipients": recipients,
            "message": message,
            "session_id": session_id,
        })
        return json.loads(text).get("event_id", "")

    async def push_tape_event(self, event: TapeEvent, route: bool = False) -> None:
        try:
            await self._call_simu("push_tape_event", {
                "event_id": event.event_id,
                "session_id": event.session_id,
                "src": event.src,
                "dst": event.dst,
                "event_type": event.event_type,
                "payload": event.payload,
                "timestamp": event.timestamp.isoformat(),
                "parent_event_id": event.parent_event_id,
                "route": route,
            })
        except (Exception, asyncio.CancelledError):
            logger.warning("Failed to push tape event via MCP", exc_info=True)

    async def create_task_session(
        self,
        parent_session_id: str,
        goal: str,
        description: str = "",
        constraints: str = "",
        timeout_seconds: int = 300,
        depth: int = 1,
    ) -> str:
        text = await self._call_simu("create_task_session", {
            "parent_session_id": parent_session_id,
            "goal": goal,
            "description": description,
            "constraints": constraints,
            "timeout_seconds": timeout_seconds,
            "depth": depth,
        })
        return json.loads(text)["task_session_id"]

    async def finish_task_session(
        self,
        task_session_id: str,
        parent_session_id: str,
        result: str,
        status: str = "completed",
    ) -> None:
        await self._call_simu("finish_task_session", {
            "task_session_id": task_session_id,
            "parent_session_id": parent_session_id,
            "result": result,
            "status": status,
        })

    async def create_incident(
        self,
        title: str,
        effects: list[dict[str, str]],
        remaining_ticks: int,
        description: str = "",
        source: str = "",
    ) -> dict[str, Any]:
        text = await self._call_simu("create_incident", {
            "title": title,
            "description": description,
            "effects": effects,
            "remaining_ticks": remaining_ticks,
            "source": source,
        })
        return json.loads(text)

    # ------------------------------------------------------------------
    # Invocation management (simu-mcp)
    # ------------------------------------------------------------------

    async def complete_invocation(
        self,
        invocation_id: str,
        status: str = "succeeded",
        error: str | None = None,
    ) -> None:
        await self._call_simu("complete_invocation", {
            "invocation_id": invocation_id,
            "status": status,
            "error": error,
        })

    async def update_session_title(self, session_id: str, title: str) -> None:
        try:
            await self._call_simu("update_session_title", {
                "session_id": session_id,
                "title": title,
            })
        except Exception:
            logger.warning("Failed to update session title via MCP", exc_info=True)

    async def report_error(self, event: TapeEvent, error: Exception) -> None:
        """Report an unhandled error back to the Server."""
        logger.exception("Error processing event %s", event.event_id)
        if event.invocation_id:
            await self.complete_invocation(
                event.invocation_id,
                status="failed",
                error=str(error),
            )

    # ------------------------------------------------------------------
    # Role queries (role-mcp)
    # ------------------------------------------------------------------

    async def query_role_map(self) -> dict[str, Any]:
        text = await self._call_role("query_role_map", {})
        return json.loads(text)
