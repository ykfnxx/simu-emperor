"""QueueController — per-agent FIFO queue with concurrency control.

Each Agent processes one invocation at a time.  New events are queued
until the current invocation completes.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Awaitable

from simu_shared.models import TapeEvent

logger = logging.getLogger(__name__)


class QueueController:
    """Per-agent event queue with serial dispatch."""

    def __init__(self, max_depth: int = 10) -> None:
        self._max_depth = max_depth
        self._queues: dict[str, asyncio.Queue[TapeEvent]] = defaultdict(
            lambda: asyncio.Queue(maxsize=max_depth),
        )
        self._processing: set[str] = set()
        self._dispatch_fn: Callable[[str, TapeEvent], Awaitable[None]] | None = None

    def set_dispatcher(self, fn: Callable[[str, TapeEvent], Awaitable[None]]) -> None:
        """Set the function called to actually dispatch events to Agents."""
        self._dispatch_fn = fn

    async def enqueue(self, agent_id: str, event: TapeEvent) -> bool:
        """Enqueue an event for *agent_id*.  Returns False if queue is full."""
        q = self._queues[agent_id]
        if q.full():
            logger.warning("Queue full for agent %s, rejecting event", agent_id)
            return False
        await q.put(event)
        # Kick off processing if not already running.
        # Add to _processing BEFORE creating the task to prevent the TOCTOU
        # race where two enqueue() calls both see agent_id not in _processing.
        if agent_id not in self._processing:
            self._processing.add(agent_id)
            asyncio.create_task(self._process_loop(agent_id))
        return True

    async def _process_loop(self, agent_id: str) -> None:
        """Drain the queue for *agent_id*, one event at a time."""

        try:
            q = self._queues[agent_id]
            while not q.empty():
                event = await q.get()
                if self._dispatch_fn:
                    try:
                        await self._dispatch_fn(agent_id, event)
                    except Exception:
                        logger.exception("Dispatch failed for agent %s", agent_id)
                q.task_done()
        finally:
            self._processing.discard(agent_id)

    def queue_size(self, agent_id: str) -> int:
        return self._queues[agent_id].qsize() if agent_id in self._queues else 0
