"""Bub-like stateless pipeline core (~200 lines).

The framework holds no state — all behavior is delegated to plugins
registered via pluggy.  The pipeline order is fixed:

    resolve_session → load_state → build_prompt → run_model
    → save_state → dispatch_outbound

Plugins are registered with ``framework.register(plugin_instance)``
and implement hooks via ``@hookimpl``.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from typing import Any

import pluggy

from simu_sdk.framework.hooks import PROJECT_NAME, SimuHookSpec
from simu_sdk.framework.models import SimuTurnState

logger = logging.getLogger(__name__)


@dataclass
class Envelope:
    """Wrapper around an inbound event entering the pipeline."""

    payload: Any  # TapeEvent
    session_id: str = ""
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.session_id and hasattr(self.payload, "session_id"):
            self.session_id = self.payload.session_id


@dataclass
class TurnResult:
    """Output of a single pipeline execution."""

    session_id: str
    state: SimuTurnState
    result: Any  # ReActResult or similar


class BubFramework:
    """Stateless hook-first pipeline core.

    Usage::

        framework = BubFramework()
        framework.register(SimuTapePlugin(...))
        framework.register(SimuContextPlugin(...))
        framework.register(SimuReActPlugin(...))
        framework.register(MCPClientPlugin(...))
        framework.register(SimuMemoryPlugin(...))

        result = await framework.process_inbound(Envelope(payload=event))
    """

    def __init__(self) -> None:
        self._pm = pluggy.PluginManager(PROJECT_NAME)
        self._pm.add_hookspecs(SimuHookSpec)

    def register(self, plugin: Any) -> None:
        """Register a plugin instance with the framework."""
        self._pm.register(plugin)
        name = type(plugin).__name__
        logger.info("Registered plugin: %s", name)

    def unregister(self, plugin: Any) -> None:
        """Unregister a plugin instance."""
        self._pm.unregister(plugin)

    async def process_inbound(self, envelope: Envelope) -> TurnResult:
        """Execute the full pipeline for an inbound event.

        This is the core method — stateless, deterministic ordering,
        all behavior delegated to plugins.
        """
        hook = self._pm.hook

        # 1. Resolve session
        session_id = await self._call_hook(hook.resolve_session, envelope=envelope)
        if not session_id:
            session_id = envelope.session_id
        logger.debug("Resolved session: %s", session_id)

        # 2. Load state — each plugin contributes its portion
        state = SimuTurnState(session_id=session_id)
        contributions = await self._call_hook(
            hook.load_state, envelope=envelope, session_id=session_id,
        )
        if isinstance(contributions, list):
            for contrib in contributions:
                if contrib is not None:
                    self._merge_state(state, contrib)

        # 3. Build prompt
        prompt = await self._call_hook(
            hook.build_prompt, envelope=envelope, session_id=session_id, state=state,
        )
        if prompt:
            state.system_prompt = prompt

        # 4. Run model (ReAct loop)
        result = await self._call_hook(
            hook.run_model,
            envelope=envelope, session_id=session_id, state=state, prompt=state.system_prompt,
        )
        logger.debug(
            "Model completed: %d chars output",
            len(getattr(result, "content", "") or ""),
        )

        # 5. Save state — each plugin persists its portion
        await self._call_hook(
            hook.save_state,
            envelope=envelope, session_id=session_id, state=state, result=result,
        )

        # 6. Dispatch outbound
        await self._call_hook(
            hook.dispatch_outbound,
            envelope=envelope, session_id=session_id, state=state, result=result,
        )

        return TurnResult(session_id=session_id, state=state, result=result)

    @staticmethod
    async def _call_hook(hook_method: Any, **kwargs: Any) -> Any:
        """Call a pluggy hook, awaiting any coroutine results.

        pluggy does not natively support async hooks — calling an async
        hookimpl returns an unawaited coroutine.  This wrapper detects
        and awaits them transparently.
        """
        results = hook_method(**kwargs)
        if isinstance(results, list):
            return [await r if inspect.iscoroutine(r) else r for r in results]
        if inspect.iscoroutine(results):
            return await results
        return results

    @staticmethod
    def _merge_state(state: SimuTurnState, contrib: Any) -> None:
        """Merge a plugin's load_state contribution into the shared state.

        Plugins return dicts with keys matching SimuTurnState fields.
        List fields are extended; scalar fields are overwritten.
        """
        if not isinstance(contrib, dict):
            return
        for key, value in contrib.items():
            if not hasattr(state, key):
                continue
            existing = getattr(state, key)
            if isinstance(existing, list) and isinstance(value, list):
                existing.extend(value)
            else:
                setattr(state, key, value)
