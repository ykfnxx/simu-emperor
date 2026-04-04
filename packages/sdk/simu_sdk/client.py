"""ServerClient — HTTP client for Agent-to-Server communication.

Handles callback API calls (register, heartbeat, message, state query)
and the SSE event stream for receiving events from the Server.
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
    """Agent's connection to the Server.

    All callback requests carry ``X-Agent-Id`` and ``X-Callback-Token`` headers.
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
    # Communication (standard tools)
    # ------------------------------------------------------------------

    async def post_message(
        self,
        recipients: list[str],
        message: str,
        session_id: str,
    ) -> str:
        """Send a message through the Server for routing."""
        resp = await self._http.post(
            "/api/callback/message",
            json={
                "recipients": recipients,
                "message": message,
                "session_id": session_id,
            },
        )
        resp.raise_for_status()
        return resp.json().get("event_id", "")

    async def query_state(self, path: str = "") -> dict[str, Any]:
        """Query game state from the Server."""
        resp = await self._http.get(
            "/api/callback/state",
            params={"path": path} if path else {},
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Invocation management
    # ------------------------------------------------------------------

    async def complete_invocation(
        self,
        invocation_id: str,
        status: str = "succeeded",
        error: str | None = None,
    ) -> None:
        resp = await self._http.post(
            "/api/callback/invocation/complete",
            json={
                "invocation_id": invocation_id,
                "status": status,
                "error": error,
            },
        )
        resp.raise_for_status()

    async def report_error(self, event: TapeEvent, error: Exception) -> None:
        """Report an unhandled error back to the Server."""
        logger.exception("Error processing event %s", event.event_id)
        if event.invocation_id:
            await self.complete_invocation(
                event.invocation_id, status="failed", error=str(error),
            )

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
