"""
Unit tests for FastAPI server
"""

import pytest
from fastapi.testclient import TestClient

from simu_emperor.adapters.web.server import app


class TestFastAPIServer:
    """测试 FastAPI 服务器"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)

    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "connections" in data

    def test_get_agents_not_initialized(self, client):
        """测试获取 agents 列表（未初始化）"""
        response = client.get("/api/agents")

        # 应该返回 503 或空列表
        assert response.status_code in [200, 503]

    def test_get_state_not_initialized(self, client):
        """测试获取游戏状态（未初始化）"""
        response = client.get("/api/state")

        # 应该返回 503 或空字典
        assert response.status_code in [200, 503]

    def test_send_command_missing_agent(self, client):
        """测试发送命令（缺少 agent）"""
        response = client.post(
            "/api/command",
            json={"command": "test"}
        )

        # Pydantic 验证应该返回 422
        assert response.status_code == 422

    def test_websocket_connect(self, client):
        """测试 WebSocket 连接"""
        with client.websocket_connect("/ws") as websocket:
            # 连接成功，不期望接收数据
            pass

    def test_send_command_via_websocket(self, client):
        """测试通过 WebSocket 发送命令"""
        with client.websocket_connect("/ws") as websocket:
            # 发送命令
            websocket.send_json({
                "type": "command",
                "agent": "test_agent",
                "text": "test command"
            })

            # 不应该有错误
            # 注意：由于游戏未初始化，可能不会有响应

    def test_send_chat_via_websocket(self, client):
        """测试通过 WebSocket 发送聊天消息"""
        with client.websocket_connect("/ws") as websocket:
            # 发送聊天消息
            websocket.send_json({
                "type": "chat",
                "agent": "test_agent",
                "text": "hello"
            })

            # 不应该有错误

    def test_send_invalid_message_type(self, client):
        """测试发送无效的消息类型"""
        with client.websocket_connect("/ws") as websocket:
            # 发送无效消息类型
            websocket.send_json({
                "type": "invalid_type",
                "text": "test"
            })

            # 应该收到错误消息（如果实现了）
            # 或者连接可能关闭
