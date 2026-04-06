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


class EffectRequest(BaseModel):
    target_path: str  # e.g. "provinces.zhili.production_value"
    add: str | None = None  # Decimal as string
    factor: str | None = None  # Decimal as string


class CreateIncidentRequest(BaseModel):
    title: str
    description: str = ""
    effects: list[EffectRequest]
    remaining_ticks: int
    source: str = ""  # auto-filled with agent id if empty


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


class TapeEventRequest(BaseModel):
    event_id: str
    session_id: str
    src: str
    dst: list[str]
    event_type: str
    payload: dict
    timestamp: str
    parent_event_id: str | None = None
    route: bool = False


@router.post("/tape-event")
async def push_tape_event(
    req: TapeEventRequest,
    x_agent_id: str = Header(...),
    x_callback_token: str = Header(...),
) -> dict[str, str]:
    """Receive internal tape events (TOOL_CALL, TOOL_RESULT, RESPONSE) from agents.

    When ``route=True`` and the event is a RESPONSE, the server also delivers
    the event to destination agents via the normal queue — enabling automatic
    agent-to-agent reply routing.
    """
    await _verify_agent(x_agent_id, x_callback_token)
    msg_store = _get("message_store")

    content = req.payload.get("content", "")
    if not content:
        content = json.dumps(req.payload, ensure_ascii=False, default=str)

    msg = RoutedMessage(
        message_id=req.event_id,
        session_id=req.session_id,
        src=req.src,
        dst=req.dst,
        content=content,
        event_type=req.event_type,
        origin_event_id=req.parent_event_id,
    )
    await msg_store.store(msg)

    # Route RESPONSE events to destination agents when requested
    if req.route and req.event_type == EventType.RESPONSE:
        queue = _get("queue_controller")
        if queue:
            event = TapeEvent(
                event_id=req.event_id,
                src=req.src,
                dst=req.dst,
                event_type=req.event_type,
                payload=req.payload,
                session_id=req.session_id,
                parent_event_id=req.parent_event_id,
            )
            for dst in req.dst:
                if dst.startswith("agent:"):
                    target_id = dst.removeprefix("agent:")
                    if target_id != x_agent_id:
                        await queue.enqueue(target_id, event)

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
    queue = _get("queue_controller")

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

    # Route the event to the parent agent so it can unblock the session
    if queue:
        finish_event = TapeEvent(
            src=f"agent:{x_agent_id}",
            dst=[f"agent:{x_agent_id}"],
            event_type=event_type,
            payload={
                "content": req.result,
                "task_session_id": req.task_session_id,
                "status": req.status,
            },
            session_id=req.parent_session_id,
        )
        await queue.enqueue(x_agent_id, finish_event)

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
# Incident creation
# ---------------------------------------------------------------------------

_MAX_REMAINING_TICKS = 48  # 1 year


def _load_data_scope(agent_id: str) -> dict[str, Any]:
    """Load and return the data_scope.yaml for an agent.

    Handles both the new flat format (provinces/fields/nation_fields at
    top level) and the legacy V4 format (nested under skills.query_data).
    Prefers default_agents_dir over agents_dir to ensure updates propagate.
    """
    import yaml
    from simu_server.config import settings

    # Prefer default_agents (always up-to-date) over runtime agents (may be stale)
    for base in (settings.default_agents_dir, settings.agents_dir):
        scope_path = base / agent_id / "data_scope.yaml"
        if scope_path.exists():
            raw = yaml.safe_load(scope_path.read_text(encoding="utf-8")) or {}
            # If it has top-level provinces/fields, it's the new format
            if "provinces" in raw or "fields" in raw or "nation_fields" in raw:
                return raw
            # Legacy format: extract from skills.query_data
            query_data = raw.get("skills", {}).get("query_data", {})
            if query_data:
                return {
                    "display_name": raw.get("display_name", ""),
                    "provinces": query_data.get("provinces", []),
                    "fields": [
                        f.split(".")[0] for f in query_data.get("fields", [])
                    ],
                    "nation_fields": query_data.get("national", []),
                }
            return raw
    return {}


