"""Agent 对话路由。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from simu_emperor.player.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["agents"])


def _get_loop(request: Request):
    return request.app.state.game_loop


@router.get("/agents")
async def list_agents(request: Request) -> list[str]:
    """列出活跃 Agent。"""
    loop = _get_loop(request)
    return loop._agent_manager.list_active_agents()


@router.post("/agents/{agent_id}/chat", response_model=ChatResponse)
async def chat_with_agent(agent_id: str, body: ChatRequest, request: Request) -> ChatResponse:
    """与 Agent 对话。"""
    loop = _get_loop(request)
    response = await loop.handle_player_message(agent_id, body.message)
    return ChatResponse(agent_id=agent_id, response=response)


@router.get("/agents/{agent_id}/chat")
async def get_chat_history(agent_id: str, request: Request) -> list[dict]:
    """获取与 Agent 的对话历史。"""
    loop = _get_loop(request)
    history = await loop._chat_repo.get_history(loop.state.game_id, agent_id)
    return [
        {"role": role, "message": message, "created_at": str(created_at)}
        for role, message, created_at in history
    ]
