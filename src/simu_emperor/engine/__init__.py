"""引擎模块 (V4)."""

from simu_emperor.engine.engine import Engine
from simu_emperor.engine.protocols import GameStateRepository
from simu_emperor.engine.tick_coordinator import TickCoordinator

__all__ = [
    "Engine",
    "TickCoordinator",
    "GameStateRepository",
]
