"""FastAPI 服务器 (V4 - 应用层集成)

提供 WebSocket 实时通信和 REST API 端点。
V4重构：所有业务逻辑委托给ApplicationServices，本模块仅处理协议转换。
"""

import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal
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

            logger.info(
                f"[WS] Message published to event bus: agent={agent}, session={target_session_id}"
            )

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
    # Logging (INFO level for debugging)
    logger.info(f"[WS _on_event] Received event: type={event.type}, src={event.src}, dst={event.dst}")

    # 转换为 WSMessage
    ws_message = await message_converter.convert(event)

    if ws_message:
        logger.info(f"[WS _on_event] Broadcasting: kind={ws_message.get('kind')}, connections={connection_manager.connection_count}")
        await connection_manager.broadcast(ws_message)
    else:
        logger.info(f"[WS _on_event] Message converter returned None for event type: {event.type}")


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


class AgentGenerateRequest(BaseModel):
    """生成 agent 请求"""

    agent_id: str
    title: str  # 官职
    name: str  # 姓名
    duty: str  # 职责
    personality: str  # 为人描述
    province: str | None = None  # 管辖省份


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

    # V4: 使用 load_nation_data() 获取 NationData 对象
    from dataclasses import asdict
    from simu_emperor.persistence.serialization import _decimal_to_str

    nation = await game_instance.repository.load_nation_data()
    if nation is None:
        return {}

    # 转换为 dict，Decimal 转 str
    state_dict = _decimal_to_str(asdict(nation))

    # 获取 engine 用于计算变化量和实际税率
    engine = game_instance.game_service.engine
    base_tax_rate = Decimal(str(state_dict.get("base_tax_rate", "0.10")))
    provinces = state_dict.get("provinces", {})

    if isinstance(provinces, dict) and engine:
        for province_id, province in provinces.items():
            if isinstance(province, dict):
                # 添加实际税率（base_tax_rate + tax_modifier）
                tax_modifier = Decimal(str(province.get("tax_modifier", "0.0")))
                actual_tax_rate = base_tax_rate + tax_modifier
                province["actual_tax_rate"] = str(actual_tax_rate)

                # 添加变化量（相较上一tick）- 仅用于核心数值
                for field in ["production_value", "population", "stockpile", "fixed_expenditure"]:
                    delta = engine.get_province_delta(province_id, field)
                    province[f"{field}_delta"] = str(delta)

                # 添加事件影响（用于税率、增长率显示）
                incident_effects = engine.get_province_incident_effects(province_id)
                province["tax_modifier_incident"] = str(incident_effects["tax_modifier"])
                province["production_growth_incident"] = str(
                    incident_effects["production_growth_factor"]
                )
                province["population_growth_incident"] = str(
                    incident_effects["population_growth_factor"]
                )

    return state_dict


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

    # 找到标记为 is_current 的session作为当前session
    current_session_id = None
    current_agent_id = None

    for group in agent_sessions:
        for session in group["sessions"]:
            if session.get("is_current"):
                current_session_id = session["session_id"]
                current_agent_id = group["agent_id"]
                break
        if current_session_id:
            break

    # 如果没有找到is_current的session，使用main session
    if not current_session_id:
        from simu_emperor.common import DEFAULT_WEB_SESSION_ID

        current_session_id = DEFAULT_WEB_SESSION_ID

    return {
        "current_session_id": current_session_id,
        "current_agent_id": current_agent_id,
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

    agent_ids = await game_instance.agent_service.get_available_agents()
    from simu_emperor.common import get_agent_display_name

    return [
        {"agent_id": aid, "agent_name": get_agent_display_name(aid, game_instance.settings.data_dir)}
        for aid in agent_ids
    ]


@app.post("/api/agents/generate")
async def generate_agent(request: AgentGenerateRequest):
    """LLM 生成 agent 配置并创建文件"""
    if not game_instance.is_running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    try:
        result = await game_instance.agent_service.generate_agent(
            agent_id=request.agent_id,
            title=request.title,
            name=request.name,
            duty=request.duty,
            personality=request.personality,
            province=request.province,
        )
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/agents/add-generated")
async def add_generated_agent(request: AgentGenerateRequest):
    """生成配置并启动 agent（异步后台任务）

    立即返回任务 ID，需要轮询 /api/agents/jobs/{task_id} 查询状态。
    """
    if not game_instance.is_running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    try:
        task_tracker = game_instance.agent_service._get_task_tracker()

        # 创建后台任务
        task = task_tracker.create_task(f"创建 Agent: {request.agent_id}")

        # 在后台运行任务（不等待完成）
        async def background_task():
            try:
                await task_tracker.run_task(
                    task.task_id,
                    lambda: game_instance.agent_service.add_generated_agent_async(
                        agent_id=request.agent_id,
                        title=request.title,
                        name=request.name,
                        duty=request.duty,
                        personality=request.personality,
                        province=request.province,
                    ),
                )
            except Exception as e:
                logger.error(f"Background task failed: {e}")
                raise

        # 启动后台任务（不阻塞响应）
        asyncio.create_task(background_task())

        return {
            "success": True,
            "task_id": task.task_id,
            "agent_id": request.agent_id,
            "status": "pending",
            "message": "Agent 创建任务已启动，请轮询状态查询接口",
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/agents/jobs/{task_id}")
async def get_agent_job_status(task_id: str):
    """查询 Agent 创建任务状态

    Args:
        task_id: 任务 ID

    Returns:
        任务状态信息
    """
    if not game_instance.is_running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    task_tracker = game_instance.agent_service._get_task_tracker()
    task = task_tracker.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    return task.to_dict()


# ============================================================================
# Incident API
# ============================================================================


@app.get("/api/incidents")
async def list_incidents():
    """列出所有活跃的 incidents"""
    if not game_instance.is_running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    engine = game_instance.game_service.engine
    if not engine:
        return []

    incidents = engine.get_active_incidents()
    return [
        {
            "incident_id": inc.incident_id,
            "title": inc.title,
            "description": inc.description,
            "source": inc.source,
            "remaining_ticks": inc.remaining_ticks,
            "effects": [
                {
                    "target_path": eff.target_path,
                    "add": str(eff.add) if eff.add is not None else None,
                    "factor": str(eff.factor) if eff.factor is not None else None,
                }
                for eff in inc.effects
            ],
        }
        for inc in incidents
    ]


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
