"""引擎模块。"""

from simu_emperor.engine.coordinator import TurnCoordinator
from simu_emperor.engine.resolver import resolve_turn

# 以下模块当前未使用，为未来功能预留
# from simu_emperor.engine.event_generator import (
#     generate_events_for_turn,
#     generate_random_event,
#     load_event_templates,
# )

__all__ = [
    "TurnCoordinator",
    "resolve_turn",
    # "generate_events_for_turn",
    # "generate_random_event",
    # "load_event_templates",
]
