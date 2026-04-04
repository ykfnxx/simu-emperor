"""ContextManager — builds the LLM context window from local Tape events.

Implements a sliding-window strategy with optional LLM-based summarization
when the token budget is exceeded.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from simu_shared.models import ContextConfig, TapeEvent
from simu_sdk.tape.manager import TapeManager

logger = logging.getLogger(__name__)


@dataclass
class ContextWindow:
    """The assembled context ready for the LLM prompt."""

    events: list[TapeEvent] = field(default_factory=list)
    summary: str = ""
    total_events: int = 0


class ContextManager:
    """Builds a bounded context window from local Tape.

    When the event count exceeds ``keep_recent_events``, older events
    are summarized into a compact text block.  The summary is generated
    by a caller-supplied ``summarize_fn`` (typically the Agent's own LLM).
    """

    def __init__(
        self,
        tape: TapeManager,
        config: ContextConfig,
    ) -> None:
        self._tape = tape
        self._config = config
        self._summaries: dict[str, str] = {}  # session_id → running summary

    async def get_context(self, session_id: str) -> ContextWindow:
        """Return the most recent events, plus a summary of older ones."""
        total = await self._tape.count(session_id)
        recent = await self._tape.query(
            session_id,
            limit=self._config.keep_recent_events,
        )

        # If we fetched fewer than total, there are older events to summarize
        summary = self._summaries.get(session_id, "")
        if total > len(recent) and not summary:
            # Summarization will be triggered externally when needed
            logger.debug(
                "Session %s has %d events but summary not yet generated",
                session_id, total,
            )

        return ContextWindow(
            events=recent,
            summary=summary,
            total_events=total,
        )

    def set_summary(self, session_id: str, summary: str) -> None:
        """Store a compressed summary for older events in a session."""
        self._summaries[session_id] = summary

    @property
    def needs_compression(self) -> bool:
        """Placeholder — compression trigger logic."""
        return False
