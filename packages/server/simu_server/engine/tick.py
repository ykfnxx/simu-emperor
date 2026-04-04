"""TickCoordinator — advances game time by one tick.

A tick represents one turn of the simulation.  The coordinator:
1. Applies province economic growth
2. Computes tax revenue and tribute
3. Applies incident effects
4. Increments the turn counter
5. Persists state and broadcasts TICK_COMPLETED to all Agents
"""

from __future__ import annotations

import logging
from decimal import Decimal

from simu_shared.constants import EventType
from simu_shared.models import NationData, TapeEvent
from simu_server.engine.incidents import IncidentSystem
from simu_server.engine.state import GameState

logger = logging.getLogger(__name__)


class TickCoordinator:
    """Advances the game by one tick."""

    def __init__(self, state: GameState, incidents: IncidentSystem) -> None:
        self._state = state
        self._incidents = incidents

    async def tick(self, session_id: str) -> TapeEvent:
        """Execute one tick and return the TICK_COMPLETED event."""
        nation = self._state.nation

        # 1. Province economic growth
        for province in nation.provinces.values():
            province.production_value *= Decimal("1") + province.base_production_growth
            province.population *= Decimal("1") + province.base_population_growth

        # 2. Tax collection
        total_tax = Decimal("0")
        for province in nation.provinces.values():
            tax = province.production_value * (nation.base_tax_rate + province.tax_modifier)
            tribute = tax * nation.tribute_rate
            province.stockpile += tax - tribute
            total_tax += tribute

        nation.imperial_treasury += total_tax - nation.fixed_expenditure

        # 3. Incident effects
        expired = self._incidents.apply_tick(nation)

        # 4. Increment turn
        nation.turn += 1

        # 5. Persist
        await self._state.save()

        logger.info("Tick %d completed. Treasury: %s", nation.turn, nation.imperial_treasury)

        # 6. Build event
        return TapeEvent(
            src="system:engine",
            dst=["*"],
            event_type=EventType.TICK_COMPLETED,
            payload={
                "turn": nation.turn,
                "imperial_treasury": str(nation.imperial_treasury),
                "expired_incidents": [i.title for i in expired],
            },
            session_id=session_id,
        )
