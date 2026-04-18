"""SimuTapePlugin — load and save tape events through the pipeline."""

from __future__ import annotations

import logging
from typing import Any

from simu_sdk.framework.hooks import hookimpl
from simu_sdk.tape.manager import TapeManager

logger = logging.getLogger(__name__)


class SimuTapePlugin:
    """Handles tape event persistence in the Bub pipeline.

    - ``load_state``: fetches recent tape events for the session
    - ``save_state``: appends the response event to tape
    """

    def __init__(self, tape: TapeManager) -> None:
        self._tape = tape

    @hookimpl
    def resolve_session(self, envelope: Any) -> str | None:
        """Use the event's session_id as the pipeline session."""
        event = envelope.payload
        return getattr(event, "session_id", None)

    @hookimpl
    async def load_state(self, envelope: Any, session_id: str) -> dict:
        """Load recent tape events for context building."""
        # Append the incoming event to tape
        await self._tape.append(envelope.payload)
        return {}

    @hookimpl
    async def save_state(self, envelope: Any, session_id: str, state: Any, result: Any) -> None:
        """Persist the response event to tape."""
        if state.response_event is not None:
            await self._tape.append(state.response_event)
