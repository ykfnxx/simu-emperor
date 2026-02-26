"""
测试 Agent 核心逻辑
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from simu_emperor.agents.agent import Agent
from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.llm.mock import MockProvider


@pytest.fixture
def mock_event_bus():
    """Mock EventBus"""
    event_bus = MagicMock(spec=EventBus)
    event_bus.subscribe = MagicMock()
    event_bus.unsubscribe = MagicMock()
    event_bus.send_event = AsyncMock()
    return event_bus


@pytest.fixture
def mock_llm():
    """Mock LLM Provider"""
    return MockProvider(response="LLM response")


@pytest.fixture
def temp_data_dir(tmp_path):
    """创建临时数据目录"""
    # 创建 soul.md
    soul_path = tmp_path / "soul.md"
    soul_path.write_text("# Test Soul\nYou are a test agent.", encoding="utf-8")

    # 创建 data_scope.yaml
    import yaml

    scope_path = tmp_path / "data_scope.yaml"
    scope_path.write_text(yaml.dump({"query": ["province.population"]}), encoding="utf-8")

    return tmp_path


@pytest.fixture
def agent(mock_event_bus, mock_llm, temp_data_dir):
    """创建 Agent 实例"""
    return Agent(
        agent_id="test_agent",
        event_bus=mock_event_bus,
        llm_provider=mock_llm,
        data_dir=temp_data_dir,
    )


class TestAgent:
    """测试 Agent 类"""

    def test_init(self, agent, mock_event_bus, mock_llm, temp_data_dir):
        """测试初始化"""
        assert agent.agent_id == "test_agent"
        assert agent.event_bus == mock_event_bus
        assert agent.llm_provider == mock_llm
        assert agent.data_dir == temp_data_dir
        assert agent._soul is not None
        assert agent._data_scope is not None

    def test_start(self, agent, mock_event_bus):
        """测试启动"""
        agent.start()

        assert mock_event_bus.subscribe.call_count == 2

    def test_stop(self, agent, mock_event_bus):
        """测试停止"""
        agent.start()
        agent.stop()

        assert mock_event_bus.unsubscribe.call_count == 2

    @pytest.mark.asyncio
    async def test_on_event_command(self, agent):
        """测试处理命令事件"""
        agent.start()

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.COMMAND,
            payload={"action": "test"},
        )

        await agent._on_event(event)

        # 不应该抛出异常

    @pytest.mark.asyncio
    async def test_on_event_query(self, agent):
        """测试处理查询事件"""
        agent.start()

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.QUERY,
            payload={"query": "test"},
        )

        await agent._on_event(event)

        # 不应该抛出异常

    @pytest.mark.asyncio
    async def test_on_event_chat(self, agent):
        """测试处理对话事件"""
        agent.start()

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.CHAT,
            payload={"message": "hello"},
        )

        await agent._on_event(event)

        # 不应该抛出异常

    @pytest.mark.asyncio
    async def test_handle_end_turn(self, agent, mock_event_bus):
        """测试处理回合结束"""
        agent.start()

        event = Event(src="player", dst=["*"], type=EventType.END_TURN)

        await agent._handle_end_turn(event)

        # 应该发送 ready 事件
        assert mock_event_bus.send_event.called
        sent_event = mock_event_bus.send_event.call_args[0][0]
        assert sent_event.type == EventType.READY
        assert sent_event.src == "agent:test_agent"

    @pytest.mark.asyncio
    async def test_handle_turn_resolved(self, agent):
        """测试处理回合结算完成"""
        agent.start()

        event = Event(
            src="system:calculator",
            dst=["*"],
            type=EventType.TURN_RESOLVED,
            payload={"turn": 1},
        )

        await agent._handle_turn_resolved(event)

        # 不应该抛出异常

    @pytest.mark.asyncio
    async def test_call_llm(self, agent, mock_llm):
        """测试调用 LLM"""
        response = await agent._call_llm("Test prompt")

        assert response == "LLM response"
        assert mock_llm.call_count == 1

    @pytest.mark.asyncio
    async def test_call_llm_custom_system(self, agent, mock_llm):
        """测试调用 LLM（自定义系统提示词）"""
        response = await agent._call_llm("Test prompt", system_prompt="Custom system")

        assert response == "LLM response"
