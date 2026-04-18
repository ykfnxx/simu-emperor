"""simu-mcp — Game interaction + communication MCP server.

Exposes MCP tools for:
- query_state: read game state
- create_incident: apply effects to game state (with permission checks)
- send_message: send messages to other agents / player
- create_task_session: create a sub-task session
- finish_task_session: complete or fail a task session
- push_tape_event: record tape events for observability
"""

from __future__ import annotations

import json
import logging
import uuid as _uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from simu_shared.constants import EventType
from simu_shared.models import Effect, Incident, RoutedMessage, SessionStatus, TapeEvent

from simu_server.mcp.auth import get_agent_id

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dependency injection (same pattern as routes/callback.py)
# ---------------------------------------------------------------------------

_deps: dict[str, Any] = {}


def set_dependencies(**kwargs: Any) -> None:
    _deps.update(kwargs)


def _get(name: str) -> Any:
    v = _deps.get(name)
    if v is None:
        raise RuntimeError(f"MCP dependency not set: {name}")
    return v


# ---------------------------------------------------------------------------
# FastMCP server instance
# ---------------------------------------------------------------------------

simu_mcp = FastMCP("simu-mcp")


# ---------------------------------------------------------------------------
# Tool: query_state
# ---------------------------------------------------------------------------


@simu_mcp.tool()
async def query_state(path: str = "") -> str:
    """Query the current game state.

    Use dot-notation paths to drill into specific data:
    - "" (empty) → full state snapshot
    - "nation" → nation-level data
    - "nation.imperial_treasury" → specific field
    - "provinces.zhili" → a single province
    - "provinces.zhili.production_value" → province field
    """
    get_agent_id()  # ensure authenticated
    engine = _get("engine")
    result = engine.query_state(path)
    return json.dumps(result, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Tool: send_message
# ---------------------------------------------------------------------------


@simu_mcp.tool()
async def send_message(
    recipients: list[str],
    message: str,
    session_id: str,
    await_reply: bool = False,
) -> str:
    """Send a message to other agents or the player.

    Args:
        recipients: List of target agent IDs (e.g. ["governor_zhili"]) or "player".
        message: The message content.
        session_id: The session this message belongs to.
        await_reply: If True, the caller expects to block until a reply arrives.
            The server records this intent; the agent-side state machine handles
            actual blocking via SSE events.

    Returns:
        JSON with event_id and await_reply flag. When await_reply=True, the
        agent should mark its session as BLOCKED and wait for a RESPONSE event.
    """
    agent_id = get_agent_id()
    msg_store = _get("message_store")
    queue = _get("queue_controller")
    ws_mgr = _get("ws_manager")

    dst = [f"agent:{r}" if r != "player" else r for r in recipients]
    event = TapeEvent(
        src=f"agent:{agent_id}",
        dst=dst,
        event_type=EventType.AGENT_MESSAGE,
        payload={"content": message},
        session_id=session_id,
    )

    msg = RoutedMessage(
        session_id=session_id,
        src=f"agent:{agent_id}",
        dst=dst,
        content=message,
        event_type=EventType.AGENT_MESSAGE,
        origin_event_id=event.event_id,
    )
    await msg_store.store(msg)

    for r in recipients:
        if r != "player":
            await queue.enqueue(r, event)

    agent_reg = await _get("agent_registry").get(agent_id)
    display_name = agent_reg.display_name if agent_reg else agent_id
    await ws_mgr.broadcast(
        {
            "kind": "chat",
            "data": {
                "agent": agent_id,
                "agentDisplayName": display_name,
                "text": message,
                "timestamp": event.timestamp.isoformat(),
                "session_id": session_id,
            },
        }
    )

    result: dict[str, Any] = {"event_id": event.event_id}
    if await_reply:
        result["await_reply"] = True
        result["awaiting_from"] = [f"agent:{r}" if r != "player" else r for r in recipients]
    return json.dumps(result)


# ---------------------------------------------------------------------------
# Tool: create_incident
# ---------------------------------------------------------------------------

_MAX_REMAINING_TICKS = 48  # 1 year


class EffectParam(BaseModel):
    """A single effect on a game state field."""

    target_path: str = Field(
        description=(
            "Dot-notation path, e.g. 'provinces.zhili.production_value' "
            "or 'nation.imperial_treasury'"
        ),
    )
    add: str | None = Field(
        default=None,
        description="Additive modifier as a decimal string, e.g. '100.5'",
    )
    factor: str | None = Field(
        default=None,
        description="Multiplicative modifier as a decimal string, e.g. '0.05' for +5%",
    )


@simu_mcp.tool()
async def create_incident(
    title: str,
    description: str,
    effects: list[EffectParam],
    remaining_ticks: int,
    source: str = "",
) -> str:
    """Create a game incident that modifies state over time.

    Each effect targets a specific field and applies either an additive
    (``add``) or multiplicative (``factor``) modifier.  Permission checks
    are enforced based on the agent's data_scope configuration.

    Args:
        title: Short incident title.
        description: Detailed description.
        effects: List of effects to apply.
        remaining_ticks: Duration in ticks (1-48, each tick = ~1 month).
        source: Optional source label (defaults to agent ID).

    Returns:
        JSON with incident_id and status, or error details.
    """
    agent_id = get_agent_id()
    engine = _get("engine")

    if engine is None:
        return json.dumps({"error": "Engine not initialized"})

    nation = engine.state.nation

    if remaining_ticks < 1 or remaining_ticks > _MAX_REMAINING_TICKS:
        return json.dumps({"error": f"remaining_ticks must be 1-{_MAX_REMAINING_TICKS}"})

    if not effects:
        return json.dumps({"error": "At least one effect is required"})

    scope = _load_data_scope(agent_id)
    if not scope:
        return json.dumps({"error": f"Agent {agent_id} has no data_scope configuration"})

    active_incidents = engine.incidents.active
    errors: list[str] = []
    for eff in effects:
        err = _validate_effect(eff, agent_id, scope, nation, active_incidents)
        if err:
            errors.append(err)

    if errors:
        return json.dumps({"error": "; ".join(errors)})

    # Build Effect objects — normalize nation-level paths
    nation_fields = {"imperial_treasury", "base_tax_rate", "tribute_rate", "fixed_expenditure"}
    built_effects = []
    for eff in effects:
        path = eff.target_path
        parts = path.split(".")
        if len(parts) == 1 and parts[0] in nation_fields:
            path = f"nation.{parts[0]}"
        kwargs: dict[str, Any] = {"target_path": path}
        if eff.add is not None:
            kwargs["add"] = Decimal(eff.add)
        if eff.factor is not None:
            kwargs["factor"] = Decimal(eff.factor)
        built_effects.append(Effect(**kwargs))

    incident = Incident(
        title=title,
        description=description,
        effects=built_effects,
        remaining_ticks=remaining_ticks,
        source=source or f"agent:{agent_id}",
    )
    await engine.add_incident(incident)

    logger.info(
        "Agent %s created incident '%s' (%d effects, %d ticks)",
        agent_id,
        title,
        len(built_effects),
        remaining_ticks,
    )
    return json.dumps({"incident_id": incident.incident_id, "status": "created"})


# ---------------------------------------------------------------------------
# Tool: create_task_session
# ---------------------------------------------------------------------------


@simu_mcp.tool()
async def create_task_session(
    parent_session_id: str,
    goal: str,
    description: str = "",
    constraints: str = "",
    timeout_seconds: int = 300,
    depth: int = 1,
) -> str:
    """Create a sub-task session for focused work within a parent session.

    Args:
        parent_session_id: The parent session to nest under.
        goal: What this task should accomplish.
        description: Detailed task description.
        constraints: Any constraints or limits.
        timeout_seconds: Maximum duration (default 300s).
        depth: Nesting depth (max 5).

    Returns:
        JSON with the new task_session_id.
    """
    agent_id = get_agent_id()
    sm = _get("session_manager")
    msg_store = _get("message_store")

    task_session_id = f"task:{_uuid.uuid4().hex[:12]}"
    await sm.create(
        created_by=f"agent:{agent_id}",
        parent_id=parent_session_id,
        session_id=task_session_id,
    )
    await sm.add_agent(task_session_id, agent_id)
    await sm.update_metadata(
        task_session_id,
        {
            "goal": goal,
            "description": description,
            "constraints": constraints,
            "timeout_seconds": timeout_seconds,
            "depth": depth,
            "created_by_agent": agent_id,
        },
    )

    task_event = RoutedMessage(
        session_id=task_session_id,
        src=f"agent:{agent_id}",
        dst=[f"agent:{agent_id}"],
        content=f"Task created: {goal}",
        event_type=EventType.TASK_CREATED,
    )
    await msg_store.store(task_event)

    logger.info(
        "Agent %s created task session %s (parent=%s, goal=%s)",
        agent_id,
        task_session_id,
        parent_session_id,
        goal,
    )
    return json.dumps({"task_session_id": task_session_id})


# ---------------------------------------------------------------------------
# Tool: finish_task_session
# ---------------------------------------------------------------------------


@simu_mcp.tool()
async def finish_task_session(
    task_session_id: str,
    parent_session_id: str,
    result: str,
    status: str = "completed",
) -> str:
    """Complete or fail a task session.

    Args:
        task_session_id: The task session to finish.
        parent_session_id: The parent session.
        result: Summary of task results.
        status: "completed" or "failed".

    Returns:
        JSON status.
    """
    agent_id = get_agent_id()
    sm = _get("session_manager")
    msg_store = _get("message_store")
    ws_mgr = _get("ws_manager")
    queue = _get("queue_controller")

    new_status = SessionStatus.COMPLETED if status == "completed" else SessionStatus.FAILED
    await sm.update_status(task_session_id, new_status)

    event_type = EventType.TASK_FINISHED if status == "completed" else EventType.TASK_FAILED
    finish_msg = RoutedMessage(
        session_id=parent_session_id,
        src=f"agent:{agent_id}",
        dst=[f"agent:{agent_id}"],
        content=result,
        event_type=event_type,
    )
    await msg_store.store(finish_msg)

    if queue:
        finish_event = TapeEvent(
            src=f"agent:{agent_id}",
            dst=[f"agent:{agent_id}"],
            event_type=event_type,
            payload={
                "content": result,
                "task_session_id": task_session_id,
                "status": status,
            },
            session_id=parent_session_id,
        )
        await queue.enqueue(agent_id, finish_event)

    await ws_mgr.broadcast(
        {
            "kind": "task_finished",
            "data": {
                "task_session_id": task_session_id,
                "parent_session_id": parent_session_id,
                "status": status,
                "result": result,
            },
        }
    )

    logger.info(
        "Agent %s finished task session %s (status=%s)",
        agent_id,
        task_session_id,
        status,
    )
    return json.dumps({"status": "ok"})


# ---------------------------------------------------------------------------
# Tool: push_tape_event
# ---------------------------------------------------------------------------


@simu_mcp.tool()
async def push_tape_event(
    event_id: str,
    session_id: str,
    src: str,
    dst: list[str],
    event_type: str,
    payload: dict,
    timestamp: str,
    parent_event_id: str | None = None,
    route: bool = False,
) -> str:
    """Record a tape event for observability.

    When ``route=True`` and event_type is RESPONSE, the event is also
    delivered to destination agents via the message queue.

    Returns:
        JSON status.
    """
    agent_id = get_agent_id()
    msg_store = _get("message_store")

    # Force src to authenticated agent to prevent identity spoofing
    src = f"agent:{agent_id}"

    content = payload.get("content", "")
    if not content:
        content = json.dumps(payload, ensure_ascii=False, default=str)

    msg = RoutedMessage(
        message_id=event_id,
        session_id=session_id,
        src=src,
        dst=dst,
        content=content,
        event_type=event_type,
        origin_event_id=parent_event_id,
    )
    await msg_store.store(msg)

    if route and event_type == EventType.RESPONSE:
        queue = _get("queue_controller")
        event = TapeEvent(
            event_id=event_id,
            src=src,
            dst=dst,
            event_type=event_type,
            payload=payload,
            session_id=session_id,
            parent_event_id=parent_event_id,
        )
        for d in dst:
            if d.startswith("agent:"):
                target_id = d.removeprefix("agent:")
                if target_id != agent_id:
                    await queue.enqueue(target_id, event)

    return json.dumps({"status": "ok"})


# ---------------------------------------------------------------------------
# Shared validation helpers (extracted from routes/callback.py)
# ---------------------------------------------------------------------------


def _load_data_scope(agent_id: str) -> dict[str, Any]:
    """Load data_scope.yaml for an agent.

    Handles both the flat format (provinces/fields/nation_fields at
    top level) and the legacy V4 format (nested under skills.query_data).
    """
    import yaml
    from simu_server.config import settings

    for base in (settings.default_agents_dir, settings.agents_dir):
        scope_path = base / agent_id / "data_scope.yaml"
        if scope_path.exists():
            raw = yaml.safe_load(scope_path.read_text(encoding="utf-8")) or {}
            if "provinces" in raw or "fields" in raw or "nation_fields" in raw:
                return raw
            query_data = raw.get("skills", {}).get("query_data", {})
            if query_data:
                return {
                    "display_name": raw.get("display_name", ""),
                    "provinces": query_data.get("provinces", []),
                    "fields": [f.split(".")[0] for f in query_data.get("fields", [])],
                    "nation_fields": query_data.get("national", []),
                }
            return raw
    return {}


def _validate_effect(
    effect: EffectParam,
    agent_id: str,
    scope: dict[str, Any],
    nation: Any,
    active_incidents: list[Any] | None = None,
) -> str | None:
    """Validate a single effect against data_scope and game limits.

    Returns an error message string, or None if valid.
    """
    parts = effect.target_path.split(".")

    # --- Parse target path ---
    if parts[0] == "provinces" and len(parts) == 3:
        province_id, field_name = parts[1], parts[2]
        allowed_provinces = scope.get("provinces", [])
        if allowed_provinces != "all" and province_id not in allowed_provinces:
            return f"权限不足：agent {agent_id} 无权修改省份 {province_id} 的数据"
        allowed_fields = scope.get("fields", [])
        if field_name not in allowed_fields:
            return f"字段不允许：{agent_id} 的 data_scope 不包含省份字段 {field_name}"
        province = nation.provinces.get(province_id)
        if province is None:
            return f"省份不存在：{province_id}"
        current = getattr(province, field_name, None)
        if current is None or not isinstance(current, Decimal):
            return f"字段无效：{field_name} 不是有效的数值字段"

    elif (len(parts) == 1) or (len(parts) == 2 and parts[0] == "nation"):
        field_name = parts[-1]
        allowed_nation_fields = scope.get("nation_fields", [])
        if field_name not in allowed_nation_fields:
            return f"字段不允许：{agent_id} 的 data_scope 不包含国家级别字段 {field_name}"
        current = getattr(nation, field_name, None)
        if current is None or not isinstance(current, Decimal):
            return f"字段无效：{field_name} 不是有效的国家级数值字段"
    else:
        return (
            f"target_path 格式错误：{effect.target_path}"
            f"（应为 'provinces.{{id}}.{{field}}' 或 'nation.{{field}}'）"
        )

    # --- Value validation ---
    if effect.add is not None and effect.factor is not None:
        return "Effect 必须只有 add 或 factor 之一，不能同时设置"
    if effect.add is None and effect.factor is None:
        return "Effect 必须设置 add 或 factor 之一"

    _allow_non_positive = {"tax_modifier", "base_production_growth", "base_population_growth"}

    nation_field_names = {
        "imperial_treasury",
        "base_tax_rate",
        "tribute_rate",
        "fixed_expenditure",
    }
    canonical_path = effect.target_path
    if len(parts) == 1 and parts[0] in nation_field_names:
        canonical_path = f"nation.{parts[0]}"

    existing_factors: list[Decimal] = []
    existing_unapplied_adds: list[Decimal] = []
    if active_incidents:
        for incident in active_incidents:
            for eff in incident.effects:
                if eff.target_path != canonical_path:
                    continue
                if eff.factor is not None:
                    existing_factors.append(eff.factor)
                if eff.add is not None and not incident.applied:
                    existing_unapplied_adds.append(eff.add)

    try:
        if effect.add is not None:
            add_val = Decimal(effect.add)
            simulated = current + sum(existing_unapplied_adds) + add_val
            if field_name not in _allow_non_positive and simulated <= 0:
                return (
                    f"数值溢出：add={effect.add} 会将 {effect.target_path} "
                    f"（当前值 {current}，已有未生效 add 合计 "
                    f"{sum(existing_unapplied_adds)}）减至 {simulated}（≤ 0）"
                )
        if effect.factor is not None:
            factor_val = Decimal(effect.factor)
            simulated = current
            for ef in existing_factors:
                simulated *= Decimal("1") + ef
            simulated *= Decimal("1") + factor_val
            if field_name not in _allow_non_positive and simulated <= 0:
                return (
                    f"数值溢出：factor={effect.factor} 叠加已有修改后会将 "
                    f"{effect.target_path}（当前值 {current}）变为 "
                    f"{simulated}（≤ 0）"
                )
    except InvalidOperation:
        return f"数值格式错误：add={effect.add}, factor={effect.factor}"

    return None
