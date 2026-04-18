"""Bub-like hook-first agent framework built on pluggy.

Provides a stateless pipeline core (~200 lines) that delegates all
behavior to plugins via hooks:

    resolve_session → load_state → build_prompt → run_model
    → save_state → dispatch_outbound
"""

from simu_sdk.framework.core import BubFramework, Envelope, TurnResult
from simu_sdk.framework.hooks import hookimpl, hookspec
from simu_sdk.framework.models import SimuTurnState

__all__ = [
    "BubFramework",
    "Envelope",
    "TurnResult",
    "SimuTurnState",
    "hookimpl",
    "hookspec",
]
