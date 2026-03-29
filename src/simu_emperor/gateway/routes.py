import asyncio
import json
import logging
from uuid import uuid4
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, APIRouter
from fastapi.responses import JSONResponse

from pydantic import BaseModel
from typing import Optional, Any
from simu_emperor.mq.dealer import MQDealer
from simu_emperor.mq.event import Event
from simu_emperor.mq.subscriber import MQSubscriber
from simu_emperor.gateway.ws_handler import WebSocketHandler
from simu_emperor.gateway.frontend_adapter import (
    event_to_frontend,
    frontend_to_event,
    format_health_response,
    format_agents_response,
    format_state_response,
)


logger = logging.getLogger(__name__)
router = APIRouter()


class SessionCreateRequest(BaseModel):
    name: Optional[str] = None
    agent_id: Optional[str] = None


class SessionSelectRequest(BaseModel):
    session_id: str
    agent_id: Optional[str] = None


class GroupCreateRequest(BaseModel):
    name: str
    agent_ids: list[str]


class GroupMessageRequest(BaseModel):
    group_id: str
    message: str


class GroupAgentRequest(BaseModel):
    group_id: str
    agent_id: str


class AgentAddRequest(BaseModel):
    agent_id: str
    title: str
    name: str
    duty: str
    personality: str
    province: Optional[str] = None


@router.get("/health")
async def health(gateway: Any = None):
    if gateway is None:
        return {"status": "stopped", "connections": 0}
    return format_health_response(
        connected=gateway._running if gateway else False,
        client_count=gateway.ws_handler.get_client_count() if gateway and gateway.ws_handler else 0,
    )


@router.get("/agents", response_model=None)
async def list_agents(agent_config_repo: Optional[Any] = None):
    if agent_config_repo is None:
        return {"agents": []}
    agents = await agent_config_repo.get_all()
    return format_agents_response(agents)


@router.get("/state", response_model=None)
async def get_state(game_state_repo: Optional[Any] = None):
    if game_state_repo is None:
        return {"turn": 0, "imperial_treasury": 0, "provinces": {}}
    tick = await game_state_repo.get_tick()
    treasury = await game_state_repo.get_national_treasury()
    return {
        "turn": tick,
        "imperial_treasury": treasury.get("total_silver", 0) if treasury else 0,
        "base_tax_rate": treasury.get("base_tax_rate", 0.1) if treasury else 0.1,
        "tribute_rate": treasury.get("tribute_rate", 0.8) if treasury else 0.8,
        "fixed_expenditure": treasury.get("fixed_expenditure", 0) if treasury else 0,
        "provinces": {},
    }


@router.get("/overview", response_model=None)
async def get_overview(game_state_repo: Optional[Any] = None):
    if game_state_repo is None:
        return {"turn": 0, "treasury": 0, "population": 0, "province_count": 0}
    tick = await game_state_repo.get_tick()
    treasury = await game_state_repo.get_national_treasury()
    return {
        "turn": tick,
        "treasury": treasury.get("total_silver", 0) if treasury else 0,
        "population": 0,
        "province_count": 0,
    }


@router.get("/incidents")
async def get_incidents():
    return []


@router.get("/sessions")
async def get_sessions():
    return {
        "current_session_id": "default",
        "sessions": [],
    }


@router.post("/sessions")
async def create_session(request: SessionCreateRequest):
    session_id = f"session:{uuid4().hex[:8]}"
    return {
        "success": True,
        "current_session_id": session_id,
        "session": {
            "session_id": session_id,
            "title": request.name or "New Session",
            "created_at": None,
            "updated_at": None,
            "event_count": 0,
            "agents": [],
            "is_current": True,
        },
    }


@router.post("/sessions/select")
async def select_session(request: SessionSelectRequest):
    return {
        "success": True,
        "current_session_id": request.session_id,
        "session": {
            "session_id": request.session_id,
            "is_current": True,
            "agent_id": request.agent_id,
        },
    }


@router.get("/tape/current")
async def get_current_tape(
    limit: int = 100,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None,
    include_sub_sessions: Optional[str] = None,
):
    return {
        "session_id": session_id or "default",
        "events": [],
        "total": 0,
    }


@router.get("/tape/subsessions")
async def get_subsessions(
    session_id: str,
    agent_id: Optional[str] = None,
):
    return []


@router.get("/groups")
async def get_groups():
    return []


@router.post("/groups")
async def create_group(request: GroupCreateRequest):
    return {
        "group_id": f"group:{uuid4().hex[:8]}",
        "name": request.name,
        "agent_ids": request.agent_ids,
        "created_at": "",
        "session_id": "",
        "message_count": 0,
    }


@router.post("/groups/message")
async def send_group_message(request: GroupMessageRequest):
    return {"success": True, "sent_agents": [], "count": 0}


@router.post("/groups/add-agent")
async def add_group_agent(request: GroupAgentRequest):
    return {"success": True}


@router.post("/groups/remove-agent")
async def remove_group_agent(request: GroupAgentRequest):
    return {"success": True}


@router.post("/agents/add-generated")
async def add_agent(request: AgentAddRequest):
    return {
        "success": True,
        "task_id": f"task:{uuid4().hex[:8]}",
        "agent_id": request.agent_id,
        "status": "pending",
        "message": "Agent creation started",
    }


@router.get("/agents/jobs/{task_id}")
async def get_agent_job_status(task_id: str):
    return {
        "task_id": task_id,
        "name": "Agent Creation",
        "status": "completed",
        "created_at": "",
        "started_at": None,
        "completed_at": None,
        "error": None,
        "result": None,
        "progress": 100,
    }
