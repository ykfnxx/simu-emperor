"""引擎模块。"""

from simu_emperor.engine.event_generator import (
    generate_events_for_turn,
    generate_random_event,
    load_event_templates,
)

__all__ = [
    "generate_events_for_turn",
    "generate_random_event",
    "load_event_templates",
]
