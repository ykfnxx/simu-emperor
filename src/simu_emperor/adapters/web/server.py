"""
FastAPI 服务器

提供 WebSocket 实时通信和 REST API 端点。
"""

from contextlib import asynccontextmanager
import logging
import os
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from simu_emperor.config import settings
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.adapters.web.game_instance import WebGameInstance
from simu_emperor.adapters.web.connection_manager import ConnectionManager
from simu_emperor.adapters.web.message_converter import MessageConverter


logger = logging.getLogger(__name__)

# 全局单例
game_instance = WebGameInstance(settings)
connection_manager = ConnectionManager()
message_converter = MessageConverter()

# ============================================================================
# Validation Helpers
# ============================================================================


def _normalize_agent_id(agent_id: str) -> str:
    """规范化 agent_id，兼容 agent: 前缀。"""
    normalized = agent_id.strip()
    if normalized.startswith("agent:"):
        return normalized.replace("agent:", "", 1)
    return normalized


def _validate_agent_id(
    agent_id: str | None,
    *,
    required: bool,
    field_name: str,
) -> str | None:
    """校验 agent_id 非空且存在。"""
    if agent_id is None:
        if required:
            raise ValueError(f"{field_name} is required")
        return None

    normalized = _normalize_agent_id(agent_id)
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")

    available_agents = {
        _normalize_agent_id(agent) for agent in game_instance.get_available_agents()
    }
    if normalized not in available_agents:
        raise ValueError(f"Unknown agent: {normalized}")

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
    if not normalized.startswith("session:web:"):
        raise ValueError(f"Invalid session_id format: {normalized}")
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

    if msg_type == "command":
        try:
            await handle_command(data)
        except ValueError as exc:
            logger.warning("Invalid command payload: %s", exc)
            await _send_ws_error(websocket, str(exc))
    elif msg_type == "chat":
        try:
            await handle_chat(data)
        except ValueError as exc:
            logger.warning("Invalid chat payload: %s", exc)
            await _send_ws_error(websocket, str(exc))
    else:
        await _send_ws_error(websocket, f"Unknown message type: {msg_type}")


async def handle_command(data: dict) -> None:
    """处理命令消息 - 转换为 CHAT 事件"""
    agent = _validate_agent_id(data.get("agent"), required=True, field_name="agent")
    command = _validate_text(data.get("text", ""), field_name="text").strip()
    session_id = _validate_session_id(data.get("session_id"), required=False)
    if not command:
        raise ValueError("text cannot be empty")

    target_session_id = session_id or game_instance.get_session_for_agent(agent)
    game_instance.set_current_context(agent, target_session_id)

    event = Event(
        src="player:web",
        dst=[f"agent:{agent}"],
        type=EventType.CHAT,
        payload={"message": command},
        session_id=target_session_id,
    )

    if game_instance.event_bus:
        await game_instance.event_bus.send_event(event)
    else:
        raise ValueError("Game not initialized")


async def handle_chat(data: dict) -> None:
    """处理聊天消息"""
    agent = _validate_agent_id(data.get("agent"), required=True, field_name="agent")
    text = _validate_text(data.get("text", ""), field_name="text").strip()
    session_id = _validate_session_id(data.get("session_id"), required=False)
    if not text:
        raise ValueError("text cannot be empty")

    target_session_id = session_id or game_instance.get_session_for_agent(agent)
    game_instance.set_current_context(agent, target_session_id)

    event = Event(
        src="player:web",
        dst=[f"agent:{agent}"],
        type=EventType.CHAT,
        payload={"message": text},
        session_id=target_session_id,
    )

    if game_instance.event_bus:
        await game_instance.event_bus.send_event(event)
    else:
        raise ValueError("Game not initialized")


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
# REST API
# ============================================================================


