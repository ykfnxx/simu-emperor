"""
Unit tests for ConnectionManager
"""

import pytest

from simu_emperor.adapters.web.connection_manager import ConnectionManager


class MockWebSocket:
    """模拟 WebSocket 连接"""

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.accepted = False
        self.sent_messages = []
        self.closed = False

    async def accept(self):
        """接受连接"""
        self.accepted = True

    async def send_json(self, message: dict):
        """发送 JSON 消息"""
        if self.closed:
            raise ConnectionError("WebSocket is closed")
        self.sent_messages.append(message)

    def close(self):
        """关闭连接（同步方法）"""
        self.closed = True


class TestConnectionManager:
    """测试 ConnectionManager 类"""

    @pytest.mark.asyncio
    async def test_connect(self):
        """测试连接"""
        manager = ConnectionManager()
        ws = MockWebSocket("client1")

        await manager.connect(ws)

        assert ws.accepted
        assert manager.connection_count == 1
        assert ws in manager.active_connections

    @pytest.mark.asyncio
    async def test_connect_multiple(self):
        """测试多个连接"""
        manager = ConnectionManager()
        ws1 = MockWebSocket("client1")
        ws2 = MockWebSocket("client2")

        await manager.connect(ws1)
        await manager.connect(ws2)

        assert manager.connection_count == 2
        assert ws1 in manager.active_connections
        assert ws2 in manager.active_connections

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """测试断开连接"""
        manager = ConnectionManager()
        ws = MockWebSocket("client1")

        await manager.connect(ws)
        assert manager.connection_count == 1

        await manager.disconnect(ws)
        assert manager.connection_count == 0
        assert ws not in manager.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_non_existent(self):
        """测试断开不存在的连接"""
        manager = ConnectionManager()
        ws = MockWebSocket("client1")

        # 不应该抛出异常
        await manager.disconnect(ws)
        assert manager.connection_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_single_connection(self):
        """测试向单个连接广播"""
        manager = ConnectionManager()
        ws = MockWebSocket("client1")

        await manager.connect(ws)

        message = {"kind": "chat", "data": {"text": "test"}}
        await manager.broadcast(message)

        assert len(ws.sent_messages) == 1
        assert ws.sent_messages[0] == message

    @pytest.mark.asyncio
    async def test_broadcast_multiple_connections(self):
        """测试向多个连接广播"""
        manager = ConnectionManager()
        ws1 = MockWebSocket("client1")
        ws2 = MockWebSocket("client2")

        await manager.connect(ws1)
        await manager.connect(ws2)

        message = {"kind": "chat", "data": {"text": "test"}}
        await manager.broadcast(message)

        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1
        assert ws1.sent_messages[0] == message
        assert ws2.sent_messages[0] == message

    @pytest.mark.asyncio
    async def test_broadcast_no_connections(self):
        """测试向空连接列表广播"""
        manager = ConnectionManager()

        # 不应该抛出异常
        message = {"kind": "chat", "data": {"text": "test"}}
        await manager.broadcast(message)

    @pytest.mark.asyncio
    async def test_broadcast_auto_cleanup_failed_connections(self):
        """测试广播时自动清理失败的连接"""
        manager = ConnectionManager()
        ws1 = MockWebSocket("client1")
        ws2 = MockWebSocket("client2")

        await manager.connect(ws1)
        await manager.connect(ws2)

        # 关闭 ws2，模拟发送失败
        ws2.close()

        message = {"kind": "chat", "data": {"text": "test"}}
        await manager.broadcast(message)

        # ws1 应该收到消息
        assert len(ws1.sent_messages) == 1

        # ws2 应该被自动清理
        assert manager.connection_count == 1
        assert ws1 in manager.active_connections
        assert ws2 not in manager.active_connections

    @pytest.mark.asyncio
    async def test_send_personal(self):
        """测试发送个人消息"""
        manager = ConnectionManager()
        ws1 = MockWebSocket("client1")
        ws2 = MockWebSocket("client2")

        await manager.connect(ws1)
        await manager.connect(ws2)

        message = {"kind": "error", "data": {"message": "test error"}}
        await manager.send_personal(message, ws1)

        # 只有 ws1 收到消息
        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 0
        assert ws1.sent_messages[0] == message

    @pytest.mark.asyncio
    async def test_send_personal_failed_cleanup(self):
        """测试个人消息发送失败时清理连接"""
        manager = ConnectionManager()
        ws = MockWebSocket("client1")

        await manager.connect(ws)
        assert manager.connection_count == 1

        # 关闭连接，模拟发送失败
        ws.close()

        message = {"kind": "error", "data": {"message": "test error"}}
        await manager.send_personal(message, ws)

        # 连接应该被清理
        assert manager.connection_count == 0

    @pytest.mark.asyncio
    async def test_connection_count_property(self):
        """测试连接数属性"""
        manager = ConnectionManager()

        assert manager.connection_count == 0

        ws1 = MockWebSocket("client1")
        await manager.connect(ws1)
        assert manager.connection_count == 1

        ws2 = MockWebSocket("client2")
        await manager.connect(ws2)
        assert manager.connection_count == 2

        await manager.disconnect(ws1)
        assert manager.connection_count == 1
