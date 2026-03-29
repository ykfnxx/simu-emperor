"""Incident and Effect data models (V5).

Migrated from V4 engine.models.incident for V5 architecture.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List
import re


@dataclass
class Effect:
    """单个效果，由 Incident 产生（单点影响）

    Exactly one of 'add' or 'factor' must be specified.

    Args:
        target_path: Dot-notation path to target, e.g. "provinces.zhili.production_value"
        add: One-time numeric change (only applied once when incident.applied == False)
        factor: Continuous percentage multiplier (applied every tick, e.g., 0.1 = +10%)
    """

    target_path: str
    add: Optional[Decimal] = None
    factor: Optional[Decimal] = None

    def __post_init__(self):
        if (self.add is None) == (self.factor is None):
            raise ValueError("Effect must have exactly one of 'add' or 'factor'")

        if self.add is not None and not isinstance(self.add, Decimal):
            self.add = Decimal(str(self.add))
        if self.factor is not None and not isinstance(self.factor, Decimal):
            self.factor = Decimal(str(self.factor))

        if self.factor is not None and self.factor <= Decimal("-1.0"):
            raise ValueError(f"Effect.factor must be > -1.0, got {self.factor}")

        valid_pattern = re.compile(r"^(provinces\.[a-z_]+\.[a-z_]+|nation\.[a-z_]+)$")
        if not valid_pattern.match(self.target_path):
            raise ValueError(
                f"Effect.target_path must be in format 'provinces.<id>.<field>' or 'nation.<field>', "
                f"got '{self.target_path}'"
            )


@dataclass
class Incident:
    """引擎内的事件（区别于 EventBus Event）

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
    title: str
    description: str
    effects: List[Effect]
    source: str
    remaining_ticks: int
    applied: bool = False

    def __post_init__(self):
        if self.remaining_ticks <= 0:
            raise ValueError(f"Incident.remaining_ticks must be > 0, got {self.remaining_ticks}")

        if not self.effects:
            raise ValueError("Incident.effects must not be empty")
