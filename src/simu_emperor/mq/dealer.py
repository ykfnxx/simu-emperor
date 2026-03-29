"""
MQDealer - ZeroMQ DEALER socket封装

用于点对点请求/响应通信(Worker/Engine连接到Router)
"""

import asyncio
import logging

import zmq.asyncio

from simu_emperor.mq.event import Event


logger = logging.getLogger(__name__)


class MQDealer:
    """
    ZeroMQ DEALER socket封装

    用于:
    - Worker连接到Router
    - Engine连接到Router
    - Gateway连接到Router
    """

    def __init__(self, addr: str, identity: str | None = None):
        self.addr = addr
        self.identity = identity or ""

        self._ctx: zmq.asyncio.Context | None = None
        self._socket: zmq.asyncio.Socket | None = None
        self._connected = False

    async def connect(self) -> None:
        if self._connected:
            logger.warning(f"MQDealer already connected to {self.addr}")
            return

        self._ctx = zmq.asyncio.Context()
        self._socket = self._ctx.socket(zmq.DEALER)

        if self.identity:
            self._socket.setsockopt(zmq.IDENTITY, self.identity.encode())

        self._socket.connect(self.addr)
        self._connected = True

        logger.info(f"MQDealer connected to {self.addr}")

    async def send(self, data: str | bytes) -> None:
        if not self._connected or not self._socket:
            raise RuntimeError("MQDealer not connected")

        if isinstance(data, str):
            data = data.encode("utf-8")

        await self._socket.send(data)
        logger.debug(f"MQDealer sent {len(data)} bytes to {self.addr}")

    async def send_event(self, event: Event) -> None:
        await self.send(event.to_json())

    async def receive(self, timeout: float | None = None) -> str:
        if not self._connected or not self._socket:
            raise RuntimeError("MQDealer not connected")

        if timeout:
            data = await asyncio.wait_for(self._socket.recv(), timeout=timeout)
        else:
            data = await self._socket.recv()

        logger.debug(f"MQDealer received {len(data)} bytes from {self.addr}")
        return data.decode("utf-8")

    async def receive_event(self, timeout: float | None = None) -> Event:
        data = await self.receive(timeout=timeout)
        return Event.from_json(data)

    async def close(self) -> None:
        if self._socket:
            self._socket.close()
            self._socket = None

        if self._ctx:
            self._ctx.term()
            self._ctx = None

        self._connected = False
        logger.info(f"MQDealer disconnected from {self.addr}")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
