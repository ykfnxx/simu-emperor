import asyncio
import json
import logging

import zmq.asyncio

from simu_emperor.mq.event import Event
from simu_emperor.router.routing_table import RoutingTable


logger = logging.getLogger(__name__)


class Router:
    def __init__(self, router_addr: str = "ipc://@simu_router"):
        self.router_addr = router_addr
        self.routing_table = RoutingTable()
        self._ctx: zmq.asyncio.Context | None = None
        self._socket: zmq.asyncio.Socket | None = None
        self._running = False

    async def start(self) -> None:
        self._ctx = zmq.asyncio.Context()
        self._socket = self._ctx.socket(zmq.ROUTER)
        self._socket.bind(self.router_addr)
        self._running = True

        logger.info(f"Router started at {self.router_addr}")

        await self._event_loop()

    async def _event_loop(self) -> None:
        while self._running:
            try:
                parts = await asyncio.wait_for(self._socket.recv_multipart(), timeout=1.0)

                if len(parts) != 2:
                    logger.warning(f"Invalid message format: {len(parts)} parts")
                    continue

                identity, data = parts

                try:
                    msg = json.loads(data.decode("utf-8"))

                    if msg.get("type") == "REGISTER":
                        await self._handle_register(identity, msg)
                    elif msg.get("type") == "UNREGISTER":
                        await self._handle_unregister(identity, msg)
                    else:
                        await self._route_event(identity, msg)

                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")

            except asyncio.TimeoutError:
                continue

    async def _handle_register(self, identity: bytes, msg: dict) -> None:
        agent_id = msg.get("agent_id")
        if not agent_id:
            logger.warning("REGISTER message missing agent_id")
            return

        self.routing_table.register(agent_id, identity)

        await self._socket.send_multipart(
            [identity, json.dumps({"type": "REGISTER_ACK", "agent_id": agent_id}).encode("utf-8")]
        )

    async def _handle_unregister(self, identity: bytes, msg: dict) -> None:
        agent_id = msg.get("agent_id")
        if agent_id:
            self.routing_table.unregister(agent_id)

    async def _route_event(self, sender_identity: bytes, event_dict: dict) -> None:
        try:
            event = Event.from_dict(event_dict)
        except Exception as e:
            logger.error(f"Invalid event format: {e}")
            return

        for dst in event.dst:
            await self._route_to_destination(dst, event)

    async def _route_to_destination(self, dst: str, event: Event) -> None:
        if dst.startswith("agent:"):
            agent_id = dst[6:]
            worker_identity = self.routing_table.get(agent_id)

            if worker_identity:
                await self._socket.send_multipart(
                    [worker_identity, event.to_json().encode("utf-8")]
                )
                logger.debug(f"Routed event to agent: {agent_id}")
            else:
                logger.warning(f"No worker for agent: {agent_id}")

        elif dst.startswith("engine:"):
            engine_identity = self.routing_table.get("engine:*")
            if engine_identity:
                await self._socket.send_multipart(
                    [engine_identity, event.to_json().encode("utf-8")]
                )

        elif dst.startswith("player:"):
            gateway_identity = self.routing_table.get("gateway:*")
            if gateway_identity:
                await self._socket.send_multipart(
                    [gateway_identity, event.to_json().encode("utf-8")]
                )

        elif dst.startswith("broadcast:"):
            for agent_id in self.routing_table.list_all():
                if agent_id.startswith("agent:"):
                    worker_identity = self.routing_table.get(agent_id)
                    if worker_identity:
                        await self._socket.send_multipart(
                            [worker_identity, event.to_json().encode("utf-8")]
                        )

    async def stop(self) -> None:
        self._running = False

        if self._socket:
            self._socket.close()
            self._socket = None

        if self._ctx:
            self._ctx.term()
            self._ctx = None

        logger.info("Router stopped")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
