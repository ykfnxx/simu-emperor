"""Agent 对话路由。"""

from __future__ import annotations

import re

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from simu_emperor.player.schemas import ChatRequest, ChatResponse, CommandRequest, CommandResponse
from simu_emperor.engine.models.events import PlayerEvent, EventSource

router = APIRouter(tags=["agents"])


class AgentInfo(BaseModel):
    """Agent 信息。"""

    id: str
    name: str
    title: str


class AgentDetail(BaseModel):
    """Agent 详细信息（含职责范围）。"""

    id: str
    name: str
    title: str
    data_scope: dict


class AgentTemplate(BaseModel):
    """可用官员模板。"""

    id: str
    display_name: str


class AddAgentRequest(BaseModel):
    """新增官员请求。"""

    template_id: str
    new_id: str | None = None  # 如果不提供，使用 template_id


class UpdateAgentRequest(BaseModel):
    """更新官员请求。"""

    title: str | None = None
    data_scope: dict | None = None


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


@router.post("/agents/{agent_id}/command", response_model=CommandResponse)
async def send_command_to_agent(
    agent_id: str, body: CommandRequest, request: Request
) -> CommandResponse:
    """向 Agent 下旨（创建 PlayerEvent，指定该 Agent 执行）。"""
    loop = _get_loop(request)
    state = loop.state

    # 创建 PlayerEvent，指定 agent_id
    event = PlayerEvent(
        source=EventSource.PLAYER,
        turn_created=state.current_turn,
        description=body.description,
        command_type=body.command_type,
        target_province_id=body.target_province_id,
        parameters=body.parameters,
        direct=body.direct,
    )

    # 使用 submit_command 正确处理命令
    # direct=True -> 直接加入 active_events
    # direct=False -> 加入 _pending_commands，等待执行阶段由 Agent 处理
    loop.submit_command(event)

    return CommandResponse(
        status="accepted",
        command_type=body.command_type,
        direct=body.direct,
    )


@router.get("/agents/{agent_id}/report")
async def get_agent_report(agent_id: str, request: Request, turn: int | None = None):
    """获取指定 Agent 的奏折。"""
    from simu_emperor.player.schemas import ReportResponse

    loop = _get_loop(request)
    target_turn = turn if turn is not None else loop.state.current_turn

    reports = await loop._report_repo.list_reports(loop.state.game_id, target_turn)
    for agent_id_in_report, markdown in reports:
        if agent_id_in_report == agent_id:
            return ReportResponse(agent_id=agent_id, turn=target_turn, markdown=markdown)

    return None


class DismissResponse(BaseModel):
    """免职响应。"""

    status: str
    agent_id: str


@router.delete("/agents/{agent_id}", response_model=DismissResponse)
async def dismiss_agent(agent_id: str, request: Request) -> DismissResponse:
    """免去官员职位。"""
    loop = _get_loop(request)
    loop._agent_manager.remove_agent(agent_id)
    return DismissResponse(status="dismissed", agent_id=agent_id)


@router.get("/agents/{agent_id}/detail", response_model=AgentDetail)
async def get_agent_detail(agent_id: str, request: Request) -> AgentDetail:
    """获取 Agent 详细信息（含职责范围）。"""
    loop = _get_loop(request)
    soul_content = loop._agent_manager.file_manager.read_soul(agent_id)
    data_scope_content = loop._agent_manager.file_manager.read_data_scope(agent_id)

    info = _parse_agent_info(agent_id, soul_content)
    data_scope = yaml.safe_load(data_scope_content) if data_scope_content else {}

    return AgentDetail(
        id=agent_id,
        name=info.name,
        title=info.title,
        data_scope=data_scope,
    )


@router.get("/agent-templates", response_model=list[AgentTemplate])
async def list_agent_templates(request: Request) -> list[AgentTemplate]:
    """列出可用的官员模板。"""
    loop = _get_loop(request)
    template_base = loop._agent_manager.file_manager.template_base

    templates = []
    for template_dir in sorted(template_base.iterdir()):
        if template_dir.is_dir() and (template_dir / "soul.md").exists():
            data_scope_path = template_dir / "data_scope.yaml"
            display_name = template_dir.name
            if data_scope_path.exists():
                data_scope = yaml.safe_load(data_scope_path.read_text(encoding="utf-8"))
                display_name = data_scope.get("display_name", template_dir.name)
            templates.append(AgentTemplate(id=template_dir.name, display_name=display_name))

    return templates


@router.post("/agents", response_model=AgentInfo)
async def add_agent(body: AddAgentRequest, request: Request) -> AgentInfo:
    """新增官员。"""
    loop = _get_loop(request)
    template_base = loop._agent_manager.file_manager.template_base

    template_dir = template_base / body.template_id
    if not template_dir.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Template {body.template_id} not found")

    agent_id = body.new_id or body.template_id
    soul_content = (template_dir / "soul.md").read_text(encoding="utf-8")
    data_scope_content = (template_dir / "data_scope.yaml").read_text(encoding="utf-8")

    loop._agent_manager.add_agent(agent_id, soul_content, data_scope_content)

    return _parse_agent_info(agent_id, soul_content)


@router.patch("/agents/{agent_id}", response_model=AgentDetail)
async def update_agent(agent_id: str, body: UpdateAgentRequest, request: Request) -> AgentDetail:
    """更新官员信息（职位或职责范围）。"""
    loop = _get_loop(request)
    file_manager = loop._agent_manager.file_manager

    # 获取当前信息
    soul_content = file_manager.read_soul(agent_id)
    data_scope_content = file_manager.read_data_scope(agent_id)
    data_scope = yaml.safe_load(data_scope_content) if data_scope_content else {}

    # 更新职位（修改 soul.md 第一行）
    if body.title:
        lines = soul_content.strip().split("\n")
        # 解析第一行
        match = re.match(r"^#\s*(.+?)\s*[-–—]\s*(.+)$", lines[0])
        if match:
            name = match.group(2).strip()
            lines[0] = f"# {body.title} - {name}"
        else:
            lines[0] = f"# {body.title} - {agent_id}"
        soul_content = "\n".join(lines)
        file_manager.write_soul(agent_id, soul_content)

    # 更新职责范围
    if body.data_scope:
        data_scope.update(body.data_scope)
        file_manager.write_data_scope(agent_id, yaml.dump(data_scope, allow_unicode=True))

    # 返回更新后的信息
    return await get_agent_detail(agent_id, request)
