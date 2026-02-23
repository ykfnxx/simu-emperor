"""Agent 对话路由。"""

from __future__ import annotations

import re

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from simu_emperor.player.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["agents"])


class AgentInfo(BaseModel):
    """Agent 信息。"""

    id: str
    name: str
    title: str


def _get_loop(request: Request):
    return request.app.state.game_loop


def _parse_agent_info(agent_id: str, soul_content: str) -> AgentInfo:
    """从 soul.md 解析 agent 名称和职位。"""
    # 尝试匹配第一行的格式: "# 职位 - 姓名" 或 "# 姓名 - 职位"
    first_line = soul_content.strip().split("\n")[0]
    match = re.match(r"^#\s*(.+?)\s*[-–—]\s*(.+)$", first_line)
    if match:
        # 判断哪边是名字（通常是2-3个汉字）
        part1, part2 = match.group(1).strip(), match.group(2).strip()
        # 如果 part2 是2-3个字符，大概率是名字
        if len(part2) <= 3:
            return AgentInfo(id=agent_id, name=part2, title=part1)
        else:
            return AgentInfo(id=agent_id, name=part1, title=part2)

    # 回退：使用 agent_id 作为名称
    return AgentInfo(id=agent_id, name=agent_id, title=agent_id)


@router.get("/agents")
async def list_agents(request: Request) -> list[AgentInfo]:
    """列出活跃 Agent。"""
    loop = _get_loop(request)
    agent_ids = loop._agent_manager.list_active_agents()
    agents = []
    for agent_id in agent_ids:
        soul_content = loop._agent_manager.file_manager.read_soul(agent_id)
        agents.append(_parse_agent_info(agent_id, soul_content))
    return agents


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