def _validate_effect(
    effect: EffectRequest,
    agent_id: str,
    scope: dict[str, Any],
    nation: Any,
) -> str | None:
    """Validate a single effect against data_scope and limits.

    Returns an error message string, or None if valid.
    """
    from decimal import Decimal, InvalidOperation

    parts = effect.target_path.split(".")

    # --- Parse target path ---
    if parts[0] == "provinces" and len(parts) == 3:
        province_id, field_name = parts[1], parts[2]

        # Province permission check
        allowed_provinces = scope.get("provinces", [])
        if allowed_provinces != "all" and province_id not in allowed_provinces:
            return f"权限不足：agent {agent_id} 无权修改省份 {province_id} 的数据"

        # Field permission check
        allowed_fields = scope.get("fields", [])
        if field_name not in allowed_fields:
            return f"字段不允许：{agent_id} 的 data_scope 不包含省份字段 {field_name}"

        # Get current value for validation
        province = nation.provinces.get(province_id)
        if province is None:
            return f"省份不存在：{province_id}"
        current = getattr(province, field_name, None)
        if current is None or not isinstance(current, Decimal):
            return f"字段无效：{field_name} 不是有效的数值字段"

    elif (len(parts) == 1) or (len(parts) == 2 and parts[0] == "nation"):
        field_name = parts[-1]  # handles both "{field}" and "nation.{field}"

        # Nation field permission check
        allowed_nation_fields = scope.get("nation_fields", [])
        if field_name not in allowed_nation_fields:
            return f"字段不允许：{agent_id} 的 data_scope 不包含国家级别字段 {field_name}"

        current = getattr(nation, field_name, None)
        if current is None or not isinstance(current, Decimal):
            return f"字段无效：{field_name} 不是有效的国家级数值字段"

    else:
        return f"target_path 格式错误：{effect.target_path}（应为 'provinces.{{id}}.{{field}}' 或 'nation.{{field}}'）"

    # --- Value validation ---
    if effect.add is not None and effect.factor is not None:
        return "Effect 必须只有 add 或 factor 之一，不能同时设置"
    if effect.add is None and effect.factor is None:
        return "Effect 必须设置 add 或 factor 之一"

    try:
        if effect.add is not None:
            add_val = Decimal(effect.add)
            # Negative add cannot reduce field to 0 or below
            if add_val < 0 and current + add_val <= 0:
                return (
                    f"数值溢出：add={effect.add} 会将 {effect.target_path} "
                    f"（当前值 {current}）减至 0 或以下"
                )
        if effect.factor is not None:
            factor_val = Decimal(effect.factor)
            if factor_val < 0:
                return f"factor 不能为负数：{effect.factor}"
    except InvalidOperation:
        return f"数值格式错误：add={effect.add}, factor={effect.factor}"

    return None


@router.post("/incident")
async def create_incident(
    req: CreateIncidentRequest,
    x_agent_id: str = Header(...),
    x_callback_token: str = Header(...),
) -> dict[str, Any]:
    """Create a new incident with data_scope permission checks."""
    from decimal import Decimal

    from simu_shared.models import Effect, Incident

    await _verify_agent(x_agent_id, x_callback_token)

    engine = _get("engine")
    if engine is None:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    nation = engine.state.nation

    # Validate remaining_ticks
    if req.remaining_ticks < 1 or req.remaining_ticks > _MAX_REMAINING_TICKS:
        raise HTTPException(
            status_code=400,
            detail=f"remaining_ticks 必须在 1-{_MAX_REMAINING_TICKS} 之间",
        )

    if not req.effects:
        raise HTTPException(status_code=400, detail="至少需要一个 effect")

    # Load data scope
    scope = _load_data_scope(x_agent_id)
    if not scope:
        raise HTTPException(
            status_code=403,
            detail=f"Agent {x_agent_id} 没有 data_scope 配置",
        )

    # Validate each effect
    errors: list[str] = []
    for eff in req.effects:
        err = _validate_effect(eff, x_agent_id, scope, nation)
        if err:
            errors.append(err)

    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    # Build and add incident
    # Nation-level fields need "nation." prefix for the engine's path parser
    nation_fields = {"imperial_treasury", "base_tax_rate", "tribute_rate", "fixed_expenditure"}
    effects = []
    for eff in req.effects:
        path = eff.target_path
        parts = path.split(".")
        if len(parts) == 1 and parts[0] in nation_fields:
            path = f"nation.{parts[0]}"
        kwargs: dict[str, Any] = {"target_path": path}
        if eff.add is not None:
            kwargs["add"] = Decimal(eff.add)
        if eff.factor is not None:
            kwargs["factor"] = Decimal(eff.factor)
        effects.append(Effect(**kwargs))

    incident = Incident(
        title=req.title,
        description=req.description,
        effects=effects,
        remaining_ticks=req.remaining_ticks,
        source=req.source or f"agent:{x_agent_id}",
    )
    engine.add_incident(incident)

    logger.info(
        "Agent %s created incident '%s' (%d effects, %d ticks)",
        x_agent_id, req.title, len(effects), req.remaining_ticks,
    )
    return {"incident_id": incident.incident_id, "status": "created"}


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
