"""
Integration tests for Web Adapter

测试前后端完整流程，包括 WebSocket 连接、REST API、消息发送接收等。
"""

import pytest
import asyncio
from fastapi.testclient import TestClient

from simu_emperor.adapters.web.server import app


class TestWebAPIIntegration:
    """Web API 集成测试"""

    # TestClient 的异步清理在测试环境中有问题
    # 这些测试需要在手动测试中验证
    @pytest.mark.skip(reason="TestClient cleanup issue in test environment")
    def test_command_validation(self):
        """测试命令验证（缺少 agent 字段）"""
        with TestClient(app) as client:
            response = client.post("/api/command", json={"command": "test command"})

            # 应该返回 422 验证错误
            assert response.status_code == 422


class TestWebSocketIntegration:
    """WebSocket 集成测试"""

    def test_websocket_connection(self):
        """测试 WebSocket 连接建立"""
        client = TestClient(app)

        with client.websocket_connect("/ws") as websocket:
            # 连接成功，无异常
            pass

    def test_websocket_send_command(self):
        """测试通过 WebSocket 发送命令"""
        client = TestClient(app)

        with client.websocket_connect("/ws") as websocket:
            # 发送命令消息
            websocket.send_json({"type": "command", "agent": "test_agent", "text": "test command"})

            # 发送成功，无异常
            pass

    def test_websocket_send_chat(self):
        """测试通过 WebSocket 发送聊天消息"""
        client = TestClient(app)

        with client.websocket_connect("/ws") as websocket:
            # 发送聊天消息
            websocket.send_json({"type": "chat", "agent": "test_agent", "text": "hello"})

            # 发送成功，无异常
            pass

    def test_websocket_invalid_message_type(self):
        """测试发送无效消息类型"""
        client = TestClient(app)

        with client.websocket_connect("/ws") as websocket:
            # 发送无效消息类型
            websocket.send_json({"type": "invalid_type", "text": "test"})

            # 应该被处理（不会崩溃）
            pass

    def test_multiple_websocket_connections(self):
        """测试多个 WebSocket 连接"""
        client = TestClient(app)

        # 模拟多个连接
        connections = []
        for _ in range(3):
            ws = client.websocket_connect("/ws")
            ws.__enter__()
            connections.append(ws)

        # 所有连接都应该成功
        assert len(connections) == 3

        # 清理
        for ws in connections:
            ws.__exit__(None, None, None)


class TestMessageFlowIntegration:
    """消息流程集成测试"""

    @pytest.mark.asyncio
    async def test_message_converter_integration(self):
        """测试 MessageConverter 与 WebSocket 的集成"""
        from simu_emperor.adapters.web.message_converter import MessageConverter
        from simu_emperor.event_bus.event import Event
        from simu_emperor.event_bus.event_types import EventType

        converter = MessageConverter()

        # 测试 RESPONSE 事件转换
        event = Event(
            src="agent:governor_zhili",
            dst=["player:web"],
            type=EventType.RESPONSE,
            payload={"narrative": "测试消息"},
            session_id="session:web:test",
        )

        result = await converter.convert(event)

        assert result is not None
        assert result["kind"] == "chat"
        assert result["data"]["text"] == "测试消息"

    def test_connection_manager_broadcast(self):
        """测试 ConnectionManager 广播功能"""
        from simu_emperor.adapters.web.connection_manager import ConnectionManager

        manager = ConnectionManager()

        # 创建模拟 WebSocket 连接
        class MockWebSocket:
            def __init__(self):
                self.messages = []

            async def accept(self):
                pass

            async def send_json(self, message):
                self.messages.append(message)

        # 创建多个连接
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        # 异步连接
        asyncio.run(manager.connect(ws1))
        asyncio.run(manager.connect(ws2))

        # 广播消息
        message = {"kind": "test", "data": {"text": "broadcast"}}
        asyncio.run(manager.broadcast(message))

        # 验证所有连接都收到消息
        assert len(ws1.messages) == 1
        assert len(ws2.messages) == 1
        assert ws1.messages[0] == message
        assert ws2.messages[0] == message

        # 清理
        asyncio.run(manager.disconnect(ws1))
        asyncio.run(manager.disconnect(ws2))


class TestFullWorkflow:
    """完整工作流测试"""

    def test_client_lifecycle(self):
        """测试客户端生命周期"""
        from simu_emperor.adapters.web.game_instance import WebGameInstance
        from simu_emperor.config import GameConfig
        import tempfile
        from pathlib import Path

        # 创建临时目录
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # 创建测试配置 - 使用 Pydantic 模型
            from simu_emperor.config import LLMConfig, MemoryConfig

            settings = GameConfig(
                data_dir=str(tmp_path / "data"),
                log_dir=str(tmp_path / "logs"),
                llm=LLMConfig(provider="mock", api_key="test", model="test"),
                memory=MemoryConfig(enabled=False),
            )

            instance = WebGameInstance(settings)

            # 验证初始化 (V4架构：不再有player_id和session_id属性)
            assert instance.settings == settings
            assert instance._running is False
            assert instance.services is None  # 服务未启动

    def test_server_startup(self):
        """测试服务器启动"""
        client = TestClient(app)

        # 服务器应该正常启动
        # health endpoint 应该可访问
        response = client.get("/api/health")
        assert response.status_code == 200


# 运行所有测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
