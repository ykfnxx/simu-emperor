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
from simu_shared.models import AgentStatus, InvocationStatus, RoutedMessage, SessionStatus, TapeEvent

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


class CreateTaskSessionRequest(BaseModel):
    parent_session_id: str
    goal: str
    description: str = ""
    constraints: str = ""
    timeout_seconds: int = 300
    depth: int = 1


class FinishTaskSessionRequest(BaseModel):
    task_session_id: str
    parent_session_id: str
    result: str
    status: str = "completed"  # "completed" or "failed"


# ---------------------------------------------------------------------------
# Dependency injection (same pattern as client.py)
# ---------------------------------------------------------------------------

_deps: dict[str, Any] = {}


def set_dependencies(**kwargs: Any) -> None:
    _deps.update(kwargs)


def _get(name: str, default: Any = None) -> Any:
    return _deps.get(name, default)


async def _verify_agent(agent_id: str, token: str) -> None:
    """Verify that the agent is registered and the callback token is valid."""
    process_manager = _get("process_manager")
    if process_manager is None:
        return
    expected_token = process_manager.get_token(agent_id)
    if expected_token is None:
        raise HTTPException(status_code=401, detail=f"Unknown agent: {agent_id}")
    if expected_token != token:
        raise HTTPException(status_code=403, detail="Invalid callback token")


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@router.post("/register")
async def register_agent(
    req: RegisterRequest,
    x_agent_id: str = Header(...),
    x_callback_token: str = Header(...),
) -> dict[str, Any]:
    await _verify_agent(x_agent_id, x_callback_token)
    if req.agent_id != x_agent_id:
        raise HTTPException(
            status_code=403,
            detail=f"Header agent '{x_agent_id}' cannot register as '{req.agent_id}'",
        )
    registry = _get("agent_registry")
    await registry.update_status(x_agent_id, AgentStatus.RUNNING)
    await registry.update_capabilities(x_agent_id, req.capabilities)
    await registry.update_heartbeat(x_agent_id)
    logger.info("Agent %s registered with capabilities: %s", x_agent_id, req.capabilities)
    return {"status": "ok"}


@router.post("/heartbeat")
async def heartbeat(
    x_agent_id: str = Header(...),
    x_callback_token: str = Header(...),
) -> dict[str, str]:
    await _verify_agent(x_agent_id, x_callback_token)
    await _get("agent_registry").update_heartbeat(x_agent_id)
    return {"status": "ok"}


@router.post("/status")
async def report_status(
    req: StatusRequest,
    x_agent_id: str = Header(...),
    x_callback_token: str = Header(...),
) -> dict[str, str]:
    await _verify_agent(x_agent_id, x_callback_token)
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
    x_callback_token: str = Header(...),
) -> dict[str, Any]:
    await _verify_agent(x_agent_id, x_callback_token)
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

    # Push to frontend WebSocket — use "chat" kind with ChatData format
    # so the frontend's existing 'chat' handler can process it.
    agent_reg = await _get("agent_registry").get(x_agent_id)
    display_name = agent_reg.display_name if agent_reg else x_agent_id
    await ws_mgr.broadcast({
        "kind": "chat",
        "data": {
            "agent": x_agent_id,
            "agentDisplayName": display_name,
            "text": req.message,
            "timestamp": event.timestamp.isoformat(),
            "session_id": req.session_id,
        },
    })

    return {"event_id": event.event_id}


@router.post("/tool-result")
async def report_tool_result(
    request: Request,
    x_agent_id: str = Header(...),
    x_callback_token: str = Header(...),
) -> dict[str, str]:
    await _verify_agent(x_agent_id, x_callback_token)
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
    x_callback_token: str = Header(...),
) -> dict[str, Any]:
    await _verify_agent(x_agent_id, x_callback_token)
    return _get("engine").query_state(path)


@router.get("/agents")
async def query_agents(
    x_agent_id: str = Header(...),
    x_callback_token: str = Header(...),
) -> list[dict[str, Any]]:
    await _verify_agent(x_agent_id, x_callback_token)
    agents = await _get("agent_registry").list_all()
    return [
        {"agent_id": a.agent_id, "display_name": a.display_name, "status": a.status.value}
        for a in agents
    ]


