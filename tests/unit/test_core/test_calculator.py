"""
测试 TurnCoordinator 核心逻辑
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from simu_emperor.engine.coordinator import TurnCoordinator
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
    """Mock Repository with valid game state"""
    from decimal import Decimal

    repo = MagicMock()
    repo.get_active_agents = AsyncMock(return_value=[])

    # 返回有效的 NationalBaseData 格式
    repo.load_state = AsyncMock(
        return_value={
            "turn": 0,
            "imperial_treasury": "100000",
            "national_tax_modifier": "1.0",
            "tribute_rate": "0.1",
            "provinces": [
                {
                    "province_id": "zhili",
                    "name": "直隶",
                    "population": {
                        "total": "2600000",
                        "happiness": "0.7",
                        "growth_rate": "0.002",
                        "labor_ratio": "0.55",
                    },
                    "agriculture": {
                        "crops": [
                            {"crop_type": "wheat", "area_mu": "300000", "yield_per_mu": "1.3"},
                            {"crop_type": "rice", "area_mu": "100000", "yield_per_mu": "3"},
                        ],
                        "irrigation_level": "0.3",
                    },
                    "commerce": {
                        "merchant_households": "150000",
                        "market_prosperity": "0.7",
                    },
                    "trade": {
                        "trade_volume": "500000",
                        "trade_route_quality": "0.6",
                    },
                    "military": {
                        "soldiers": "50000",
                        "morale": "0.7",
                        "garrison_size": "30000",
                        "equipment_level": "0.5",
                        "upkeep": "150000",
                        "upkeep_per_soldier": "3",
                    },
                    "taxation": {
                        "land_tax_rate": "0.03",
                        "commercial_tax_rate": "0.05",
                        "tariff_rate": "0.1",
                    },
                    "consumption": {
                        "civilian_grain_per_capita": "3",
                        "military_grain_per_soldier": "5",
                    },
                    "administration": {
                        "official_count": "5000",
                        "official_salary": "20",
                        "infrastructure_value": "0.5",
                    },
                    "granary_stock": "1200000",
                    "local_treasury": "80000",
                }
            ],
        }
    )

    repo.save_state = AsyncMock()
    repo.save_turn_metrics = AsyncMock()
    repo.increment_turn = AsyncMock(return_value=1)
    repo.update_province_data = AsyncMock()
    return repo


@pytest.fixture
def calculator(mock_event_bus, mock_repository):
    """创建 TurnCoordinator 实例"""
    return TurnCoordinator(mock_event_bus, mock_repository)


class TestTurnCoordinator:
    """测试 TurnCoordinator 类"""

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

        event = Event(src="player", dst=["*"], type=EventType.END_TURN, session_id="test_calc")
        await calculator._on_end_turn(event)

        # 应该直接结算（不等待 ready）
        assert len(calculator.pending_ready) == 0

    @pytest.mark.asyncio
    async def test_on_end_turn_with_agents(self, calculator):
        """测试结束回合（有 Agent）"""
        calculator.start()

        # Mock _get_active_agents 方法
        calculator._get_active_agents = AsyncMock(return_value=["agent:a", "agent:b", "agent:c"])

        event = Event(src="player", dst=["*"], type=EventType.END_TURN, session_id="test_calc")
        await calculator._on_end_turn(event)

        # 应该等待这 3 个 Agent
        assert calculator.pending_ready == {"agent:a", "agent:b", "agent:c"}

    @pytest.mark.asyncio
    async def test_on_ready(self, calculator):
        """测试 Agent 准备就绪"""
        calculator.start()
        calculator.pending_ready = {"agent:a", "agent:b"}

        # Agent a 就绪
        event = Event(
            src="agent:a", dst=["system:calculator"], type=EventType.READY, session_id="test_calc"
        )
        await calculator._on_ready(event)

        assert "agent:a" not in calculator.pending_ready
        assert calculator.pending_ready == {"agent:b"}

    @pytest.mark.asyncio
    async def test_on_ready_all_agents(self, calculator, mock_event_bus):
        """测试所有 Agent 都就绪"""
        calculator.start()
        calculator.pending_ready = {"agent:a"}

        # 最后一个 Agent 就绪，应该触发回合结算
        event = Event(
            src="agent:a", dst=["system:calculator"], type=EventType.READY, session_id="test_calc"
        )
        await calculator._on_ready(event)

        assert len(calculator.pending_ready) == 0
        # 应该发送了 turn_resolved 事件
        assert mock_event_bus.send_event.called

    @pytest.mark.asyncio
    async def test_on_ready_non_ready_event(self, calculator):
        """测试非 ready 事件被忽略"""
        calculator.start()
        calculator.pending_ready = {"agent:a"}

        event = Event(
            src="agent:a", dst=["system:calculator"], type=EventType.COMMAND, session_id="test_calc"
        )
        await calculator._on_ready(event)

        # pending_ready 不应该改变
        assert calculator.pending_ready == {"agent:a"}

    @pytest.mark.asyncio
    async def test_on_adjust_tax(self, calculator, mock_repository):
        """测试税率调整"""
        calculator.start()

        event = Event(
            src="agent:revenue_minister",
            dst=["system:calculator"],
            type=EventType.ADJUST_TAX,
            payload={"province": "zhili", "rate": 0.1},
            session_id="test_calc",
        )

        await calculator._on_adjust_tax(event)

        # 应该调用 repository 更新方法
        assert mock_repository.update_province_data.called

    @pytest.mark.asyncio
    async def test_on_build_irrigation(self, calculator):
        """测试水利建设"""
        calculator.start()

        event = Event(
            src="agent:agriculture_minister",
            dst=["system:calculator"],
            type=EventType.BUILD_IRRIGATION,
            payload={"province": "zhili", "level": 2},
            session_id="test_calc",
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
            session_id="test_calc",
        )

        await calculator._on_recruit_troops(event)

        # 不应该抛出异常

    @pytest.mark.asyncio
    async def test_resolve_turn(self, calculator, mock_event_bus, mock_repository):
        """测试回合结算"""
        calculator.start()

        await calculator._resolve_turn()

        # 应该调用 repository 方法
        assert mock_repository.load_state.called
        assert mock_repository.save_state.called
        assert mock_repository.save_turn_metrics.called
        # 注意：increment_turn 不再被调用（回合数在 engine 中递增）

        # 应该发送 turn_resolved 事件
        assert mock_event_bus.send_event.called
        sent_event = mock_event_bus.send_event.call_args[0][0]
        assert sent_event.type == EventType.TURN_RESOLVED
        assert sent_event.src == "system:calculator"
        # 验证回合数已递增
        assert sent_event.payload.get("turn") == 1
