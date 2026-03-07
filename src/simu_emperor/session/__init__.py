"""Session module for V4 Task Session architecture."""

from simu_emperor.session.constants import MAX_TASK_DEPTH
from simu_emperor.session.models import Session
from simu_emperor.session.manager import SessionManager

__all__ = ["MAX_TASK_DEPTH", "Session", "SessionManager"]
