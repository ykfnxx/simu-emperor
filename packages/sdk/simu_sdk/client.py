"""ServerClient — lifecycle-only HTTP client for Agent-to-Server communication.

Handles agent lifecycle operations:
  - register / deregister / heartbeat
  - SSE event stream (server push to agent)

All game interaction (query_state, send_message, create_incident, etc.)
is handled by MCPServerClient via MCP protocol.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

import httpx
from httpx_sse import aconnect_sse

from simu_shared.models import TapeEvent

logger = logging.getLogger(__name__)


class ServerClient:
    """Agent's lifecycle connection to the Server.

    All requests carry ``X-Agent-Id`` and ``X-Callback-Token`` headers.
    """

    def __init__(self, server_url: str, agent_id: str, agent_token: str) -> None:
        self._base_url = server_url.rstrip("/")
        self._agent_id = agent_id
        self._headers = {
            "X-Agent-Id": agent_id,
            "X-Callback-Token": agent_token,
        }
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def register(self, capabilities: list[str]) -> dict[str, Any]:
        """Register this Agent with the Server after process start."""
        resp = await self._http.post(
            "/api/callback/register",
            json={"agent_id": self._agent_id, "capabilities": capabilities},
        )
        resp.raise_for_status()
        return resp.json()

    async def heartbeat(self) -> None:
        resp = await self._http.post("/api/callback/heartbeat")
        resp.raise_for_status()

    async def deregister(self) -> None:
        resp = await self._http.post(
            "/api/callback/status",
            json={"status": "stopping"},
        )
        resp.raise_for_status()

    # ------------------------------------------------------------------
    # SSE event stream
    # ------------------------------------------------------------------

    async def event_stream(self) -> AsyncIterator[TapeEvent]:
        """Yield events from the Server's SSE endpoint.

        Automatically reconnects on transient failures.
        """
        while True:
            try:
                async with aconnect_sse(
                    self._http,
                    "GET",
                    "/api/callback/events",
                ) as event_source:
                    async for sse in event_source.aiter_sse():
                        if sse.event == "event":
                            data = json.loads(sse.data)
                            yield TapeEvent(**data)
            except httpx.ReadError:
                logger.warning("SSE connection lost, reconnecting...")
                continue
            except Exception:
                logger.exception("SSE stream error")
                raise

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self._http.aclose()
