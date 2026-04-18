"""MCP authentication — token validation and agent identity context.

Uses a raw ASGI middleware to validate X-Agent-Id / X-Callback-Token headers
and set a contextvars.ContextVar so MCP tool functions can retrieve the
authenticated agent ID without it being a tool parameter (preventing spoofing).
"""

from __future__ import annotations

import contextvars
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Context variable holding the authenticated agent ID for the current request.
current_agent_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_agent_id")

_process_manager: Any = None


def set_process_manager(pm: Any) -> None:
    """Store a reference to the ProcessManager for token validation."""
    global _process_manager
    _process_manager = pm


def get_agent_id() -> str:
    """Return the authenticated agent ID for the current request.

    Raises RuntimeError if called outside an authenticated MCP request.
    """
    try:
        return current_agent_id.get()
    except LookupError:
        raise RuntimeError("No authenticated agent in current context")


class MCPAuthMiddleware:
    """Raw ASGI middleware that wraps an MCP Starlette app.

    Validates ``X-Agent-Id`` and ``X-Callback-Token`` headers before
    forwarding the request to the inner app.  On success the
    ``current_agent_id`` context variable is set so downstream MCP tool
    handlers can call :func:`get_agent_id`.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Extract headers (ASGI headers are list of (bytes, bytes) tuples)
        headers: dict[bytes, bytes] = dict(scope.get("headers", []))
        agent_id = headers.get(b"x-agent-id", b"").decode()
        token = headers.get(b"x-callback-token", b"").decode()

        if not agent_id or not token:
            await self._send_error(send, 401, "Missing X-Agent-Id or X-Callback-Token header")
            return

        if _process_manager is not None:
            expected = _process_manager.get_token(agent_id)
            if expected is None:
                await self._send_error(send, 401, f"Unknown agent: {agent_id}")
                return
            if expected != token:
                await self._send_error(send, 403, "Invalid callback token")
                return

        tok = current_agent_id.set(agent_id)
        try:
            await self.app(scope, receive, send)
        finally:
            current_agent_id.reset(tok)

    @staticmethod
    async def _send_error(send: Any, status: int, detail: str) -> None:
        body = json.dumps({"error": detail}).encode()
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })
