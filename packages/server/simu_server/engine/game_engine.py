"""GameEngine — top-level facade for state + tick + incidents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from simu_shared.models import Incident, TapeEvent
from simu_server.engine.incidents import IncidentSystem
from simu_server.engine.state import GameState
from simu_server.engine.tick import TickCoordinator
from simu_server.stores.database import Database


class GameEngine:
    """Combines GameState, TickCoordinator, and IncidentSystem."""

    def __init__(self, db: Database) -> None:
        self.state = GameState(db)
        self.incidents = IncidentSystem()
        self.tick_coordinator = TickCoordinator(self.state, self.incidents)

    async def initialize(self, initial_state_path: Path | None = None) -> None:
        await self.state.load(initial_state_path)

    async def tick(self, session_id: str) -> TapeEvent:
        return await self.tick_coordinator.tick(session_id)

    def query_state(self, path: str = "") -> dict[str, Any]:
        return self.state.query(path)

    def get_overview(self) -> dict[str, Any]:
        return self.state.get_overview()

    def add_incident(self, incident: Incident) -> None:
        self.incidents.add(incident)

    def list_incidents(self) -> list[dict[str, Any]]:
        return self.incidents.list_all()
