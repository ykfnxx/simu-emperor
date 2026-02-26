"""
测试 AgentManager
"""

import pytest
from unittest.mock import MagicMock

from simu_emperor.agents.manager import AgentManager


@pytest.fixture
def mock_event_bus():
    """Mock EventBus"""
    event_bus = MagicMock()
    event_bus.subscribe = MagicMock()
    event_bus.unsubscribe = MagicMock()
    return event_bus


@pytest.fixture
def mock_llm():
    """Mock LLM Provider"""
    llm = MagicMock()
    llm.call = MagicMock(return_value="Response")
    return llm


@pytest.fixture
def temp_dirs(tmp_path):
    """创建临时目录"""
    template_dir = tmp_path / "templates"
    agent_dir = tmp_path / "agents"

    template_dir.mkdir(parents=True)
    agent_dir.mkdir(parents=True)

    # 创建测试模板 1
    template_agent = template_dir / "test_agent"
    template_agent.mkdir(parents=True)
    (template_agent / "soul.md").write_text("# Test Soul", encoding="utf-8")
    (template_agent / "data_scope.yaml").write_text("query: []", encoding="utf-8")

    # 创建测试模板 2
    another_agent = template_dir / "another_agent"
    another_agent.mkdir(parents=True)
    (another_agent / "soul.md").write_text("# Another Soul", encoding="utf-8")
    (another_agent / "data_scope.yaml").write_text("query: []", encoding="utf-8")

    return {
        "template_dir": template_dir,
        "agent_dir": agent_dir,
    }


@pytest.fixture
def manager(mock_event_bus, mock_llm, temp_dirs):
    """创建 AgentManager 实例"""
    return AgentManager(
        event_bus=mock_event_bus,
        llm_provider=mock_llm,
        template_dir=temp_dirs["template_dir"],
        agent_dir=temp_dirs["agent_dir"],
    )


class TestAgentManager:
    """测试 AgentManager 类"""

    def test_init(self, manager, mock_event_bus, mock_llm, temp_dirs):
        """测试初始化"""
        assert manager.event_bus == mock_event_bus
        assert manager.llm_provider == mock_llm
        assert manager.template_dir == temp_dirs["template_dir"]
        assert manager.agent_dir == temp_dirs["agent_dir"]
        assert manager.get_active_agents() == []

    def test_initialize_agent(self, manager, temp_dirs):
        """测试初始化 Agent"""
        result = manager.initialize_agent("test_agent")

        assert result is True

        agent_path = temp_dirs["agent_dir"] / "test_agent"
        assert agent_path.exists()
        assert (agent_path / "soul.md").exists()
        assert (agent_path / "data_scope.yaml").exists()
        assert (agent_path / "memory").exists()
        assert (agent_path / "workspace").exists()

    def test_initialize_agent_not_found(self, manager):
        """测试初始化不存在的 Agent"""
        result = manager.initialize_agent("nonexistent")

        assert result is False

    def test_add_agent(self, manager):
        """测试添加 Agent"""
        # 先初始化
        manager.initialize_agent("test_agent")

        # 添加 Agent
        result = manager.add_agent("test_agent")

        assert result is True
        assert "test_agent" in manager.get_active_agents()

    def test_add_agent_not_initialized(self, manager):
        """测试添加未初始化的 Agent"""
        result = manager.add_agent("nonexistent")

        assert result is False

    def test_remove_agent(self, manager):
        """测试移除 Agent"""
        manager.initialize_agent("test_agent")
        manager.add_agent("test_agent")

        result = manager.remove_agent("test_agent")

        assert result is True
        assert "test_agent" not in manager.get_active_agents()

    def test_remove_agent_not_active(self, manager):
        """测试移除未活跃的 Agent"""
        result = manager.remove_agent("nonexistent")

        assert result is False

    def test_get_all_agents(self, manager, temp_dirs):
        """测试获取所有 Agent"""
        manager.initialize_agent("test_agent")
        manager.initialize_agent("another_agent")

        agents = manager.get_all_agents()

        assert "test_agent" in agents
        assert "another_agent" in agents

    def test_get_active_agents(self, manager):
        """测试获取活跃 Agent"""
        manager.initialize_agent("test_agent")
        manager.initialize_agent("another_agent")

        manager.add_agent("test_agent")

        active = manager.get_active_agents()

        assert "test_agent" in active
        assert "another_agent" not in active

    def test_start_agent(self, manager):
        """测试启动 Agent"""
        manager.initialize_agent("test_agent")

        result = manager.start_agent("test_agent")

        assert result is True
        assert "test_agent" in manager.get_active_agents()

    def test_stop_agent(self, manager):
        """测试停止 Agent"""
        manager.initialize_agent("test_agent")
        manager.add_agent("test_agent")

        result = manager.stop_agent("test_agent")

        assert result is True
        assert "test_agent" not in manager.get_active_agents()

    def test_stop_all(self, manager):
        """测试停止所有 Agent"""
        manager.initialize_agent("agent1")
        manager.initialize_agent("agent2")

        manager.add_agent("agent1")
        manager.add_agent("agent2")

        manager.stop_all()

        assert manager.get_active_agents() == []

    def test_get_agent(self, manager):
        """测试获取 Agent 实例"""
        manager.initialize_agent("test_agent")
        manager.add_agent("test_agent")

        agent = manager.get_agent("test_agent")

        assert agent is not None
        assert agent.agent_id == "test_agent"

    def test_get_agent_not_found(self, manager):
        """测试获取不存在的 Agent"""
        agent = manager.get_agent("nonexistent")

        assert agent is None
