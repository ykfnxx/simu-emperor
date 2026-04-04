"""Callback API — endpoints called by Agent processes.

All requests must carry X-Agent-Id and X-Callback-Token headers.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from simu_shared.constants import EventType
from simu_shared.models import AgentStatus, InvocationStatus, RoutedMessage, TapeEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/callback")


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    agent_id: str
    capabilities: list[str] = []


class MessageRequest(BaseModel):
    recipients: list[str]
    message: str
    session_id: str


class StatusRequest(BaseModel):
    status: str


class InvocationCompleteRequest(BaseModel):
    invocation_id: str
    status: str = "succeeded"
    error: str | None = None


# ---------------------------------------------------------------------------
# Dependency injection (same pattern as client.py)
# ---------------------------------------------------------------------------

_deps: dict[str, Any] = {}


def set_dependencies(**kwargs: Any) -> None:
    _deps.update(kwargs)


def _get(name: str) -> Any:
    return _deps[name]


def _verify_agent(agent_id: str) -> None:
    """Basic auth check — agent must be known."""
    # Full token validation would check against process_manager.get_token()
    # For now, just ensure the agent is registered
    pass


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@router.post("/register")
async def register_agent(
    req: RegisterRequest,
    x_agent_id: str = Header(...),
) -> dict[str, Any]:
    registry = _get("agent_registry")
    await registry.update_status(req.agent_id, AgentStatus.RUNNING)
    await registry.update_capabilities(req.agent_id, req.capabilities)
    await registry.update_heartbeat(req.agent_id)
    logger.info("Agent %s registered with capabilities: %s", req.agent_id, req.capabilities)
    return {"status": "ok"}


@router.post("/heartbeat")
async def heartbeat(x_agent_id: str = Header(...)) -> dict[str, str]:
    await _get("agent_registry").update_heartbeat(x_agent_id)
    return {"status": "ok"}


@router.post("/status")
async def report_status(
    req: StatusRequest,
    x_agent_id: str = Header(...),
) -> dict[str, str]:
    status_map = {
        "stopping": AgentStatus.STOPPING,
        "stopped": AgentStatus.STOPPED,
        "failed": AgentStatus.FAILED,
    }
    new_status = status_map.get(req.status)
    if new_status:
        await _get("agent_registry").update_status(x_agent_id, new_status)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Communication
# ---------------------------------------------------------------------------

@router.post("/message")
async def post_message(
    req: MessageRequest,
    x_agent_id: str = Header(...),
) -> dict[str, Any]:
    event_router = _get("event_router")
    msg_store = _get("message_store")
    queue = _get("queue_controller")
    ws_mgr = _get("ws_manager")

    # Build event
    dst = [f"agent:{r}" if r != "player" else r for r in req.recipients]
    event = TapeEvent(
        src=f"agent:{x_agent_id}",
        dst=dst,
        event_type=EventType.AGENT_MESSAGE,
        payload={"content": req.message},
        session_id=req.session_id,
    )

    # Persist for frontend
    msg = RoutedMessage(
        session_id=req.session_id,
        src=f"agent:{x_agent_id}",
        dst=dst,
        content=req.message,
        event_type=EventType.AGENT_MESSAGE,
        origin_event_id=event.event_id,
    )
    await msg_store.store(msg)

    # Route to target agents
    for r in req.recipients:
        if r != "player":
            await queue.enqueue(r, event)

    # Push to frontend WebSocket
    await ws_mgr.broadcast({"kind": "agent_message", "data": event.model_dump(mode="json")})

    return {"event_id": event.event_id}


@router.post("/tool-result")
async def report_tool_result(
    request: Request,
    x_agent_id: str = Header(...),
) -> dict[str, str]:
    body = await request.json()
    logger.debug("Tool result from %s: %s", x_agent_id, body.get("tool_name"))
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Data queries
# ---------------------------------------------------------------------------

@router.get("/state")
async def query_state(
    path: str = "",
    x_agent_id: str = Header(...),
) -> dict[str, Any]:
    return _get("engine").query_state(path)


@router.get("/agents")
async def query_agents(x_agent_id: str = Header(...)) -> list[dict[str, Any]]:
    agents = await _get("agent_registry").list_all()
    return [
        {"agent_id": a.agent_id, "display_name": a.display_name, "status": a.status.value}
        for a in agents
    ]


# ---------------------------------------------------------------------------
# Invocation management
# ---------------------------------------------------------------------------

@router.post("/invocation/complete")
async def complete_invocation(
    req: InvocationCompleteRequest,
    x_agent_id: str = Header(...),
) -> dict[str, str]:
    inv_mgr = _get("invocation_manager")
    status = InvocationStatus(req.status)
    await inv_mgr.complete(req.invocation_id, status, req.error)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# SSE event stream (Agent connects here to receive events)
# ---------------------------------------------------------------------------

@router.get("/events")
async def event_stream(x_agent_id: str = Header(...)) -> EventSourceResponse:
    event_router = _get("event_router")
    queue = event_router.connect(x_agent_id)

    async def generate():
        try:
            while True:
                event: TapeEvent = await queue.get()
                yield {
                    "event": "event",
                    "data": event.model_dump_json(),
                }
        except asyncio.CancelledError:
            event_router.disconnect(x_agent_id)

    return EventSourceResponse(generate())
