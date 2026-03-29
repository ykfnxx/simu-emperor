import asyncio
import json
import logging

from simu_emperor.mq.dealer import MQDealer
from simu_emperor.mq.subscriber import MQSubscriber
from simu_emperor.mq.event import Event
from simu_emperor.worker.agent_worker import AgentWorker


logger = logging.getLogger(__name__)


class WorkerProcess:
    def __init__(
        self,
        agent_id: str,
        router_addr: str = "ipc://@simu_router",
        broadcast_addr: str = "ipc://@simu_broadcast",
    ):
        self.agent_id = agent_id
        self.router_addr = router_addr
        self.broadcast_addr = broadcast_addr

        self.dealer: MQDealer | None = None
        self.subscriber: MQSubscriber | None = None
        self.agent_worker: AgentWorker | None = None
        self._running = False

    async def start(self) -> None:
        self.dealer = MQDealer(self.router_addr, identity=f"worker:{self.agent_id}")
        await self.dealer.connect()

        await self.dealer.send(json.dumps({"type": "REGISTER", "agent_id": self.agent_id}))

        self.subscriber = MQSubscriber(self.broadcast_addr)
        await self.subscriber.connect()
        self.subscriber.subscribe("")

        self.agent_worker = AgentWorker(
            agent_id=self.agent_id,
            dealer=self.dealer,
        )

        self._running = True
        logger.info(f"Worker process started for agent: {self.agent_id}")

        await asyncio.gather(
            self._receive_loop(),
            self._broadcast_loop(),
        )

    async def _receive_loop(self) -> None:
        while self._running:
            try:
                data = await asyncio.wait_for(self.dealer.receive(), timeout=1.0)

                msg = json.loads(data)

                if msg.get("type") == "REGISTER_ACK":
                    logger.info(f"Registration acknowledged: {msg.get('agent_id')}")
                    continue

                event = Event.from_dict(msg)
                await self.agent_worker.handle_event(event)

            except asyncio.TimeoutError:
                continue
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
            except Exception as e:
                logger.error(f"Error in receive loop: {e}")

    async def _broadcast_loop(self) -> None:
        while self._running:
            try:
                topic, data = await asyncio.wait_for(self.subscriber.receive(), timeout=1.0)

                event = Event.from_json(data)
                await self.agent_worker.handle_broadcast(event)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}")

    async def stop(self) -> None:
        self._running = False

        if self.dealer:
            await self.dealer.close()
        if self.subscriber:
            await self.subscriber.close()

        logger.info(f"Worker process stopped for agent: {self.agent_id}")
