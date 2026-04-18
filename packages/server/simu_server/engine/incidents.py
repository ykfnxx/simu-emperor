"""IncidentSystem — time-limited events with economic effects.

Incidents apply one-time additive changes and ongoing multiplicative
factors to the game state.  Each tick decrements remaining_ticks; when
it reaches zero the incident expires.

Incidents are persisted to SQLite so they survive server restarts.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from simu_shared.models import Effect, Incident, NationData
from simu_server.stores.database import Database

logger = logging.getLogger(__name__)


class IncidentSystem:
    """Manages active incidents and applies their effects each tick."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._incidents: list[Incident] = []

    async def load(self) -> None:
        """Load active incidents from SQLite on startup."""
        cursor = await self._db.conn.execute(
            "SELECT data FROM incidents WHERE remaining_ticks > 0",
        )
        rows = await cursor.fetchall()
        for (data,) in rows:
            self._incidents.append(Incident.model_validate_json(data))
        if self._incidents:
            logger.info("Restored %d active incidents from database", len(self._incidents))

    @property
    def active(self) -> list[Incident]:
        return [i for i in self._incidents if i.remaining_ticks > 0]

    async def add(self, incident: Incident) -> None:
        self._incidents.append(incident)
        await self._db.conn.execute(
            "INSERT OR REPLACE INTO incidents (incident_id, data, remaining_ticks) VALUES (?, ?, ?)",
            (incident.incident_id, incident.model_dump_json(), incident.remaining_ticks),
        )
        await self._db.conn.commit()
        logger.info("Incident added: %s (%d ticks)", incident.title, incident.remaining_ticks)

    async def apply_tick(self, nation: NationData) -> list[Incident]:
        """Apply all active effects and tick down.  Returns newly expired incidents."""
        expired: list[Incident] = []

        for incident in self._incidents:
            if incident.remaining_ticks <= 0:
                continue

            for effect in incident.effects:
                self._apply_effect(effect, nation, incident)

            # Mark one-time adds as applied
            incident.applied = True
            incident.remaining_ticks -= 1

            if incident.remaining_ticks <= 0:
                expired.append(incident)
                logger.info("Incident expired: %s", incident.title)

        # Persist updated state
        for incident in self._incidents:
            await self._db.conn.execute(
                "UPDATE incidents SET data = ?, remaining_ticks = ? WHERE incident_id = ?",
                (incident.model_dump_json(), incident.remaining_ticks, incident.incident_id),
            )
        await self._db.conn.commit()

        return expired

    def list_all(self) -> list[dict[str, Any]]:
        return [i.model_dump() for i in self._incidents]

    @staticmethod
    def _apply_effect(effect: Effect, nation: NationData, incident: Incident) -> None:
        """Apply a single effect to the nation state."""
        parts = effect.target_path.split(".")
        if not parts:
            return

        # Navigate to the target field
        if parts[0] == "provinces" and len(parts) >= 3:
            province_id = parts[1]
            field_name = parts[2]
            province = nation.provinces.get(province_id)
            if province is None:
                return
            _apply_numeric(province, field_name, effect, incident.applied)
        elif parts[0] == "nation" and len(parts) >= 2:
            field_name = parts[1]
            _apply_numeric(nation, field_name, effect, incident.applied)


def _apply_numeric(obj: Any, field: str, effect: Effect, already_applied: bool) -> None:
    """Apply an additive or multiplicative change to a numeric field."""
    current = getattr(obj, field, None)
    if current is None or not isinstance(current, Decimal):
        return

    if effect.add is not None and not already_applied:
        setattr(obj, field, current + effect.add)
    elif effect.factor is not None:
        setattr(obj, field, current * (Decimal("1") + effect.factor))
