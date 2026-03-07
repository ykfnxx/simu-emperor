"""
Unit tests for FastAPI server
"""

import pytest
from unittest.mock import AsyncMock
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

    def test_get_agents_initialized(self, client, monkeypatch):
        """测试获取 agents 列表（已初始化）。"""
        from simu_emperor.adapters.web import server as server_module

        monkeypatch.setattr(server_module.game_instance, "_running", True)
        monkeypatch.setattr(
            server_module.game_instance,
            "get_available_agents",
            lambda: ["governor_zhili", "minister_of_revenue"],
        )

        response = client.get("/api/agents")
        assert response.status_code == 200
        assert response.json() == ["governor_zhili", "minister_of_revenue"]

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

    def test_send_command_unknown_agent(self, client):
        """测试发送命令（未知 agent）。"""
        response = client.post(
            "/api/command",
            json={"agent": "agent:not_exists", "command": "test"},
        )
        assert response.status_code == 400
        assert "Unknown agent" in response.json()["detail"]

    def test_websocket_connect(self, client):
        """测试 WebSocket 连接"""
        with client.websocket_connect("/ws"):
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

    def test_websocket_command_unknown_agent_returns_error(self, client):
        """测试 WebSocket 未知 agent 返回错误。"""
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json(
                {
                    "type": "command",
                    "agent": "not_exists",
                    "text": "test command",
                }
            )
            message = websocket.receive_json()
            assert message["kind"] == "error"
            assert "Unknown agent" in message["data"]["message"]

    def test_get_overview(self, client):
        """测试帝国概况端点"""
        response = client.get("/api/overview")
        assert response.status_code == 200
        data = response.json()
        assert "turn" in data
        assert "treasury" in data

    def test_list_sessions(self, client):
        """测试会话列表端点"""
        response = client.get("/api/sessions")
        assert response.status_code == 200
        data = response.json()
        assert "current_session_id" in data
        assert "current_agent_id" in data
        assert "sessions" in data
        assert "agent_sessions" in data

    def test_create_session(self, client, monkeypatch):
        """测试新建会话端点"""
        from simu_emperor.adapters.web import server as server_module

        monkeypatch.setattr(
            server_module.game_instance,
            "get_available_agents",
            lambda: ["governor_zhili", "minister_of_revenue"],
        )

        response = client.post(
            "/api/sessions",
            json={"name": "测试会话", "agent_id": "governor_zhili"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "current_session_id" in data
        assert "current_agent_id" in data
        assert "session" in data

    def test_create_session_invalid_agent(self, client):
        """测试新建会话时 agent 不存在。"""
        response = client.post(
            "/api/sessions",
            json={"name": "测试会话", "agent_id": "not_exists"},
        )
        assert response.status_code == 400
        assert "Unknown agent" in response.json()["detail"]

    def test_create_session_empty_name(self, client):
        """测试新建会话时 name 为空字符串。"""
        response = client.post(
            "/api/sessions",
            json={"name": "   ", "agent_id": "governor_zhili"},
        )
        assert response.status_code == 422

    def test_select_session_not_found(self, client, monkeypatch):
        """测试选择不存在会话"""
        from simu_emperor.adapters.web import server as server_module

        mock_select = AsyncMock(side_effect=ValueError("Session not found"))
        monkeypatch.setattr(server_module.game_instance, "select_session", mock_select)

        response = client.post(
            "/api/sessions/select",
            json={"session_id": "session:web:not-found"},
        )
        assert response.status_code == 404

    def test_select_session_invalid_format(self, client):
        """测试选择会话时 session_id 格式非法。"""
        response = client.post(
            "/api/sessions/select",
            json={"session_id": "invalid-session-id"},
        )
        assert response.status_code == 400
        assert "Invalid session_id format" in response.json()["detail"]

    def test_get_current_tape(self, client, monkeypatch):
        """测试获取当前 tape 端点"""
        from simu_emperor.adapters.web import server as server_module

        mock_get_tape = AsyncMock(
            return_value={"session_id": "session:web:test", "events": [], "total": 0}
        )
        monkeypatch.setattr(server_module.game_instance, "get_current_tape", mock_get_tape)

        response = client.get("/api/tape/current")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "session:web:test"
        assert "events" in data

    def test_get_current_tape_invalid_agent(self, client):
        """测试获取 tape 时 agent_id 不存在。"""
        response = client.get("/api/tape/current?agent_id=not_exists")
        assert response.status_code == 400
        assert "Unknown agent" in response.json()["detail"]
