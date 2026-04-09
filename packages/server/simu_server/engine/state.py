"""GameState — manages the nation and province data.

Persists state in the Server's SQLite database and provides query APIs
scoped by data access paths.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from simu_shared.models import NationData
from simu_server.stores.database import Database

logger = logging.getLogger(__name__)


class GameState:
    """In-memory game state with SQLite persistence."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self.nation: NationData = NationData()

    async def load(self, initial_state_path: Path | None = None) -> None:
        """Load state from DB, or initialize from a JSON file if DB is empty."""
        logger.info(
            "GameState.load called with initial_state_path=%s",
            initial_state_path,
        )
        cursor = await self._db.conn.execute(
            "SELECT value FROM game_state WHERE key = 'nation'",
        )
        row = await cursor.fetchone()
        need_file_init = False

        if row:
            loaded = NationData.model_validate_json(row[0])
            if loaded.provinces:
                self.nation = loaded
                logger.info("Game state loaded from DB (turn %d)", self.nation.turn)
                return
            logger.warning(
                "DB state has no provinces (turn %d) — re-initializing from file",
                loaded.turn,
            )
            need_file_init = True
        else:
            need_file_init = True

        if need_file_init and initial_state_path and initial_state_path.exists():
            data = json.loads(initial_state_path.read_text(encoding="utf-8"))
            # Support both flat and nested JSON formats.
            # Nested: {"nation": {...}, "provinces": {...}}
            # Flat: {"turn": 0, "provinces": {...}, ...}
            if "nation" in data and "provinces" in data and "turn" not in data:
                nation_dict = {**data["nation"], "provinces": data["provinces"]}
            else:
                nation_dict = data
            self.nation = NationData.model_validate(nation_dict)
            await self.save()
            logger.info("Game state initialized from %s", initial_state_path)
        else:
            logger.info("Starting with empty game state")

    async def save(self) -> None:
        """Persist current state to SQLite."""
        await self._db.conn.execute(
            "INSERT OR REPLACE INTO game_state (key, value) VALUES (?, ?)",
            ("nation", self.nation.model_dump_json()),
        )
        await self._db.conn.commit()

    def query(self, path: str = "") -> dict[str, Any]:
        """Query state by dotted path.  Empty path returns full state."""
        data = json.loads(self.nation.model_dump_json())
        if not path:
            return data
        parts = path.split(".")
        current: Any = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return {}
            if current is None:
                return {}
        if isinstance(current, dict):
            return current
        return {"value": current}

    def get_overview(self) -> dict[str, Any]:
        """Return a high-level overview for the frontend."""
        n = self.nation
        return {
            "turn": n.turn,
            "imperial_treasury": str(n.imperial_treasury),
            "base_tax_rate": str(n.base_tax_rate),
            "tribute_rate": str(n.tribute_rate),
            "province_count": len(n.provinces),
            "total_population": str(sum(p.population for p in n.provinces.values())),
            "total_production": str(sum(p.production_value for p in n.provinces.values())),
        }
