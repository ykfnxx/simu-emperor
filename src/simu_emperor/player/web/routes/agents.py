"""Agent 对话路由。"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

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
    """与 Agent 对话（非流式）。"""
    loop = _get_loop(request)
    response = await loop.handle_player_message(agent_id, body.message)
    return ChatResponse(agent_id=agent_id, response=response)


@router.post("/agents/{agent_id}/chat/stream")
async def chat_with_agent_stream(
    agent_id: str, body: ChatRequest, request: Request
) -> StreamingResponse:
    """与 Agent 对话（流式输出）。"""

    async def event_generator():
        try:
            loop = _get_loop(request)
            # 获取 Agent 的 context
            context = await loop._build_agent_context(agent_id, body.message)

            # 流式生成
            full_response = ""
            async for chunk in loop._llm_client.generate_stream(context):
                full_response += chunk
                # SSE 格式：data: {content}\n\n
                yield f"data: {chunk}\n\n"

            # 保存完整对话到历史记录
            await loop._chat_repo.add_message(loop.state.game_id, agent_id, "player", body.message)
            await loop._chat_repo.add_message(loop.state.game_id, agent_id, "agent", full_response)

            # 发送结束标记
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/agents/{agent_id}/chat")
async def get_chat_history(agent_id: str, request: Request) -> list[dict]:
    """获取与 Agent 的对话历史。"""
    loop = _get_loop(request)
    history = await loop._chat_repo.get_history(loop.state.game_id, agent_id)
    return [
        {"role": role, "message": message, "created_at": str(created_at)}
        for role, message, created_at in history
    ]
