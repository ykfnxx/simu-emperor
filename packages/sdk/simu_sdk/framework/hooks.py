"""Hook specifications for the Bub-like pipeline.

Plugins implement these hooks via ``@hookimpl``.  The framework core
calls them in order during ``process_inbound``.
"""

from __future__ import annotations

from typing import Any

import pluggy

PROJECT_NAME = "simu_agent"

hookspec = pluggy.HookspecMarker(PROJECT_NAME)
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class SimuHookSpec:
    """Defines the pipeline hook points.

    Hooks are called in registration order.  ``firstresult=True`` means
    only the first non-None return is used; otherwise all results are
    collected into a list.
    """

    @hookspec(firstresult=True)
    def resolve_session(self, envelope: Any) -> str | None:
        """Determine the session ID for this inbound message.

        Returns:
            The session_id string, or None to use the envelope default.
        """

    @hookspec
    def load_state(self, envelope: Any, session_id: str) -> Any:
        """Load state needed for processing.

        Each plugin returns its contribution (e.g. tape events, context,
        memories).  Results are merged into SimuTurnState by the core.
        """

    @hookspec(firstresult=True)
    def build_prompt(self, envelope: Any, session_id: str, state: Any) -> str | None:
        """Build the system prompt for the LLM.

        Returns:
            The complete system prompt string.
        """

    @hookspec(firstresult=True)
    def run_model(self, envelope: Any, session_id: str, state: Any, prompt: str) -> Any:
        """Execute the LLM reasoning loop (ReAct).

        Returns:
            A result object (typically ReActResult) with model output.
        """

    @hookspec
    def save_state(self, envelope: Any, session_id: str, state: Any, result: Any) -> None:
        """Persist state after model execution.

        Called for each plugin to save its portion of state (tape events,
        memory updates, session summaries, etc.).
        """

    @hookspec
    def dispatch_outbound(self, envelope: Any, session_id: str, state: Any, result: Any) -> None:
        """Handle outbound actions after the pipeline completes.

        Used for routing responses, completing invocations, posting
        messages to the server, etc.
        """
