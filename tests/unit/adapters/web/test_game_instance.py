"""
Unit tests for WebGameInstance
"""

import pytest
import json
from pathlib import Path
from pydantic import BaseModel

from simu_emperor.adapters.web.game_instance import WebGameInstance


class MockLLMConfig(BaseModel):
    """Mock LLM 配置"""
    provider: str = "mock"
    api_key: str = "test_key"
    api_base: str | None = None
    model: str = "mock-model"


class TestWebGameInstance:
    """测试 WebGameInstance 类"""

    @pytest.fixture
    def settings(self, tmp_path):
        """创建测试配置"""
        class MockSettings:
            def __init__(self, tmp_path):
                self.data_dir = tmp_path / "data"
                self.data_dir.mkdir(parents=True, exist_ok=True)
                self.log_dir = tmp_path / "logs"
                self.log_dir.mkdir(parents=True, exist_ok=True)
                self.llm = MockLLMConfig()

        return MockSettings(tmp_path)

    def test_create_llm_provider_mock(self, settings):
        """测试创建 Mock LLM Provider"""
        instance = WebGameInstance(settings)
        provider = instance.create_llm_provider()

        # 检查 provider 不为 None
        assert provider is not None
        assert hasattr(provider, 'call')

    def test_initialization(self, settings):
        """测试初始化"""
        instance = WebGameInstance(settings)

        assert instance.settings == settings
        assert instance.player_id == "player:web"
        assert instance.session_id == "session:web:main"
        assert instance.memory_dir == settings.data_dir / "memory"
        assert instance._running is False
        assert instance.event_bus is None
        assert instance.repository is None
        assert instance.calculator is None
        assert instance.agent_manager is None

    @pytest.mark.asyncio
    async def test_shutdown_when_not_running(self, settings):
        """测试未运行时关闭"""
        instance = WebGameInstance(settings)

        # 未运行时关闭不应该抛出异常
        await instance.shutdown()

        assert instance._running is False

    # 跳过耗时的完整集成测试
    # 这些测试应该在 integration/ 目录中进行
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Full initialization requires integration test environment")
    async def test_start_and_shutdown(self, settings):
        """测试启动和关闭（集成测试）"""
        pass

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Full initialization requires integration test environment")
    async def test_start_already_running(self, settings):
        """测试重复启动"""
        pass

    def test_db_path(self, settings):
        """测试数据库路径"""
        instance = WebGameInstance(settings)

        expected_path = str(settings.data_dir / "game.db")
        assert instance.db_path == expected_path

    @pytest.mark.asyncio
    async def test_create_session_and_select(self, settings):
        """测试创建并切换 session"""
        instance = WebGameInstance(settings)

        created = await instance.create_session("水灾赈灾")
        assert created["session_id"].startswith("session:web:")
        assert created["is_current"] is True
        assert instance.session_id == created["session_id"]

        sessions = await instance.list_sessions()
        session_ids = {item["session_id"] for item in sessions}
        assert "session:web:main" in session_ids
        assert created["session_id"] in session_ids

        selected = await instance.select_session("session:web:main")
        assert selected["session_id"] == "session:web:main"
        assert instance.session_id == "session:web:main"

    @pytest.mark.asyncio
    async def test_select_session_not_found(self, settings):
        """测试切换不存在 session 报错"""
        instance = WebGameInstance(settings)
        with pytest.raises(ValueError):
            await instance.select_session("session:web:not-found")

    @pytest.mark.asyncio
    async def test_get_empire_overview_without_repository(self, settings):
        """测试未初始化时的帝国概况"""
        instance = WebGameInstance(settings)
        overview = await instance.get_empire_overview()

        assert overview["turn"] == 0
        assert overview["treasury"] == 0
        assert overview["population"] == 0
        assert overview["military"] == 0
        assert overview["happiness"] == 0.0
        assert overview["province_count"] == 0

    @pytest.mark.asyncio
    async def test_get_current_tape(self, settings):
        """测试读取当前 session 的 tape"""
        instance = WebGameInstance(settings)
        instance.session_id = "session:web:test"

        tape_path = (
            instance.memory_dir
            / "agents"
            / "governor_zhili"
            / "sessions"
            / "session:web:test"
            / "tape.jsonl"
        )
        tape_path.parent.mkdir(parents=True, exist_ok=True)

        event = {
            "event_id": "evt_1",
            "src": "agent:governor_zhili",
            "dst": ["player:web"],
            "type": "response",
            "payload": {"narrative": "启禀陛下"},
            "timestamp": "2026-03-07T00:00:00+00:00",
            "session_id": "session:web:test",
            "parent_event_id": None,
            "root_event_id": "",
        }
        tape_path.write_text(json.dumps(event, ensure_ascii=False) + "\n", encoding="utf-8")

        result = await instance.get_current_tape(limit=20)
        assert result["session_id"] == "session:web:test"
        assert result["total"] == 1
        assert result["events"][0]["event_id"] == "evt_1"
        assert result["events"][0]["agent_id"] == "governor_zhili"

    def test_get_available_agents_only_active(self, settings):
        """测试可用 agent 仅返回已启动的活跃 agent。

        未初始化的模板 agent 不应被视为可用，
        因为它们未订阅 EventBus，无法接收和处理事件。
        """
        instance = WebGameInstance(settings)

        # 模板目录（未初始化，不应出现在可用列表中）
        (settings.data_dir / "default_agents" / "governor_zhili").mkdir(parents=True, exist_ok=True)
        (settings.data_dir / "default_agents" / "minister_of_revenue").mkdir(parents=True, exist_ok=True)
        # memory 目录（未初始化，不应出现在可用列表中）
        (instance.memory_dir / "agents" / "archivist" / "sessions").mkdir(parents=True, exist_ok=True)
        # 当前会话映射（未初始化，不应出现在可用列表中）
        instance._current_session_by_agent["grand_secretary"] = "session:web:main"

        class MockAgentManager:
            def get_active_agents(self):
                # 只有 governor_zhili 实际启动了
                return ["governor_zhili"]

            def get_all_agents(self):
                return ["governor_zhili", "minister_of_revenue"]

        instance.agent_manager = MockAgentManager()

        agents = instance.get_available_agents()
        # 只返回活跃 agent，不包括未初始化的模板/memory/会话映射 agent
        assert agents == ["governor_zhili"]