class CommandRequest(BaseModel):
    """命令请求"""

    agent: str
    command: str

    @field_validator("agent")
    @classmethod
    def _validate_agent(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("agent cannot be empty")
        return normalized

    @field_validator("command")
    @classmethod
    def _validate_command(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("command cannot be empty")
        return normalized


class SessionCreateRequest(BaseModel):
    """新建 session 请求"""

    name: str | None = None
    agent_id: str | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Session name cannot be empty")
        return normalized

    @field_validator("agent_id")
    @classmethod
    def _validate_agent_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("agent_id cannot be empty")
        return normalized


class SessionSelectRequest(BaseModel):
    """选择 session 请求"""

    session_id: str
    agent_id: str | None = None

    @field_validator("session_id")
    @classmethod
    def _validate_session_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("session_id cannot be empty")
        return normalized

    @field_validator("agent_id")
    @classmethod
    def _validate_agent_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("agent_id cannot be empty")
        return normalized


class GroupChatCreateRequest(BaseModel):
    """创建群聊请求"""

    name: str
    agent_ids: list[str]

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("群聊名称不能为空")
        return normalized

    @field_validator("agent_ids")
    @classmethod
    def _validate_agent_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("至少需要选择一个agent")
        normalized = [agent.strip() for agent in value if agent.strip()]
        if len(normalized) < 1:
            raise ValueError("至少需要选择一个agent")
        return normalized


class GroupChatMessageRequest(BaseModel):
    """群聊消息请求"""

    group_id: str
    message: str

    @field_validator("group_id")
    @classmethod
    def _validate_group_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("group_id不能为空")
        return normalized

    @field_validator("message")
    @classmethod
    def _validate_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("消息内容不能为空")
        return normalized


class GroupChatAgentRequest(BaseModel):
    """群聊agent操作请求"""

    group_id: str
    agent_id: str

    @field_validator("group_id")
    @classmethod
    def _validate_group_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("group_id不能为空")
        return normalized

    @field_validator("agent_id")
    @classmethod
    def _validate_agent_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("agent_id不能为空")
        return normalized


@app.post("/api/command")
async def send_command(cmd: CommandRequest):
    """发送命令到游戏 - 转换为 CHAT 事件"""
    try:
        agent = _validate_agent_id(cmd.agent, required=True, field_name="agent")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    event = Event(
        src="player:web",
        dst=[f"agent:{agent}"],
        type=EventType.CHAT,
        payload={"message": cmd.command.strip()},
        session_id=game_instance.session_id,
    )

    if game_instance.event_bus:
        await game_instance.event_bus.send_event(event)
        return {"success": True}
    else:
        raise HTTPException(status_code=503, detail="Game not initialized")


@app.get("/api/state")
async def get_state():
    """
    查询当前游戏状态

    Returns:
        GameState (JSON)
    """
    if not game_instance.repository:
        raise HTTPException(status_code=503, detail="Game not initialized")

    state = await game_instance.repository.load_state()
    if state is None:
        return {}
    # state 可能是 Pydantic 模型或 dict
    if isinstance(state, dict):
        return state
    else:
        return state.dict()


@app.get("/api/overview")
async def get_overview():
    """
    查询帝国概况（前端右侧状态面板）。
    """
    return await game_instance.get_empire_overview()


@app.get("/api/sessions")
async def list_sessions_api():
    """
    列出所有 session，并返回当前选中 session。
    """
    sessions = await game_instance.list_sessions()
    agent_sessions = await game_instance.list_agent_sessions()
    return {
        "current_session_id": game_instance.session_id,
        "current_agent_id": game_instance.current_agent_id,
        "sessions": sessions,
        "agent_sessions": agent_sessions,
    }


@app.post("/api/sessions")
async def create_session(request: SessionCreateRequest):
    """
    新建 session 并切换为当前 session。
    """
    try:
        agent_id = _validate_agent_id(request.agent_id, required=False, field_name="agent_id")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session = await game_instance.create_session(request.name, agent_id=agent_id)
    return {
        "success": True,
        "current_session_id": game_instance.session_id,
        "current_agent_id": game_instance.current_agent_id,
        "session": session,
    }


@app.post("/api/sessions/select")
async def select_session(request: SessionSelectRequest):
    """
    选择当前 session。
    """
    try:
        validated_session_id = _validate_session_id(request.session_id, required=True)
        validated_agent_id = _validate_agent_id(
            request.agent_id, required=False, field_name="agent_id"
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        session = await game_instance.select_session(
            validated_session_id,
            agent_id=validated_agent_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "success": True,
        "current_session_id": game_instance.session_id,
        "current_agent_id": game_instance.current_agent_id,
        "session": session,
    }


@app.get("/api/tape/current")
async def get_current_tape(
    limit: int = 100,
    agent_id: str | None = None,
    session_id: str | None = None,
    include_sub_sessions: str | None = None,
):
    """
    查询当前 session 的 tape 事件。

    Args:
        limit: 事件数量限制
        agent_id: agent ID
        session_id: session ID
        include_sub_sessions: 要包含的子session ID列表（逗号分隔）
    """
    try:
        validated_agent_id = _validate_agent_id(agent_id, required=False, field_name="agent_id")
        validated_session_id = _validate_session_id(session_id, required=False)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    safe_limit = max(1, min(limit, 500))

    # 解析子session列表
    sub_sessions = None
    if include_sub_sessions:
        sub_sessions = [s.strip() for s in include_sub_sessions.split(",") if s.strip()]

    if sub_sessions:
        return await game_instance.get_tape_with_subs(
            limit=safe_limit,
            agent_id=validated_agent_id,
            session_id=validated_session_id,
            include_sub_sessions=sub_sessions,
        )

    return await game_instance.get_current_tape(
        limit=safe_limit,
        agent_id=validated_agent_id,
        session_id=validated_session_id,
    )


@app.get("/api/tape/subsessions")
async def get_sub_sessions(
    session_id: str,
    agent_id: str | None = None,
):
    """
    获取指定主会话的所有子session列表

    Args:
        session_id: 父会话ID
        agent_id: 可选，筛选特定agent的子会话

    Returns:
        子会话列表
    """
    if not game_instance._running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    return await game_instance.get_sub_sessions(session_id, agent_id)


@app.get("/api/agents")
async def list_agents():
    """
    列出所有活跃 agents

    Returns:
        ["governor_zhili", "minister_of_revenue", ...]
    """
    if not game_instance._running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    return game_instance.get_available_agents()


# ============================================================================
# Group Chat API
# ============================================================================


@app.get("/api/groups")
async def list_groups():
    """
    列出所有群聊

    Returns:
        群聊列表，每个群聊包含group_id, name, agent_ids等信息
    """
    if not game_instance._running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    return await game_instance.list_group_chats()


@app.post("/api/groups")
async def create_group(request: GroupChatCreateRequest):
    """
    创建群聊

    Args:
        request: 群聊创建请求（name, agent_ids）

    Returns:
        创建的群聊信息
    """
    if not game_instance._running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    # 验证所有agent都可用
    available_agents = game_instance.get_available_agents()
    for agent_id in request.agent_ids:
        normalized = (
            agent_id if not agent_id.startswith("agent:") else agent_id.replace("agent:", "")
        )
        if normalized not in available_agents:
            raise HTTPException(status_code=400, detail=f"Agent不可用: {agent_id}")

    group = await game_instance.create_group_chat(request.name, request.agent_ids)
    return group.to_dict()


@app.post("/api/groups/message")
async def send_group_message(request: GroupChatMessageRequest):
    """
    向群聊发送消息

    Args:
        request: 消息请求（group_id, message）

    Returns:
        {"success": true, "sent_agents": [...]}
    """
    if not game_instance._running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    sent_agents = await game_instance.send_to_group_chat(request.group_id, request.message)

    if not sent_agents:
        raise HTTPException(status_code=404, detail=f"群聊不存在: {request.group_id}")

    return {
        "success": True,
        "sent_agents": sent_agents,
        "count": len(sent_agents),
    }


@app.post("/api/groups/add-agent")
async def add_group_agent(request: GroupChatAgentRequest):
    """
    向群聊添加agent

    Args:
        request: 添加请求（group_id, agent_id）

    Returns:
        {"success": true}
    """
    if not game_instance._running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    success = await game_instance.add_agent_to_group(request.group_id, request.agent_id)

    if not success:
        raise HTTPException(status_code=400, detail="添加agent失败")

    return {"success": True}


@app.post("/api/groups/remove-agent")
async def remove_group_agent(request: GroupChatAgentRequest):
    """
    从群聊移除agent

    Args:
        request: 移除请求（group_id, agent_id）

    Returns:
        {"success": true}
    """
    if not game_instance._running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    success = await game_instance.remove_agent_from_group(request.group_id, request.agent_id)

    if not success:
        raise HTTPException(status_code=400, detail="移除agent失败")

    return {"success": True}


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "running" if game_instance._running else "stopped",
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
