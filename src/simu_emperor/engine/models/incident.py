"""Incident and Effect data models for the V4 engine.

These models represent time-limited game events that modify province/nation data.
Incident is used instead of "Event" to avoid confusion with EventBus events.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List


@dataclass
class Effect:
    """单个效果，由 Incident 产生（单点影响）

    Effect represents a single modification to a target value.
    Exactly one of 'add' or 'factor' must be specified.

    Args:
        target_path: Dot-notation path to target, e.g. "provinces.zhili.production_value"
        add: One-time numeric change (only applied once when incident.applied == False)
        factor: Continuous percentage multiplier (applied every tick, e.g., 0.1 = +10%)

    Raises:
        ValueError: If both add and factor are None, or both are set
    """

    target_path: str  # 目标路径，如 "provinces.zhili.production_value"

    # 二选一：add 是一次性数值变化，factor 是持续比例增量
    add: Optional[Decimal] = None      # 如 add=1000 表示库存+1000（仅首次生效）
    factor: Optional[Decimal] = None   # 如 factor=0.1 表示产值+10%（每个 tick 生效）

    def __post_init__(self):
        # 确保 add 和 factor 只有一个非 None
        if (self.add is None) == (self.factor is None):
            raise ValueError("Effect must have exactly one of 'add' or 'factor'")


@dataclass
class Incident:
    """引擎内的事件（区别于 EventBus Event）

    Incident represents a game event that affects province/nation data over time.
    All incidents have a duration measured in ticks (1 tick = 1 week).

    Args:
        incident_id: Unique identifier for this incident
        title: Human-readable title
        description: Human-readable description
        effects: List of Effect objects to apply
        source: Origin of this incident (e.g., agent_id, "system")
        remaining_ticks: Ticks remaining until expiry (must be > 0)
        applied: Whether add-type effects have been applied (one-time flag)
    """

    incident_id: str
    title: str  # 事件标题
    description: str  # 事件描述
    effects: List[Effect]
    source: str  # 触发来源

    # 持续时长（绑定在 Incident 层，所有 Incident 都必须有持续时间）
    remaining_ticks: int  # 剩余 tick 数，必须 > 0
    applied: bool = False  # 标记 add 类 Effect 是否已生效（一次性应用）
