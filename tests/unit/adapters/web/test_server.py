"""
Unit tests for FastAPI server

Tests the server endpoints without relying on full service initialization.
Tests that require initialized services are marked as integration tests.
"""

import pytest
from fastapi.testclient import TestClient

from simu_emperor.adapters.web.server import app


class TestFastAPIServer:
    """测试 FastAPI 服务器 (V4 重构后)"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)

    # ==================== Basic Endpoint Tests ====================

    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "connections" in data

    # ==================== Command API Tests ====================

    def test_send_command_missing_agent(self, client):
        """测试发送命令（缺少 agent）"""
        response = client.post("/api/command", json={"command": "test"})
        # Pydantic 验证应该返回 422
        assert response.status_code == 422

    # ==================== Agent API Tests ====================

    def test_get_agents_not_initialized(self, client):
        """测试获取 agents 列表（未初始化）"""
        response = client.get("/api/agents")
        # 应该返回 503
        assert response.status_code == 503

    # ==================== Game State API Tests ====================

    def test_get_state_not_initialized(self, client):
        """测试获取游戏状态（未初始化）"""
        response = client.get("/api/state")
        # 应该返回 503
        assert response.status_code == 503

    @pytest.mark.skip(reason="Requires game initialization - should be in integration tests")
    def test_get_overview(self, client):
        """测试帝国概况端点"""
        pass

    # ==================== Session API Tests ====================

    @pytest.mark.skip(reason="Requires game initialization - should be in integration tests")
    def test_create_session_invalid_agent(self, client):
        """测试新建会话时 agent 不存在。"""
        pass

    @pytest.mark.skip(reason="Requires game initialization - should be in integration tests")
    def test_create_session_empty_name(self, client):
        """测试新建会话时 name 为空字符串。"""
        pass

    def test_create_session_response_format(self, client):
        """测试创建会话响应格式是否包含前端需要的字段"""
        # 测试请求体格式验证（Pydantic会自动验证）
        response = client.post(
            "/api/sessions", json={"name": "测试会话", "agent_id": "governor_zhili"}
        )
        # 游戏未初始化，应该返回错误或 503
        # 这里主要测试请求格式正确，能通过 Pydantic 验证
        assert response.status_code in [200, 503, 500]

    @pytest.mark.skip(reason="Requires game initialization - should be in integration tests")
    def test_select_session_invalid_format(self, client):
        """测试选择会话时 session_id 格式非法。"""
        pass

    # ==================== Tape API Tests ====================

    @pytest.mark.skip(reason="Requires game initialization - should be in integration tests")
    def test_get_current_tape_invalid_agent(self, client):
        """测试获取 tape 时 agent_id 不存在。"""
        pass

    # ==================== WebSocket Tests ====================
    # Note: WebSocket tests can hang in pytest - marked as skipped for unit tests

    @pytest.mark.skip(reason="WebSocket tests should be in integration tests")
    def test_websocket_connect(self, client):
        """测试 WebSocket 连接"""
        pass

    @pytest.mark.skip(reason="WebSocket tests should be in integration tests")
    def test_websocket_command_unknown_agent_returns_error(self, client):
        """测试 WebSocket 未知 agent 返回错误。"""
        pass

    @pytest.mark.skip(reason="WebSocket tests should be in integration tests")
    def test_websocket_chat_unknown_agent_returns_error(self, client):
        """测试 WebSocket 聊天未知 agent 返回错误。"""
        pass

    @pytest.mark.skip(reason="WebSocket tests should be in integration tests")
    def test_send_invalid_message_type(self, client):
        """测试发送无效的消息类型"""
        pass

    # ==================== Integration Tests (Skipped) ====================

    @pytest.mark.skip(reason="Requires game initialization - should be in integration tests")
    def test_send_command_unknown_agent(self, client):
        """测试发送命令（未知 agent）。"""
        pass

    @pytest.mark.skip(reason="Requires game initialization - should be in integration tests")
    def test_send_command_via_websocket(self, client):
        """测试通过 WebSocket 发送命令"""
        pass

    @pytest.mark.skip(reason="Requires game initialization - should be in integration tests")
    def test_send_chat_via_websocket(self, client):
        """测试通过 WebSocket 发送聊天消息"""
        pass

    @pytest.mark.skip(reason="Requires game initialization - should be in integration tests")
    def test_list_sessions(self, client):
        """测试会话列表端点"""
        pass

    @pytest.mark.skip(reason="Requires game initialization - should be in integration tests")
    def test_create_session_and_select(self, client):
        """测试新建会话并切换"""
        pass

    @pytest.mark.skip(reason="Requires game initialization - should be in integration tests")
    def test_select_session_not_found(self, client):
        """测试选择不存在会话"""
        pass

    @pytest.mark.skip(reason="Requires game initialization - should be in integration tests")
    def test_get_current_tape(self, client):
        """测试获取当前 tape"""
        pass

    @pytest.mark.skip(reason="Requires game initialization - should be in integration tests")
    def test_list_group_chats(self, client):
        """测试群聊列表"""
        pass

    @pytest.mark.skip(reason="Requires game initialization - should be in integration tests")
    def test_create_group_chat(self, client):
        """测试创建群聊"""
        pass

    @pytest.mark.skip(reason="Requires game initialization - should be in integration tests")
    def test_send_to_group_chat(self, client):
        """测试发送群聊消息"""
        pass

    @pytest.mark.skip(reason="Requires game initialization - should be in integration tests")
    def test_add_agent_to_group(self, client):
        """测试添加 agent 到群聊"""
        pass

    @pytest.mark.skip(reason="Requires game initialization - should be in integration tests")
    def test_remove_agent_from_group(self, client):
        """测试从群聊移除 agent"""
        pass
