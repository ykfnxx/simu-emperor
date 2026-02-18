"""报告 + 省份 + 命令路由。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from simu_emperor.engine.models.events import EventSource, PlayerEvent
from simu_emperor.player.schemas import CommandRequest, CommandResponse, ReportResponse

router = APIRouter(tags=["reports"])


def _get_loop(request: Request):
    return request.app.state.game_loop


@router.get("/reports", response_model=list[ReportResponse])
async def get_reports(request: Request) -> list[ReportResponse]:
    """获取当前回合的 Agent 报告。"""
    loop = _get_loop(request)
    reports = await loop._report_repo.list_reports(loop.state.game_id, loop.state.current_turn)
    return [
        ReportResponse(agent_id=agent_id, turn=loop.state.current_turn, markdown=markdown)
        for agent_id, markdown in reports
    ]


@router.get("/provinces")
async def get_provinces(request: Request) -> list[dict]:
    """获取省份概览。"""
    loop = _get_loop(request)
    provinces = []
    for p in loop.state.base_data.provinces:
        provinces.append(
            {
                "id": p.province_id,
                "name": p.name,
                "population": str(p.population.total),
                "happiness": str(p.population.happiness),
                "granary_stock": str(p.granary_stock),
                "local_treasury": str(p.local_treasury),
                "garrison_size": str(p.military.garrison_size),
            }
        )
    return provinces


@router.post("/commands", response_model=CommandResponse)
async def submit_command(body: CommandRequest, request: Request) -> CommandResponse:
    """提交玩家命令。"""
    loop = _get_loop(request)
    command = PlayerEvent(
        source=EventSource.PLAYER,
        command_type=body.command_type,
        description=body.description,
        target_province_id=body.target_province_id,
        parameters=body.parameters,
        direct=body.direct,
        turn_created=loop.state.current_turn,
    )
    loop.submit_command(command)
    return CommandResponse(
        status="accepted",
        command_type=body.command_type,
        direct=body.direct,
    )


@router.get("/commands")
async def get_commands(request: Request) -> list[dict]:
    """获取当前回合已提交的命令。"""
    loop = _get_loop(request)
    commands = await loop._command_repo.get_commands(loop.state.game_id, loop.state.current_turn)
    return [
        {
            "command_type": cmd.command_type,
            "target_province_id": cmd.target_province_id,
            "parameters": cmd.parameters,
            "has_result": result is not None,
        }
        for cmd, result in commands
    ]
