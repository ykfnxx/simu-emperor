"""
测试 Calculator 核心逻辑
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from simu_emperor.core.calculator import Calculator
from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType


@pytest.fixture
def mock_event_bus():
    """Mock EventBus"""
    event_bus = MagicMock(spec=EventBus)
    event_bus.subscribe = MagicMock()
    event_bus.send_event = AsyncMock()
    return event_bus


@pytest.fixture
def mock_repository():
    """Mock Repository"""
    repo = MagicMock()
    repo.get_active_agents = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def calculator(mock_event_bus, mock_repository):
    """创建 Calculator 实例"""
    return Calculator(mock_event_bus, mock_repository)


class TestCalculator:
    """测试 Calculator 类"""

    def test_init(self, calculator, mock_event_bus, mock_repository):
        """测试初始化"""
        assert calculator.event_bus == mock_event_bus
        assert calculator.repository == mock_repository
        assert calculator.ready_timeout == 5.0
        assert calculator._running is False

    def test_start(self, calculator, mock_event_bus):
        """测试启动"""
        calculator.start()

        assert calculator._running is True
        # 验证订阅了事件
        assert mock_event_bus.subscribe.call_count >= 4

    def test_stop(self, calculator):
        """测试停止"""
        calculator.start()
        calculator.stop()

        assert calculator._running is False

    @pytest.mark.asyncio
    async def test_on_end_turn_no_agents(self, calculator, mock_repository):
        """测试结束回合（没有 Agent）"""
        calculator.start()

        mock_repository.get_active_agents = AsyncMock(return_value=[])

        event = Event(src="player", dst=["*"], type=EventType.END_TURN)
        await calculator._on_end_turn(event)

        # 应该直接结算（不等待 ready）
        assert len(calculator.pending_ready) == 0

    @pytest.mark.asyncio
    async def test_on_end_turn_with_agents(self, calculator):
        """测试结束回合（有 Agent）"""
        calculator.start()

        # Mock _get_active_agents 方法
        calculator._get_active_agents = AsyncMock(return_value=["agent:a", "agent:b", "agent:c"])

        event = Event(src="player", dst=["*"], type=EventType.END_TURN)
        await calculator._on_end_turn(event)

        # 应该等待这 3 个 Agent
        assert calculator.pending_ready == {"agent:a", "agent:b", "agent:c"}

    @pytest.mark.asyncio
    async def test_on_ready(self, calculator):
        """测试 Agent 准备就绪"""
        calculator.start()
        calculator.pending_ready = {"agent:a", "agent:b"}

        # Agent a 就绪
        event = Event(src="agent:a", dst=["system:calculator"], type=EventType.READY)
        await calculator._on_ready(event)

        assert "agent:a" not in calculator.pending_ready
        assert calculator.pending_ready == {"agent:b"}

    @pytest.mark.asyncio
    async def test_on_ready_all_agents(self, calculator, mock_event_bus):
        """测试所有 Agent 都就绪"""
        calculator.start()
        calculator.pending_ready = {"agent:a"}

        # 最后一个 Agent 就绪，应该触发回合结算
        event = Event(src="agent:a", dst=["system:calculator"], type=EventType.READY)
        await calculator._on_ready(event)

        assert len(calculator.pending_ready) == 0
        # 应该发送了 turn_resolved 事件
        assert mock_event_bus.send_event.called

    @pytest.mark.asyncio
    async def test_on_ready_non_ready_event(self, calculator):
        """测试非 ready 事件被忽略"""
        calculator.start()
        calculator.pending_ready = {"agent:a"}

        event = Event(src="agent:a", dst=["system:calculator"], type=EventType.COMMAND)
        await calculator._on_ready(event)

        # pending_ready 不应该改变
        assert calculator.pending_ready == {"agent:a"}

    @pytest.mark.asyncio
    async def test_on_adjust_tax(self, calculator):
        """测试税率调整"""
        calculator.start()

        event = Event(
            src="agent:revenue_minister",
            dst=["system:calculator"],
            type=EventType.ADJUST_TAX,
            payload={"province": "zhili", "rate": 0.1},
        )

        await calculator._on_adjust_tax(event)

        # 不应该抛出异常

    @pytest.mark.asyncio
    async def test_on_build_irrigation(self, calculator):
        """测试水利建设"""
        calculator.start()

        event = Event(
            src="agent:agriculture_minister",
            dst=["system:calculator"],
            type=EventType.BUILD_IRRIGATION,
            payload={"province": "zhili", "level": 2},
        )

        await calculator._on_build_irrigation(event)

        # 不应该抛出异常

    @pytest.mark.asyncio
    async def test_on_recruit_troops(self, calculator):
        """测试招募军队"""
        calculator.start()

        event = Event(
            src="agent:war_minister",
            dst=["system:calculator"],
            type=EventType.RECRUIT_TROOPS,
            payload={"province": "zhili", "count": 1000},
        )

        await calculator._on_recruit_troops(event)

        # 不应该抛出异常

    @pytest.mark.asyncio
    async def test_resolve_turn(self, calculator, mock_event_bus):
        """测试回合结算"""
        calculator.start()

        await calculator._resolve_turn()

        # 应该发送 turn_resolved 事件
        assert mock_event_bus.send_event.called
        sent_event = mock_event_bus.send_event.call_args[0][0]
        assert sent_event.type == EventType.TURN_RESOLVED
        assert sent_event.src == "system:calculator"
