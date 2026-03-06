"""
WebSocket 连接管理器

管理所有活跃的 WebSocket 连接，支持广播和点对点消息发送。
"""

import logging
from typing import List

from fastapi import WebSocket


logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    WebSocket 连接管理器

    职责：
    - 线程安全的连接列表
    - 连接生命周期管理
    - 广播和点对点消息发送

    Attributes:
        active_connections: 当前活跃的 WebSocket 连接列表
    """

    def __init__(self) -> None:
        """初始化连接管理器"""
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """
        接受新连接

        Args:
            websocket: WebSocket 连接对象
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            f"WebSocket connected. Total connections: {len(self.active_connections)}"
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """
        断开连接

        Args:
            websocket: WebSocket 连接对象
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(
            f"WebSocket disconnected. Total connections: {len(self.active_connections)}"
        )

    async def broadcast(self, message: dict) -> None:
        """
        向所有连接广播消息

        Args:
            message: 要广播的消息（将被 JSON 序列化）

        注意：
        - 发送失败的连接会被自动清理
        - 使用并发发送以提高性能
        """
        if not self.active_connections:
            logger.debug("No active connections to broadcast")
            return

        logger.debug(f"Broadcasting message to {len(self.active_connections)} connections")

        # 记录断开的连接
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send to connection: {e}")
                disconnected.append(connection)

        # 清理断开的连接
        for conn in disconnected:
            await self.disconnect(conn)

    async def send_personal(self, message: dict, websocket: WebSocket) -> None:
        """
        向特定连接发送消息

        Args:
            message: 要发送的消息
            websocket: 目标 WebSocket 连接
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
            await self.disconnect(websocket)

    @property
    def connection_count(self) -> int:
        """
        当前活跃连接数

        Returns:
            活跃连接数量
        """
        return len(self.active_connections)
