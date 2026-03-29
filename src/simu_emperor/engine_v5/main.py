import asyncio
import json
import logging

from simu_emperor.mq.dealer import MQDealer
from simu_emperor.mq.publisher import MQPublisher
from simu_emperor.mq.event import Event
from simu_emperor.engine_v5.tick_loop import TickLoop
from simu_emperor.engine_v5.incident_manager import IncidentManager


logger = logging.getLogger(__name__)


class EngineProcess:
    def __init__(
        self,
        router_addr: str = "ipc://@simu_router",
        broadcast_addr: str = "ipc://@simu_broadcast",
        tick_interval: float = 5.0,
    ):
        self.router_addr = router_addr
        self.broadcast_addr = broadcast_addr
        self.tick_interval = tick_interval

        self.dealer: MQDealer | None = None
        self.publisher: MQPublisher | None = None
        self.tick_loop: TickLoop | None = None
        self.incident_manager: IncidentManager | None = None
        self._running = False

    async def start(self) -> None:
        self.dealer = MQDealer(self.router_addr, identity="engine:*")
        await self.dealer.connect()

        await self.dealer.send(json.dumps({"type": "REGISTER", "agent_id": "engine:*"}))

        self.publisher = MQPublisher(self.broadcast_addr)
        await self.publisher.bind()

        self.incident_manager = IncidentManager()
        self.tick_loop = TickLoop(
            tick_interval=self.tick_interval,
            publisher=self.publisher,
            incident_manager=self.incident_manager,
        )

        self._running = True
        logger.info("Engine process started")

        await asyncio.gather(
            self._receive_loop(),
            self.tick_loop.run(),
        )

    async def _receive_loop(self) -> None:
        while self._running:
            try:
                data = await asyncio.wait_for(self.dealer.receive(), timeout=1.0)

                msg = json.loads(data)
                await self._handle_message(msg)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in receive loop: {e}")

    async def _handle_message(self, msg: dict) -> None:
        msg_type = msg.get("type")

        if msg_type == "CREATE_INCIDENT":
            await self.incident_manager.create_incident(msg.get("incident", {}))
        elif msg_type == "RESOLVE_INCIDENT":
            await self.incident_manager.resolve_incident(msg.get("incident_id"))

    async def stop(self) -> None:
        self._running = False

        if self.tick_loop:
            self.tick_loop.stop()

        if self.dealer:
            await self.dealer.close()

        if self.publisher:
            await self.publisher.close()

        logger.info("Engine process stopped")
