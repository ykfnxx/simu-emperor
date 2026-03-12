"""FastAPI 服务器 (V4 - 应用层集成)

提供 WebSocket 实时通信和 REST API 端点。
V4重构：所有业务逻辑委托给ApplicationServices，本模块仅处理协议转换。
"""

from contextlib import asynccontextmanager
import logging
import os
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from simu_emperor.common import DEFAULT_WEB_SESSION_ID, strip_agent_prefix
from simu_emperor.config import settings
from simu_emperor.event_bus.event import Event
from simu_emperor.adapters.web.game_instance import WebGameInstance
from simu_emperor.adapters.web.connection_manager import ConnectionManager
from simu_emperor.adapters.web.message_converter import MessageConverter


logger = logging.getLogger(__name__)

# 全局单例
game_instance = WebGameInstance(settings)
connection_manager = ConnectionManager()
message_converter = MessageConverter()

# ============================================================================
# Validation Helpers (协议层校验)
# ============================================================================


def _validate_agent_id(
    agent_id: str | None,
    *,
    required: bool,
    field_name: str,
) -> str | None:
    """校验 agent_id 非空且格式正确。"""
    if agent_id is None:
        if required:
            raise ValueError(f"{field_name} is required")
        return None

    normalized = strip_agent_prefix(agent_id)
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized


def _validate_session_id(session_id: str | None, *, required: bool) -> str | None:
    """校验 session_id 格式。"""
    if session_id is None:
        if required:
            raise ValueError("session_id is required")
        return None

    normalized = session_id.strip()
    if not normalized:
        raise ValueError("session_id cannot be empty")
    return normalized


def _validate_text(value: Any, *, field_name: str) -> str:
    """校验文本字段是字符串。"""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


async def _send_ws_error(websocket: WebSocket, message: str) -> None:
    """向当前 WebSocket 返回参数校验错误。"""
    await connection_manager.send_personal(
        {"kind": "error", "data": {"message": message}},
        websocket,
    )


# FastAPI 应用
@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期管理。"""
    logger.info("Starting FastAPI server...")
    await game_instance.start()

    global message_converter
    message_converter = MessageConverter(repository=game_instance.repository)

    if game_instance.event_bus:
        game_instance.event_bus.subscribe("*", _on_event)

    logger.info("FastAPI server started")
    try:
        yield
    finally:
        logger.info("Shutting down FastAPI server...")
        await game_instance.shutdown()
        logger.info("FastAPI server shut down")


app = FastAPI(title="Emperor Simulator Web API", lifespan=lifespan)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# WebSocket Endpoint
# ============================================================================


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 端点

    消息格式（客户端 → 服务器）:
    {
        "type": "command" | "chat",
        "agent": "governor_zhili",
        "text": "查看直隶省情况"
    }

    消息格式（服务器 → 客户端）:
    {
        "kind": "chat" | "state" | "event" | "error",
        "data": {...}
    }
    """
    await connection_manager.connect(websocket)

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_json()
            await handle_client_message(data, websocket)

    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await connection_manager.disconnect(websocket)


async def handle_client_message(data: dict, websocket: WebSocket) -> None:
    """
    处理客户端消息

    Args:
        data: 客户端发送的消息
        websocket: WebSocket 连接
    """
    msg_type = data.get("type")

    if msg_type in ("command", "chat"):
        try:
            agent = _validate_agent_id(data.get("agent"), required=True, field_name="agent")
            text = _validate_text(data.get("text", ""), field_name="text").strip()
            session_id = _validate_session_id(data.get("session_id"), required=False)

            if not text:
                raise ValueError("text cannot be empty")

            # 委托给 MessageService
            target_session_id = session_id or DEFAULT_WEB_SESSION_ID

            # 添加调试日志
            logger.info(
                f"[WS] Received {msg_type}: agent={agent}, session={target_session_id}, text={text[:50]}..."
            )

            if msg_type == "command":
                await game_instance.message_service.send_command(
                    agent_id=agent,
                    command=text,
                    session_id=target_session_id,
                )
            else:
                await game_instance.message_service.send_chat(
                    agent_id=agent,
                    message=text,
                    session_id=target_session_id,
                )

            logger.info(f"[WS] Message published to event bus: agent={agent}, session={target_session_id}")

        except ValueError as exc:
            logger.warning("Invalid message payload: %s", exc)
            await _send_ws_error(websocket, str(exc))
    else:
        await _send_ws_error(websocket, f"Unknown message type: {msg_type}")


async def _on_event(event: Event) -> None:
    """
    EventBus 事件回调（广播给所有 WebSocket 客户端）

    Args:
        event: EventBus 事件
    """
    # 转换为 WSMessage
    ws_message = await message_converter.convert(event)

    if ws_message:
        await connection_manager.broadcast(ws_message)


# ============================================================================
# REST API (协议转换层 - 委托给ApplicationServices)
# ============================================================================

class CommandRequest(BaseModel):
    """命令请求"""
    agent: str
    command: str


class SessionCreateRequest(BaseModel):
    """新建 session 请求"""
    name: str | None = None
    agent_id: str | None = None


class SessionSelectRequest(BaseModel):
    """选择 session 请求"""
    session_id: str
    agent_id: str | None = None


class GroupChatCreateRequest(BaseModel):
    """创建群聊请求"""
    name: str
    agent_ids: list[str]


class GroupChatMessageRequest(BaseModel):
    """群聊消息请求"""
    group_id: str
    message: str


