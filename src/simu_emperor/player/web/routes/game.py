"""游戏状态 + 阶段推进 + 历史路由。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from simu_emperor.engine.models.state import GamePhase
from simu_emperor.player.schemas import AdvanceResponse, StateResponse

router = APIRouter(tags=["game"])


def _get_loop(request: Request):
    return request.app.state.game_loop


@router.get("/state", response_model=StateResponse)
async def get_state(request: Request) -> StateResponse:
    """获取当前游戏状态摘要。"""
    loop = _get_loop(request)
    state = loop.state
    # 返回完整的省份数据，与前端 ProvinceBaseData 类型对齐
    provinces = [p.model_dump(mode="json") for p in state.base_data.provinces]
    return StateResponse(
        game_id=state.game_id,
        current_turn=state.current_turn,
        phase=state.phase.value,
        provinces=provinces,
        imperial_treasury=str(state.base_data.imperial_treasury),
        active_events_count=len(state.active_events),
    )


@router.post("/turn/advance", response_model=AdvanceResponse)
async def advance_turn(request: Request) -> AdvanceResponse:
    """推进到下一阶段。根据当前 phase 自动选择操作。"""
    loop = _get_loop(request)
    phase = loop.phase

    if phase == GamePhase.RESOLUTION:
        _state, _metrics = await loop.advance_to_resolution()
        return AdvanceResponse(
            phase=loop.phase.value,
            turn=loop.state.current_turn,
            message="回合结算完成，进入汇总阶段",
        )

    if phase == GamePhase.SUMMARY:
        reports = await loop.advance_to_summary()
        return AdvanceResponse(
            phase=loop.phase.value,
            turn=loop.state.current_turn,
            message="Agent 汇总完成，进入交互阶段",
            reports=reports,
        )

    if phase == GamePhase.INTERACTION:
        events = await loop.advance_to_execution()
        event_dicts = [
            {"event_id": e.event_id, "description": e.description, "agent_id": e.agent_id}
            for e in events
        ]
        return AdvanceResponse(
            phase=loop.phase.value,
            turn=loop.state.current_turn,
            message="命令执行完成，进入执行阶段",
            events=event_dicts,
        )

    # EXECUTION → 下一回合 RESOLUTION
    _state, _metrics = await loop.advance_to_resolution()
    return AdvanceResponse(
        phase=loop.phase.value,
        turn=loop.state.current_turn,
        message="新回合结算完成，进入汇总阶段",
    )


@router.get("/history")
async def get_history(request: Request) -> list[dict]:
    """获取历史回合记录。"""
    loop = _get_loop(request)
    records = []
    for tr in loop.state.history:
        records.append(
            {
                "turn": tr.turn,
                "events_count": len(tr.events_applied),
                "has_metrics": tr.metrics is not None,
            }
        )
    return records


@router.get("/debug/real-data")
async def get_real_data(request: Request) -> dict:
    """调试接口：返回完整真实数据。"""
    loop = _get_loop(request)
    return loop.state.base_data.model_dump(mode="json")
