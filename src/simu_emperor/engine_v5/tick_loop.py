import asyncio
import logging
from typing import Any, Callable

from simu_emperor.mq.publisher import MQPublisher
from simu_emperor.mq.event import Event
from simu_emperor.engine_v5.models import NationData, Incident
from simu_emperor.engine_v5 import economic


logger = logging.getLogger(__name__)


class TickLoop:
    def __init__(
        self,
        tick_interval: float,
        publisher: MQPublisher,
        incident_manager: Any,
        state: NationData | None = None,
        on_tick: Callable[[int], None] | None = None,
    ):
        self.tick_interval = tick_interval
        self.publisher = publisher
        self.incident_manager = incident_manager
        self.state = state
        self.on_tick = on_tick
        self._tick = 0
        self._running = False
        self._incidents: list[Incident] = []

    async def run(self) -> None:
        self._running = True
        logger.info(f"Tick loop started with interval {self.tick_interval}s")

        while self._running:
            await asyncio.sleep(self.tick_interval)

            self._tick += 1

            await self._process_tick()

            await self._broadcast_tick_completed()

            self._expire_incidents()

    async def _process_tick(self) -> None:
        if self.state is None:
            if self.on_tick:
                self.on_tick(self._tick)
        else:
            expired = economic.process_tick(self.state, self._incidents)
            self._incidents = [i for i in self._incidents if i.remaining_ticks > 0]

            if self.on_tick:
                self.on_tick(self._tick)

            if expired:
                logger.info(f"Expired incidents: {[i.incident_id for i in expired]}")

        logger.debug(f"Tick {self._tick} processed")

    async def _broadcast_tick_completed(self) -> None:
        event = Event(
            event_id="",
            event_type="TICK_COMPLETED",
            src="engine:*",
            dst=["broadcast:*"],
            session_id="system",
            payload={"tick": self._tick},
            timestamp="",
        )

        await self.publisher.publish_event(event)
        logger.debug(f"Broadcast TICK_COMPLETED for tick {self._tick}")

    def _expire_incidents(self) -> None:
        if self.incident_manager:
            self.incident_manager.expire_incidents(self._tick)

    def stop(self) -> None:
        self._running = False
        logger.info("Tick loop stopped")

    @property
    def tick(self) -> int:
        return self._tick

    def add_incident(self, incident: Incident) -> None:
        self._incidents.append(incident)
        logger.info(f"Incident added: {incident.incident_id}")

    def remove_incident(self, incident_id: str) -> None:
        self._incidents = [i for i in self._incidents if i.incident_id != incident_id]
        logger.info(f"Incident removed: {incident_id}")

    def get_active_incidents(self) -> list[Incident]:
        return self._incidents.copy()

    def get_state(self) -> NationData | None:
        return self.state
