"""事件层级模型：PlayerEvent/AgentEvent/RandomEvent，以 discriminated union 组织。"""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from simu_emperor.engine.models.effects import EventEffect


class EventSource(StrEnum):
    """事件来源类型（用作 discriminator）。"""

    PLAYER = "player"
    AGENT = "agent"
    RANDOM = "random"


class BaseEvent(BaseModel):
    """事件基类，定义所有事件共有字段。"""

    event_id: str = Field(default_factory=lambda: uuid4().hex, description="事件唯一标识")
    turn_created: int = Field(ge=0, description="事件创建回合")
    description: str = Field(description="事件描述")
    effects: list[EventEffect] = Field(default_factory=list, description="事件效果列表")
    duration: int = Field(default=1, ge=1, description="持续回合数")


class PlayerEvent(BaseEvent):
    """玩家操作事件（建设、调税、征兵等）。"""

    source: Literal[EventSource.PLAYER] = EventSource.PLAYER
    command_type: str = Field(description="命令类型")
    target_province_id: str | None = Field(default=None, description="目标省份 ID")
    parameters: dict[str, str] = Field(default_factory=dict, description="命令参数")
    direct: bool = Field(default=False, description="True=皇帝亲政直接生效, False=需经Agent执行")


class AgentEvent(BaseEvent):
    """Agent 执行结果事件（可能偷工减料）。"""

    source: Literal[EventSource.AGENT] = EventSource.AGENT
    agent_event_type: str = Field(description="Agent 事件类型")
    agent_id: str = Field(description="执行 Agent 的 ID")
    fidelity: Decimal = Field(ge=0, le=1, description="执行忠实度（0=完全糊弄, 1=完全忠实）")


class RandomEvent(BaseEvent):
    """随机事件（天灾、丰收、叛乱等）。"""

    source: Literal[EventSource.RANDOM] = EventSource.RANDOM
    category: str = Field(description="事件分类（如 disaster, harvest, rebellion）")
    severity: Decimal = Field(ge=0, le=1, description="严重程度")


GameEvent = Annotated[
    PlayerEvent | AgentEvent | RandomEvent,
    Field(discriminator="source"),
]
"""游戏事件联合类型，以 source 字段区分具体类型。"""
