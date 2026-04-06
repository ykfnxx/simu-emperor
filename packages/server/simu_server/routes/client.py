"""Client API — endpoints consumed by the Web frontend and CLI.

Preserves all V4 Web API functionality per design constraint.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from simu_shared.constants import EventType
from simu_shared.models import (
    AgentRegistration,
    AgentStatus,
    Incident,
    RoutedMessage,
    TapeEvent,
)

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class SendCommandRequest(BaseModel):
    text: str
    agent: str | None = None
    session_id: str | None = None


class CreateSessionRequest(BaseModel):
    pass


class SelectSessionRequest(BaseModel):
    session_id: str


class GenerateAgentRequest(BaseModel):
    display_name: str = ""
    role: str = ""
    description: str = ""


class AddGeneratedAgentRequest(BaseModel):
    agent_id: str
    config_path: str


class GroupMessageRequest(BaseModel):
    group_id: str
    message: str
    session_id: str | None = None


class GroupAgentRequest(BaseModel):
    group_id: str
    agent_id: str


class CreateGroupRequest(BaseModel):
    name: str
    agent_ids: list[str] = []


# ---------------------------------------------------------------------------
# Dependency — injected by app.py at startup
# ---------------------------------------------------------------------------

_deps: dict[str, Any] = {}


def set_dependencies(**kwargs: Any) -> None:
    _deps.update(kwargs)


def _get(name: str, default: Any = None) -> Any:
    return _deps.get(name, default)


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

@router.get("/sessions")
async def list_sessions() -> dict[str, Any]:
    sm = _get("session_manager")
    if sm is None:
        return {"current_session_id": "", "sessions": []}
    sessions = await sm.list_all()
    current = sessions[0] if sessions else None
    return {
        "current_session_id": current.session_id if current else "",
        "sessions": [
            {
                "session_id": s.session_id,
                "title": s.metadata.get("title", s.session_id),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                "event_count": 0,
                "agents": s.agent_ids,
                "is_current": s.session_id == (current.session_id if current else ""),
            }
            for s in sessions
        ],
    }


@router.post("/sessions")
async def create_session() -> dict[str, Any]:
    sm = _get("session_manager")
    if sm is None:
        return {"success": False, "error": "session_manager not available"}
    session = await sm.create()
    return {
        "success": True,
        "current_session_id": session.session_id,
        "session": {
            "session_id": session.session_id,
            "title": session.session_id,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            "event_count": 0,
            "agents": session.agent_ids,
            "is_current": True,
        },
    }


@router.post("/sessions/select")
async def select_session(req: SelectSessionRequest) -> dict[str, Any]:
    sm = _get("session_manager")
    if sm is None:
        return {"success": False, "error": "session_manager not available"}
    session = await sm.get(req.session_id)
    if session is None:
        return {"success": False, "error": "Session not found"}
    return {
        "success": True,
        "current_session_id": session.session_id,
        "session": {
            "session_id": session.session_id,
            "is_current": True,
        },
    }


# ---------------------------------------------------------------------------
# Commands / messages
# ---------------------------------------------------------------------------

@router.post("/command")
async def send_command(req: SendCommandRequest) -> dict[str, Any]:
    sm = _get("session_manager")
    router_svc = _get("event_router")
    msg_store = _get("message_store")
    queue = _get("queue_controller")

    # Resolve session
    session_id = req.session_id
    if not session_id:
        sessions = await sm.list_all()
        if sessions:
            session_id = sessions[0].session_id
        else:
            s = await sm.create()
            session_id = s.session_id

    # Build event
    dst = [f"agent:{req.agent}"] if req.agent else ["*"]
    event = TapeEvent(
        src="player",
        dst=dst,
        event_type=EventType.CHAT,
        payload={"content": req.text},
        session_id=session_id,
    )

    # Persist message for frontend
    msg = RoutedMessage(
        session_id=session_id,
        src="player",
        dst=dst,
        content=req.text,
        event_type=EventType.CHAT,
        origin_event_id=event.event_id,
    )
    await msg_store.store(msg)

    # Route to agents
    if req.agent:
        await queue.enqueue(req.agent, event)
    else:
        for agent_id in router_svc.connected_agents():
            await queue.enqueue(agent_id, event)

    # Push to WebSocket clients
    await _get("ws_manager").broadcast({"kind": "event", "data": event.model_dump(mode="json")})

    return {"event_id": event.event_id, "session_id": session_id}


# ---------------------------------------------------------------------------
# Game state
# ---------------------------------------------------------------------------

@router.get("/state")
async def get_state() -> dict[str, Any]:
    engine = _get("engine")
    if engine is None:
        return {"turn": 0, "state": {}, "incidents": []}
    state = engine.query_state()
    overview = engine.get_overview()
    incidents = engine.list_incidents()
    return {**overview, "state": state, "incidents": incidents}


@router.get("/overview")
async def get_overview() -> dict[str, Any]:
    engine = _get("engine")
    if engine is None:
        return {"turn": 0, "treasury": 0, "population": 0, "province_count": 0}
    raw = engine.get_overview()
    return {
        "turn": raw.get("turn", 0),
        "treasury": int(float(raw.get("imperial_treasury", 0))),
        "population": int(float(raw.get("total_population", 0))),
        "province_count": raw.get("province_count", 0),
    }


@router.post("/state/tick")
async def manual_tick() -> dict[str, Any]:
    engine = _get("engine")
    sm = _get("session_manager")
    sessions = await sm.list_all()
    session_id = sessions[0].session_id if sessions else "default"
    event = await engine.tick(session_id)
    await _get("event_router").broadcast(event)
    await _get("ws_manager").broadcast({"kind": "event", "data": event.model_dump(mode="json")})
    return {"turn": engine.state.nation.turn}


# ---------------------------------------------------------------------------
# Agent management
# ---------------------------------------------------------------------------

@router.get("/agents")
async def list_agents() -> list[dict[str, Any]]:
    registry = _get("agent_registry")
    if registry is None:
        return []
    agents = await registry.list_all()
    return [
        {
            "agent_id": a.agent_id,
            "agent_name": a.display_name or a.agent_id,
        }
        for a in agents
    ]


@router.post("/agents/generate")
async def generate_agent(req: GenerateAgentRequest) -> dict[str, Any]:
    task_id = await _get("agent_generator").generate(req.model_dump())
    return {"task_id": task_id}


@router.get("/agents/jobs/{task_id}")
async def get_generation_job(task_id: str) -> dict[str, Any]:
    return _get("agent_generator").get_status(task_id)


@router.post("/agents/add-generated")
async def add_generated_agent(req: AddGeneratedAgentRequest) -> dict[str, Any]:
    reg = AgentRegistration(
        agent_id=req.agent_id,
        config_path=req.config_path,
        status=AgentStatus.REGISTERED,
    )
    await _get("agent_registry").register(reg)
    pid = await _get("process_manager").spawn(reg)
    await _get("agent_registry").update_status(req.agent_id, AgentStatus.STARTING, pid)
    return {"agent_id": req.agent_id, "pid": pid}


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

@router.get("/incidents")
async def list_incidents() -> list[dict[str, Any]]:
    engine = _get("engine")
    if engine is None:
        return []
    return engine.list_incidents()


# ---------------------------------------------------------------------------
# Groups — preserves V4 API surface
# ---------------------------------------------------------------------------

@router.get("/groups")
async def list_groups() -> list[dict[str, Any]]:
    store = _get("group_store")
    if store is None:
        return []
    return store.list_all()


@router.post("/groups")
async def create_group(req: CreateGroupRequest) -> dict[str, Any]:
    store = _get("group_store")
    if store is None:
        return {"error": "group_store not available"}
    group = store.create(name=req.name, agent_ids=req.agent_ids)
    return group.to_dict()


@router.post("/groups/message")
async def send_group_message(req: GroupMessageRequest) -> dict[str, Any]:
    store = _get("group_store")
    if store is None:
        return {"error": "group_store not available"}
    agent_ids = store.record_message(req.group_id)
    if not agent_ids:
        return {"error": "Group not found"}

    # Broadcast message to each agent in the group
    queue = _get("queue_controller")
    session_id = req.session_id
    if not session_id:
        sm = _get("session_manager")
        sessions = await sm.list_all()
        session_id = sessions[0].session_id if sessions else None

    if session_id and queue:
        event = TapeEvent(
            src="player",
            dst=[f"agent:{aid}" for aid in agent_ids],
            event_type=EventType.CHAT,
            payload={"content": req.message},
            session_id=session_id,
        )
        for aid in agent_ids:
            await queue.enqueue(aid, event)

    return {"status": "sent", "agent_ids": agent_ids}


@router.post("/groups/add-agent")
async def add_agent_to_group(req: GroupAgentRequest) -> dict[str, Any]:
    store = _get("group_store")
    if store is None:
        return {"error": "group_store not available"}
    group = store.add_agent(req.group_id, req.agent_id)
    if group is None:
        return {"error": "Group not found"}
    return group.to_dict()


@router.post("/groups/remove-agent")
async def remove_agent_from_group(req: GroupAgentRequest) -> dict[str, Any]:
    store = _get("group_store")
    if store is None:
        return {"error": "group_store not available"}
    group = store.remove_agent(req.group_id, req.agent_id)
    if group is None:
        return {"error": "Group not found"}
    return group.to_dict()


# ---------------------------------------------------------------------------
# Tape query (proxied from V4 — returns messages from message_store)
# ---------------------------------------------------------------------------

@router.get("/tape/current")
async def get_current_tape() -> dict[str, Any]:
    sm = _get("session_manager")
    if sm is None:
        return {"session_id": "", "events": [], "total": 0}
    sessions = await sm.list_all()
    if not sessions:
        return {"session_id": "", "events": [], "total": 0}
    session = sessions[0]
    msg_store = _get("message_store")
    if msg_store is None:
        return {"session_id": session.session_id, "events": [], "total": 0}
    messages = await msg_store.query(session.session_id)
    events = [
        {
            "event_id": m.message_id,
            "src": m.src,
            "dst": m.dst,
            "type": m.event_type,
            "payload": {"content": m.content},
            "timestamp": m.timestamp.isoformat() if m.timestamp else "",
            "session_id": m.session_id,
        }
        for m in messages
    ]
    return {"session_id": session.session_id, "events": events, "total": len(events)}


@router.get("/tape/subsessions")
async def get_subsessions() -> list[dict[str, Any]]:
    sm = _get("session_manager")
    if sm is None:
        return []
    sessions = await sm.list_all()
    return [
        {
            "session_id": s.session_id,
            "parent_id": s.parent_id or "",
            "created_at": s.created_at.isoformat() if s.created_at else "",
            "updated_at": s.updated_at.isoformat() if s.updated_at else "",
            "event_count": 0,
            "depth": 1,
            "status": s.status.value if hasattr(s.status, "value") else str(s.status),
        }
        for s in sessions if s.is_task
    ]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# WebSocket for frontend real-time updates
# ---------------------------------------------------------------------------

class WSManager:
    """Manages WebSocket connections from frontend clients."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.remove(ws)

    async def broadcast(self, data: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)


ws_manager = WSManager()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws_manager.connect(ws)
    try:
        while True:
            data = await ws.receive_json()
            # Client can send commands via WS too
            if data.get("type") == "command":
                req = SendCommandRequest(
                    text=data.get("text", ""),
                    agent=data.get("agent"),
                    session_id=data.get("session_id"),
                )
                result = await send_command(req)
                await ws.send_json({"kind": "ack", "data": result})
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
