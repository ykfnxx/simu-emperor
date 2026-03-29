"""
MQPublisher - ZeroMQ PUB socket封装

用于广播消息(如Engine广播tick事件)
"""

import logging

import zmq.asyncio

from simu_emperor.mq.event import Event


logger = logging.getLogger(__name__)


class MQPublisher:
    """
    ZeroMQ PUB socket封装

    用于:
    - Engine广播TICK_COMPLETED事件
    - 其他需要广播的场景
    """

    def __init__(self, addr: str):
        self.addr = addr

        self._ctx: zmq.asyncio.Context | None = None
        self._socket: zmq.asyncio.Socket | None = None
        self._bound = False

    async def bind(self) -> None:
        if self._bound:
            logger.warning(f"MQPublisher already bound to {self.addr}")
            return

        self._ctx = zmq.asyncio.Context()
        self._socket = self._ctx.socket(zmq.PUB)
        self._socket.bind(self.addr)
        self._bound = True

        logger.info(f"MQPublisher bound to {self.addr}")

    async def publish(self, topic: str, data: str | bytes) -> None:
        if not self._bound or not self._socket:
            raise RuntimeError("MQPublisher not bound")

        if isinstance(data, str):
            data = data.encode("utf-8")

        await self._socket.send_multipart([topic.encode("utf-8"), data])
        logger.debug(f"MQPublisher published to topic '{topic}': {len(data)} bytes")

    async def publish_event(self, event: Event, topic: str | None = None) -> None:
        if topic is None:
            topic = event.event_type
        await self.publish(topic, event.to_json())

    async def close(self) -> None:
        if self._socket:
            self._socket.close()
            self._socket = None

        if self._ctx:
            self._ctx.term()
            self._ctx = None

        self._bound = False
        logger.info(f"MQPublisher unbound from {self.addr}")

    async def __aenter__(self):
        await self.bind()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