@router.get("/role-map")
async def query_role_map(
    x_agent_id: str = Header(...),
    x_callback_token: str = Header(...),
) -> dict[str, Any]:
    """Return role_map.md content parsed into structured data."""
    await _verify_agent(x_agent_id, x_callback_token)

    from simu_server.config import settings

    role_map_path = settings.data_dir / "role_map.md"
    if not role_map_path.exists():
        return {"roles": []}

    text = role_map_path.read_text(encoding="utf-8")
    roles: list[dict[str, str]] = []
    current: dict[str, str] = {}

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("## "):
            if current:
                roles.append(current)
            # Parse "## 户部尚书 (minister_of_revenue)"
            title_part = line[3:].strip()
            agent_id = ""
            title = title_part
            if "(" in title_part and ")" in title_part:
                idx = title_part.index("(")
                title = title_part[:idx].strip()
                agent_id = title_part[idx + 1 : title_part.index(")")].strip()
            current = {"title": title, "agent_id": agent_id, "name": "", "duty": ""}
        elif line.startswith("- 姓名：") and current:
            current["name"] = line[len("- 姓名：") :].strip()
        elif line.startswith("- 职责：") and current:
            current["duty"] = line[len("- 职责：") :].strip()

    if current:
        roles.append(current)

    return {"roles": roles}


# ---------------------------------------------------------------------------
# Invocation management
# ---------------------------------------------------------------------------

@router.post("/invocation/complete")
async def complete_invocation(
    req: InvocationCompleteRequest,
    x_agent_id: str = Header(...),
    x_callback_token: str = Header(...),
) -> dict[str, str]:
    await _verify_agent(x_agent_id, x_callback_token)
    inv_mgr = _get("invocation_manager")
    status = InvocationStatus(req.status)
    await inv_mgr.complete(req.invocation_id, status, req.error)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Task session management
# ---------------------------------------------------------------------------

@router.post("/task-session/create")
async def create_task_session(
    req: CreateTaskSessionRequest,
    x_agent_id: str = Header(...),
    x_callback_token: str = Header(...),
) -> dict[str, Any]:
    await _verify_agent(x_agent_id, x_callback_token)
    sm = _get("session_manager")
    msg_store = _get("message_store")

    # Create child session with task: prefix
    import uuid as _uuid
    task_session_id = f"task:{_uuid.uuid4().hex[:12]}"
    session = await sm.create(
        created_by=f"agent:{x_agent_id}",
        parent_id=req.parent_session_id,
        session_id=task_session_id,
    )

    # Add the creating agent to the task session's agent list
    await sm.add_agent(task_session_id, x_agent_id)

    # Store task metadata
    await sm.update_metadata(task_session_id, {
        "goal": req.goal,
        "description": req.description,
        "constraints": req.constraints,
        "timeout_seconds": req.timeout_seconds,
        "depth": req.depth,
        "created_by_agent": x_agent_id,
    })

    # Write TASK_CREATED event as first message in the task session
    task_event = RoutedMessage(
        session_id=task_session_id,
        src=f"agent:{x_agent_id}",
        dst=[f"agent:{x_agent_id}"],
        content=f"Task created: {req.goal}",
        event_type=EventType.TASK_CREATED,
    )
    await msg_store.store(task_event)

    logger.info(
        "Agent %s created task session %s (parent=%s, goal=%s)",
        x_agent_id, task_session_id, req.parent_session_id, req.goal,
    )
    return {"task_session_id": task_session_id}


@router.post("/task-session/finish")
async def finish_task_session(
    req: FinishTaskSessionRequest,
    x_agent_id: str = Header(...),
    x_callback_token: str = Header(...),
) -> dict[str, str]:
    await _verify_agent(x_agent_id, x_callback_token)
    sm = _get("session_manager")
    msg_store = _get("message_store")
    ws_mgr = _get("ws_manager")

    # Mark task session as completed/failed
    new_status = SessionStatus.COMPLETED if req.status == "completed" else SessionStatus.FAILED
    await sm.update_status(req.task_session_id, new_status)

    # Write finish event to the PARENT session so the creator sees it
    event_type = EventType.TASK_FINISHED if req.status == "completed" else EventType.TASK_FAILED
    finish_msg = RoutedMessage(
        session_id=req.parent_session_id,
        src=f"agent:{x_agent_id}",
        dst=[f"agent:{x_agent_id}"],
        content=req.result,
        event_type=event_type,
    )
    await msg_store.store(finish_msg)

    # Push to frontend WebSocket
    await ws_mgr.broadcast({
        "kind": "task_finished",
        "data": {
            "task_session_id": req.task_session_id,
            "parent_session_id": req.parent_session_id,
            "status": req.status,
            "result": req.result,
        },
    })

    logger.info(
        "Agent %s finished task session %s (status=%s)",
        x_agent_id, req.task_session_id, req.status,
    )
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# SSE event stream (Agent connects here to receive events)
# ---------------------------------------------------------------------------

@router.get("/events")
async def event_stream(
    x_agent_id: str = Header(...),
    x_callback_token: str = Header(...),
) -> EventSourceResponse:
    await _verify_agent(x_agent_id, x_callback_token)
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
