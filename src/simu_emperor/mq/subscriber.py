"""
MQSubscriber - ZeroMQ SUB socket封装

用于订阅广播消息(如Worker订阅Engine的tick事件)
"""

import logging

import zmq.asyncio

from simu_emperor.mq.event import Event


logger = logging.getLogger(__name__)


class MQSubscriber:
    """
    ZeroMQ SUB socket封装

    用于:
    - Worker订阅Engine的tick事件
    - 其他需要订阅广播的场景
    """

    def __init__(self, addr: str):
        self.addr = addr

        self._ctx: zmq.asyncio.Context | None = None
        self._socket: zmq.asyncio.Socket | None = None
        self._connected = False

    async def connect(self) -> None:
        if self._connected:
            logger.warning(f"MQSubscriber already connected to {self.addr}")
            return

        self._ctx = zmq.asyncio.Context()
        self._socket = self._ctx.socket(zmq.SUB)
        self._socket.connect(self.addr)
        self._connected = True

        logger.info(f"MQSubscriber connected to {self.addr}")

    def subscribe(self, topic: str) -> None:
        if not self._connected or not self._socket:
            raise RuntimeError("MQSubscriber not connected")

        self._socket.setsockopt(zmq.SUBSCRIBE, topic.encode("utf-8"))
        logger.debug(f"MQSubscriber subscribed to topic '{topic}'")

    async def receive(self) -> tuple[str, str]:
        if not self._connected or not self._socket:
            raise RuntimeError("MQSubscriber not connected")

        parts = await self._socket.recv_multipart()

        if len(parts) != 2:
            raise ValueError(f"Expected 2 parts, got {len(parts)}")

        topic = parts[0].decode("utf-8")
        data = parts[1].decode("utf-8")

        logger.debug(f"MQSubscriber received from topic '{topic}': {len(data)} bytes")

        return topic, data

    async def receive_event(self) -> tuple[str, Event]:
        topic, data = await self.receive()
        event = Event.from_json(data)
        return topic, event

    async def close(self) -> None:
        if self._socket:
            self._socket.close()
            self._socket = None

        if self._ctx:
            self._ctx.term()
            self._ctx = None

        self._connected = False
        logger.info(f"MQSubscriber disconnected from {self.addr}")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