class GroupChatAgentRequest(BaseModel):
    """群聊agent操作请求"""
    group_id: str
    agent_id: str


# ============================================================================
# Game State API
# ============================================================================


@app.post("/api/command")
async def send_command(cmd: CommandRequest):
    """发送命令到游戏"""
    try:
        await game_instance.message_service.send_command(
            agent_id=cmd.agent,
            command=cmd.command,
            session_id=DEFAULT_WEB_SESSION_ID,
        )
        return {"success": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/state")
async def get_state():
    """查询当前游戏状态"""
    if not game_instance.repository:
        raise HTTPException(status_code=503, detail="Game not initialized")

    state = await game_instance.repository.load_state()
    if state is None:
        return {}
    if isinstance(state, dict):
        return state
    else:
        return state.dict()


@app.get("/api/overview")
async def get_overview():
    """查询帝国概况"""
    return await game_instance.game_service.get_overview()


# ============================================================================
# Session API
# ============================================================================


@app.get("/api/sessions")
async def list_sessions_api():
    """列出所有 session"""
    if not game_instance.is_running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    sessions = await game_instance.session_service.list_sessions()
    agent_sessions = await game_instance.session_service.list_agent_sessions()
    return {
        "sessions": sessions,
        "agent_sessions": agent_sessions,
    }


@app.post("/api/sessions")
async def create_session(request: SessionCreateRequest):
    """新建 session 并切换为当前 session"""
    if not game_instance.is_running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    session = await game_instance.session_service.create_session(
        name=request.name,
        agent_id=request.agent_id,
    )
    return {
        "success": True,
        "session": session,
        "current_session_id": session.get("session_id"),
        "current_agent_id": session.get("agent_id"),
    }


@app.post("/api/sessions/select")
async def select_session(request: SessionSelectRequest):
    """选择当前 session"""
    if not game_instance.is_running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    try:
        session = await game_instance.session_service.select_session(
            session_id=request.session_id,
            agent_id=request.agent_id,
        )
        return {
            "success": True,
            "session": session,
            "current_session_id": session.get("session_id") or request.session_id,
            "current_agent_id": session.get("agent_id") or request.agent_id,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ============================================================================
# Tape API
# ============================================================================


@app.get("/api/tape/current")
async def get_current_tape(
    limit: int = 100,
    agent_id: str | None = None,
    session_id: str | None = None,
    include_sub_sessions: str | None = None,
):
    """查询当前 session 的 tape 事件"""
    safe_limit = max(1, min(limit, 500))

    # 解析子session列表
    sub_sessions = None
    if include_sub_sessions:
        sub_sessions = [s.strip() for s in include_sub_sessions.split(",") if s.strip()]

    if sub_sessions:
        return await game_instance.tape_service.get_tape_with_subs(
            limit=safe_limit,
            agent_id=agent_id,
            session_id=session_id,
            sub_sessions=sub_sessions,
        )

    return await game_instance.tape_service.get_current_tape(
        limit=safe_limit,
        agent_id=agent_id,
        session_id=session_id,
    )


@app.get("/api/tape/subsessions")
async def get_sub_sessions(
    session_id: str,
    agent_id: str | None = None,
):
    """获取指定主会话的所有子session列表"""
    if not game_instance.is_running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    return await game_instance.tape_service.get_sub_sessions(session_id, agent_id)


# ============================================================================
# Agent API
# ============================================================================


@app.get("/api/agents")
async def list_agents():
    """列出所有活跃 agents"""
    if not game_instance.is_running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    return await game_instance.agent_service.get_available_agents()


# ============================================================================
# Group Chat API
# ============================================================================


@app.get("/api/groups")
async def list_groups():
    """列出所有群聊"""
    if not game_instance.is_running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    return await game_instance.group_chat_service.list_group_chats()


@app.post("/api/groups")
async def create_group(request: GroupChatCreateRequest):
    """创建群聊"""
    if not game_instance.is_running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    group = await game_instance.group_chat_service.create_group_chat(
        name=request.name,
        agent_ids=request.agent_ids,
        session_id=DEFAULT_WEB_SESSION_ID,
    )
    return group.to_dict()


@app.post("/api/groups/message")
async def send_group_message(request: GroupChatMessageRequest):
    """向群聊发送消息"""
    if not game_instance.is_running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    try:
        sent_agents = await game_instance.group_chat_service.send_to_group_chat(
            group_id=request.group_id,
            message=request.message,
        )
        return {
            "success": True,
            "sent_agents": sent_agents,
            "count": len(sent_agents),
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/groups/add-agent")
async def add_group_agent(request: GroupChatAgentRequest):
    """向群聊添加agent"""
    if not game_instance.is_running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    try:
        await game_instance.group_chat_service.add_agent_to_group(
            group_id=request.group_id,
            agent_id=request.agent_id,
        )
        return {"success": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/groups/remove-agent")
async def remove_group_agent(request: GroupChatAgentRequest):
    """从群聊移除agent"""
    if not game_instance.is_running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    try:
        await game_instance.group_chat_service.remove_agent_from_group(
            group_id=request.group_id,
            agent_id=request.agent_id,
        )
        return {"success": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ============================================================================
# Health Check
# ============================================================================


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "running" if game_instance.is_running else "stopped",
        "connections": connection_manager.connection_count,
    }


# ============================================================================
# Static Files (Production)
# ============================================================================

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    logger.info(f"Static files mounted from: {static_dir}")
else:
    logger.info(f"Static files directory not found: {static_dir}")
