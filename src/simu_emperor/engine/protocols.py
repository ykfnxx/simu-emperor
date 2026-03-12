"""Repository protocols for dependency inversion.

Defines interfaces that the Core Layer depends on.
Implementations are provided by upper layers (Persistence, Application).
"""

from typing import Protocol

from simu_emperor.engine.models.base_data import NationData


class GameStateRepository(Protocol):
    """Protocol for game state persistence.

    The Core Layer (TickCoordinator) depends on this Protocol,
    not the concrete GameRepository implementation.
    """

    async def save_nation_data(self, nation: NationData) -> None:
        """Persist game state.

        Args:
            nation: NationData to persist
        """
        ...
