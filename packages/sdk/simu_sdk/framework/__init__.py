"""Agent framework built on bub's hook-first pipeline core.

Uses bub.BubFramework for the stateless pipeline:

    resolve_session → load_state → build_prompt → run_model
    → save_state → render_outbound → dispatch_outbound
"""

from bub.framework import BubFramework
from bub.hookspecs import hookimpl, hookspec
from bub.types import Envelope, TurnResult

__all__ = [
    "BubFramework",
    "Envelope",
    "TurnResult",
    "hookimpl",
    "hookspec",
]
