"""Incident and Effect data models for the V4 engine.

These models represent time-limited game events that modify province/nation data.
Incident is used instead of "Event" to avoid confusion with EventBus events.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List
import re


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
        ValueError: If factor <= -1.0 (would make value negative or zero)
        ValueError: If target_path format is invalid
    """

    target_path: str  # 目标路径，如 "provinces.zhili.production_value"

    # 二选一：add 是一次性数值变化，factor 是持续比例增量
    add: Optional[Decimal] = None  # 如 add=1000 表示库存+1000（仅首次生效）
    factor: Optional[Decimal] = None  # 如 factor=0.1 表示产值+10%（每个 tick 生效）

    def __post_init__(self):
        # 确保 add 和 factor 只有一个非 None
        if (self.add is None) == (self.factor is None):
            raise ValueError("Effect must have exactly one of 'add' or 'factor'")

        # 确保 Decimal 类型
        if self.add is not None and not isinstance(self.add, Decimal):
            self.add = Decimal(str(self.add))
        if self.factor is not None and not isinstance(self.factor, Decimal):
            self.factor = Decimal(str(self.factor))

        # 验证 factor 范围：factor > -1.0（避免使数值变为负数）
        if self.factor is not None and self.factor <= Decimal("-1.0"):
            raise ValueError(f"Effect.factor must be > -1.0, got {self.factor}")

        # 验证 target_path 格式
        # 支持格式：provinces.{id}.{field} 或 nation.{field}
        valid_pattern = re.compile(r"^(provinces\.[a-z_]+\.[a-z_]+|nation\.[a-z_]+)$")
        if not valid_pattern.match(self.target_path):
            raise ValueError(
                f"Effect.target_path must be in format 'provinces.<id>.<field>' or 'nation.<field>', "
                f"got '{self.target_path}'"
            )


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

    Raises:
        ValueError: If remaining_ticks <= 0
        ValueError: If effects list is empty
    """

    incident_id: str
    title: str  # 事件标题
    description: str  # 事件描述
    effects: List[Effect]
    source: str  # 触发来源

    # 持续时长（绑定在 Incident 层，所有 Incident 都必须有持续时间）
    remaining_ticks: int  # 剩余 tick 数，必须 > 0
    applied: bool = False  # 标记 add 类 Effect 是否已生效（一次性应用）

    def __post_init__(self):
        """验证数据有效性"""
        if self.remaining_ticks <= 0:
            raise ValueError(f"Incident.remaining_ticks must be > 0, got {self.remaining_ticks}")

        if not self.effects:
            raise ValueError("Incident.effects must not be empty")
