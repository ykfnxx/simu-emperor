"""游戏状态模型：GameState 和 TurnRecord。"""

from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field

from simu_emperor.engine.models.base_data import NationalBaseData
from simu_emperor.engine.models.events import GameEvent


class GamePhase(StrEnum):
    """游戏阶段枚举。"""

    RESOLUTION = "resolution"
    SUMMARY = "summary"
    INTERACTION = "interaction"
    EXECUTION = "execution"


class TurnRecord(BaseModel):
    """不可变的回合记录。"""

    turn: int = Field(ge=0, description="回合数")
    base_data_snapshot: NationalBaseData = Field(description="回合结束时的数据快照")
    events_applied: list[GameEvent] = Field(default_factory=list, description="本回合应用的事件")


class GameState(BaseModel):
    """游戏完整状态。"""

    game_id: str = Field(default_factory=lambda: uuid4().hex, description="游戏唯一标识")
    current_turn: int = Field(default=0, ge=0, description="当前回合数")
    phase: GamePhase = Field(default=GamePhase.RESOLUTION, description="当前游戏阶段")
    base_data: NationalBaseData = Field(description="当前全国数据")
    active_events: list[GameEvent] = Field(default_factory=list, description="活跃事件列表")
    history: list[TurnRecord] = Field(default_factory=list, description="历史回合记录")
