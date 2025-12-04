"""
Event System Module

Provides dynamic event generation, effect calculation, and lifecycle management functionality
"""

from .event_models import Event, EventEffect, AgentEvent
from .event_generator import EventGenerator
from .agent_event_generator import AgentEventGenerator
from .event_effects import calculate_event_modifiers, apply_instant_effects
from .event_manager import EventManager
from .event_templates import EVENT_TEMPLATES

__all__ = [
    'Event',
    'AgentEvent',
    'EventEffect',
    'EventGenerator',
    'AgentEventGenerator',
    'EventManager',
    'calculate_event_modifiers',
    'apply_instant_effects',
    'EVENT_TEMPLATES'
]
