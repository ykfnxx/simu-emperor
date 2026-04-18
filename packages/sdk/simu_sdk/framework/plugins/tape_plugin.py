"""SimuTapePlugin — load and save tape events through the pipeline."""

from __future__ import annotations

import logging
from typing import Any

from bub.hookspecs import hookimpl
from simu_sdk.tape.manager import TapeManager

logger = logging.getLogger(__name__)


class SimuTapePlugin:
    """Handles tape event persistence in the Bub pipeline.

    - ``resolve_session``: extracts session_id from the inbound event
    - ``load_state``: appends incoming event to tape
    - ``save_state``: appends the response event to tape
    """

    def __init__(self, tape: TapeManager) -> None:
        self._tape = tape

    @hookimpl
    def resolve_session(self, message: Any) -> str | None:
        """Use the event's session_id as the pipeline session."""
        return getattr(message, "session_id", None)

    @hookimpl
    async def load_state(self, message: Any, session_id: str) -> dict:
        """Append the incoming event to tape and store it in state."""
        await self._tape.append(message)
        return {"_inbound_event": message}

    @hookimpl
    async def save_state(
        self, session_id: str, state: dict, message: Any, model_output: str,
    ) -> None:
        """Persist the response event to tape."""
        response_event = state.get("response_event")
        if response_event is not None:
            await self._tape.append(response_event)
