"""GameEngine — top-level facade for state + tick + incidents."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from simu_shared.models import Incident, TapeEvent
from simu_server.engine.incidents import IncidentSystem
from simu_server.engine.state import GameState
from simu_server.engine.tick import TickCoordinator
from simu_server.stores.database import Database
from simu_server.stores.tick_history import TickHistoryStore


class GameEngine:
    """Combines GameState, TickCoordinator, and IncidentSystem.

    A single asyncio.Lock serializes tick and state mutations to prevent
    concurrent access from MCP queries and tick execution.
    """

    def __init__(self, db: Database) -> None:
        self.state = GameState(db)
        self.incidents = IncidentSystem(db)
        self.tick_history = TickHistoryStore(db)
        self.tick_coordinator = TickCoordinator(self.state, self.incidents)
        self._lock = asyncio.Lock()

    async def initialize(self, initial_state_path: Path | None = None) -> None:
        await self.state.load(initial_state_path)
        await self.incidents.load()

    async def tick(self, session_id: str) -> TapeEvent:
        async with self._lock:
            event = await self.tick_coordinator.tick(session_id)
            await self.tick_history.save_snapshot(self.state.nation)
            return event

    def query_state(self, path: str = "") -> dict[str, Any]:
        return self.state.query(path)

    def get_overview(self) -> dict[str, Any]:
        return self.state.get_overview()

    async def add_incident(self, incident: Incident) -> None:
        async with self._lock:
            await self.incidents.add(incident)

    def list_incidents(self) -> list[dict[str, Any]]:
        return self.incidents.list_all()
