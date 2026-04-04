"""IncidentSystem — time-limited events with economic effects.

Incidents apply one-time additive changes and ongoing multiplicative
factors to the game state.  Each tick decrements remaining_ticks; when
it reaches zero the incident expires.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from simu_shared.models import Effect, Incident, NationData

logger = logging.getLogger(__name__)


class IncidentSystem:
    """Manages active incidents and applies their effects each tick."""

    def __init__(self) -> None:
        self._incidents: list[Incident] = []

    @property
    def active(self) -> list[Incident]:
        return [i for i in self._incidents if i.remaining_ticks > 0]

    def add(self, incident: Incident) -> None:
        self._incidents.append(incident)
        logger.info("Incident added: %s (%d ticks)", incident.title, incident.remaining_ticks)

    def apply_tick(self, nation: NationData) -> list[Incident]:
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
