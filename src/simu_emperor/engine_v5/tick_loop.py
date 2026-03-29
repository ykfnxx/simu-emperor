import asyncio
import logging
from typing import Any, Callable

from simu_emperor.mq.publisher import MQPublisher
from simu_emperor.mq.event import Event


logger = logging.getLogger(__name__)


class TickLoop:
    def __init__(
        self,
        tick_interval: float,
        publisher: MQPublisher,
        incident_manager: Any,
        on_tick: Callable[[int], None] | None = None,
    ):
        self.tick_interval = tick_interval
        self.publisher = publisher
        self.incident_manager = incident_manager
        self.on_tick = on_tick
        self._tick = 0
        self._running = False

    async def run(self) -> None:
        self._running = True
        logger.info(f"Tick loop started with interval {self.tick_interval}s")

        while self._running:
            await asyncio.sleep(self.tick_interval)

            self._tick += 1

            await self._process_tick()

            await self._broadcast_tick_completed()

            self.incident_manager.expire_incidents(self._tick)

    async def _process_tick(self) -> None:
        if self.on_tick:
            self.on_tick(self._tick)

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

    def stop(self) -> None:
        self._running = False
        logger.info("Tick loop stopped")

    @property
    def tick(self) -> int:
        return self._tick
