"""Adapters 层 - 外部接口适配器

This module contains adapters for external interfaces like Telegram Bot, CLI, etc.
"""

from simu_emperor.adapters.telegram.session import SessionManager, GameSession

__all__ = ["SessionManager", "GameSession"]
