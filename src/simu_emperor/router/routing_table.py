import logging
from typing import Any


logger = logging.getLogger(__name__)


class RoutingTable:
    def __init__(self):
        self._table: dict[str, bytes] = {}

    def register(self, agent_id: str, identity: bytes) -> None:
        self._table[agent_id] = identity
        logger.info(f"Agent registered: {agent_id}")

    def unregister(self, agent_id: str) -> None:
        if agent_id in self._table:
            del self._table[agent_id]
            logger.info(f"Agent unregistered: {agent_id}")

    def get(self, agent_id: str) -> bytes | None:
        return self._table.get(agent_id)

    def has(self, agent_id: str) -> bool:
        return agent_id in self._table

    def list_all(self) -> list[str]:
        return list(self._table.keys())

    def clear(self) -> None:
        self._table.clear()
        logger.info("Routing table cleared")
