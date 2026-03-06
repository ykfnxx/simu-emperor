"""
FastAPI 服务器

提供 WebSocket 实时通信和 REST API 端点。
"""

import logging
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from simu_emperor.config import settings
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.adapters.web.game_instance import WebGameInstance
from simu_emperor.adapters.web.connection_manager import ConnectionManager
from simu_emperor.adapters.web.message_converter import MessageConverter


logger = logging.getLogger(__name__)

# FastAPI 应用
app = FastAPI(title="Emperor Simulator Web API")

# 全局单例
game_instance = WebGameInstance(settings)
connection_manager = ConnectionManager()
message_converter = MessageConverter()

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Startup/Shutdown
# ============================================================================

@app.on_event("startup")
async def startup():
    """应用启动时初始化游戏实例"""
    logger.info("Starting FastAPI server...")
    await game_instance.start()

    # 订阅所有事件，广播给 WebSocket 客户端
    if game_instance.event_bus:
        game_instance.event_bus.subscribe("*", _on_event)

    logger.info("FastAPI server started")

@app.on_event("shutdown")
async def shutdown():
    """应用关闭时清理资源"""
    logger.info("Shutting down FastAPI server...")
    await game_instance.shutdown()
    logger.info("FastAPI server shut down")

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
        await handle_command(data)
    elif msg_type == "chat":
        await handle_chat(data)
    else:
        await connection_manager.send_personal({
            "kind": "error",
            "data": {"message": f"Unknown message type: {msg_type}"}
        }, websocket)

async def handle_command(data: dict) -> None:
    """处理命令消息"""
    agent = data.get("agent")
    command = data.get("text", "")

    if not agent:
        logger.warning("Command missing agent field")
        return

    event = Event(
        src="player:web",
        dst=[f"agent:{agent}"],
        type=EventType.COMMAND,
        payload={"intent": command, "source": "web"},
        session_id=game_instance.session_id
    )

    if game_instance.event_bus:
        await game_instance.event_bus.send_event(event)
    else:
        logger.error("EventBus not initialized")

async def handle_chat(data: dict) -> None:
    """处理聊天消息"""
    agent = data.get("agent")
    text = data.get("text", "")

    if not agent:
        logger.warning("Chat missing agent field")
        return

    event = Event(
        src="player:web",
        dst=[f"agent:{agent}"],
        type=EventType.CHAT,
        payload={"query": text},
        session_id=game_instance.session_id
    )

    if game_instance.event_bus:
        await game_instance.event_bus.send_event(event)

async def _on_event(event: Event) -> None:
    """
    EventBus 事件回调（广播给所有 WebSocket 客户端）

    Args:
        event: EventBus 事件
    """
    # 转换为 WSMessage
    ws_message = message_converter.convert(event)

    if ws_message:
        await connection_manager.broadcast(ws_message)

# ============================================================================
# REST API
# ============================================================================

class CommandRequest(BaseModel):
    """命令请求"""
    agent: str
    command: str

@app.post("/api/command")
async def send_command(cmd: CommandRequest):
    """
    发送命令到游戏

    Args:
        cmd: 命令请求

    Returns:
        {"success": true}
    """
    event = Event(
        src="player:web",
        dst=[f"agent:{cmd.agent}"],
        type=EventType.COMMAND,
        payload={"intent": cmd.command, "source": "web"},
        session_id=game_instance.session_id
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

@app.get("/api/agents")
async def list_agents():
    """
    列出所有活跃 agents

    Returns:
        ["governor_zhili", "minister_of_revenue", ...]
    """
    if not game_instance.agent_manager:
        raise HTTPException(status_code=503, detail="Game not initialized")

    agents = game_instance.agent_manager.list_agents()
    return agents

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
