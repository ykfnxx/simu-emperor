"""EventRouter — routes TapeEvents to Agent processes via SSE.

Each connected Agent maintains an SSE connection.  The router pushes
events to the correct Agent(s) based on the ``dst`` field.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from simu_shared.models import TapeEvent

logger = logging.getLogger(__name__)


class EventRouter:
    """Routes events to Agent SSE connections.

    Agents connect via ``GET /api/callback/events``.  The router keeps
    an ``asyncio.Queue`` per agent and pushes events into the matching
    queues.
    """

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[TapeEvent]] = {}

    def connect(self, agent_id: str) -> asyncio.Queue[TapeEvent]:
        """Register an SSE connection for *agent_id*. Returns the queue."""
        q: asyncio.Queue[TapeEvent] = asyncio.Queue(maxsize=100)
        self._queues[agent_id] = q
        logger.info("Agent %s connected to event stream", agent_id)
        return q

    def disconnect(self, agent_id: str) -> None:
        self._queues.pop(agent_id, None)
        logger.info("Agent %s disconnected from event stream", agent_id)

    async def route(self, event: TapeEvent) -> list[str]:
        """Route *event* to its destinations. Returns list of agent IDs that received it."""
        delivered: list[str] = []
        targets = self._resolve_targets(event)
        for agent_id in targets:
            q = self._queues.get(agent_id)
            if q is not None:
                try:
                    q.put_nowait(event)
                    delivered.append(agent_id)
                except asyncio.QueueFull:
                    logger.warning("Queue full for agent %s, dropping event", agent_id)
        return delivered

    async def broadcast(self, event: TapeEvent) -> list[str]:
        """Send *event* to all connected agents."""
        delivered: list[str] = []
        for agent_id, q in self._queues.items():
            try:
                q.put_nowait(event)
                delivered.append(agent_id)
            except asyncio.QueueFull:
                logger.warning("Queue full for agent %s, dropping event", agent_id)
        return delivered

    def connected_agents(self) -> list[str]:
        return list(self._queues)

    def _resolve_targets(self, event: TapeEvent) -> list[str]:
        """Resolve destination list to concrete agent IDs."""
        targets: list[str] = []
        for dst in event.dst:
            if dst == "*":
                return list(self._queues)
            if dst.startswith("agent:"):
                agent_id = dst.removeprefix("agent:")
                targets.append(agent_id)
        return targets
