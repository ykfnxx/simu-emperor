"""事件总线单元测试。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from simu_emperor.core.event_bus import (
    ControlEvent,
    EventBus,
    EventFilter,
    EventPriority,
    EventType,
)
from simu_emperor.engine.models.state import GamePhase


class TestEventBus:
    """EventBus 单元测试。"""

    @pytest.fixture
    def event_bus(self):
        """创建事件总线实例。"""
        return EventBus(max_queue_size=100)

    @pytest.fixture
    def game_phase(self):
        """返回测试用阶段。"""
        return GamePhase.SUMMARY

    @pytest.mark.asyncio
    async def test_start_and_stop(self, event_bus):
        """测试启动和停止事件总线。"""
        await event_bus.start()
        assert event_bus._running is True
        assert event_bus._dispatcher_task is not None

        await event_bus.stop()
        assert event_bus._running is False

    @pytest.mark.asyncio
    async def test_publish_event(self, event_bus, game_phase):
        """测试发布事件。"""
        await event_bus.start()

        event = await event_bus.publish(
            event_type=EventType.PHASE_TRANSITION,
            turn=1,
            phase=game_phase,
        )

        assert event.event_id is not None
        assert event.type == EventType.PHASE_TRANSITION
        assert event.turn == 1
        assert event.phase == game_phase

        # 等待事件被处理
        await asyncio.sleep(0.2)

        metrics = event_bus.get_metrics()
        assert metrics["published"] == 1
        assert metrics["delivered"] == 1

        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_subscribe_and_receive(self, event_bus, game_phase):
        """测试订阅和接收事件。"""
        await event_bus.start()

        received_events = []

        async def handler(event: ControlEvent):
            received_events.append(event)

        event_bus.subscribe(
            event_types=[EventType.AGENT_SUMMARY_REQUESTED],
            handler=handler,
        )

        await event_bus.publish(
            event_type=EventType.AGENT_SUMMARY_REQUESTED,
            turn=1,
            phase=game_phase,
            agent_id="test_agent",
        )

        # 等待事件被处理
        await asyncio.sleep(0.2)

        assert len(received_events) == 1
        assert received_events[0].agent_id == "test_agent"

        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_subscribe_with_filter(self, event_bus, game_phase):
        """测试带过滤器的订阅。"""
        await event_bus.start()

        received_events = []

        async def handler(event: ControlEvent):
            received_events.append(event)

        filter = EventFilter(agent_ids={"agent_a"})
        event_bus.subscribe(
            event_types=[EventType.AGENT_SUMMARY_REQUESTED],
            handler=handler,
            filter=filter,
        )

        # 发布匹配的事件
        await event_bus.publish(
            event_type=EventType.AGENT_SUMMARY_REQUESTED,
            turn=1,
            phase=game_phase,
            agent_id="agent_a",
        )

        # 发布不匹配的事件
        await event_bus.publish(
            event_type=EventType.AGENT_SUMMARY_REQUESTED,
            turn=1,
            phase=game_phase,
            agent_id="agent_b",
        )

        # 等待事件被处理
        await asyncio.sleep(0.2)

        assert len(received_events) == 1
        assert received_events[0].agent_id == "agent_a"

        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_unsubscribe(self, event_bus, game_phase):
        """测试取消订阅。"""
        await event_bus.start()

        received_events = []

        async def handler(event: ControlEvent):
            received_events.append(event)

        unsubscribe = event_bus.subscribe(
            event_types=[EventType.AGENT_SUMMARY_REQUESTED],
            handler=handler,
        )

        await event_bus.publish(
            event_type=EventType.AGENT_SUMMARY_REQUESTED,
            turn=1,
            phase=game_phase,
        )

        await asyncio.sleep(0.2)
        assert len(received_events) == 1

        # 取消订阅
        unsubscribe()

        await event_bus.publish(
            event_type=EventType.AGENT_SUMMARY_REQUESTED,
            turn=2,
            phase=game_phase,
        )

        await asyncio.sleep(0.2)
        assert len(received_events) == 1  # 仍然是 1，没有新事件

        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_future_wait_for_completion(self, event_bus, game_phase):
        """测试 Future/Promise 等待完成事件。"""
        await event_bus.start()

        correlation_id = "test-correlation-123"
        agent_id = "test_agent"
        completed = asyncio.Event()

        # 模拟 handler 发布完成事件
        async def request_handler(event: ControlEvent):
            await asyncio.sleep(0.05)  # 模拟处理延迟
            await event_bus.publish(
                event_type=EventType.AGENT_SUMMARY_COMPLETED,
                turn=event.turn,
                phase=event.phase,
                agent_id=event.agent_id,
                payload={"report": "Test report"},
                correlation_id=event.correlation_id,
                parent_id=event.event_id,
            )
            completed.set()

        event_bus.subscribe(
            event_types=[EventType.AGENT_SUMMARY_REQUESTED],
            handler=request_handler,
        )

        # 先创建 Future，再发布请求事件
        future = event_bus.create_request_future(
            correlation_id=correlation_id,
            agent_id=agent_id,
        )

        # 发布请求事件
        await event_bus.publish(
            event_type=EventType.AGENT_SUMMARY_REQUESTED,
            turn=1,
            phase=game_phase,
            agent_id=agent_id,
            correlation_id=correlation_id,
        )

        # 等待 handler 完成发布完成事件
        await asyncio.wait_for(completed.wait(), timeout=2.0)

        # 再等待一小段时间确保完成事件被分发
        await asyncio.sleep(0.2)

        # Future 应该已经被完成事件设置
        assert future.done(), "Future should be done after completion event"
        completed_event = future.result()
        assert completed_event.payload.get("report") == "Test report"
        assert completed_event.correlation_id == correlation_id

        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_future_timeout(self, event_bus, game_phase):
        """测试 Future 超时。"""
        await event_bus.start()

        correlation_id = "test-timeout-123"

        # 创建 Future，但没有对应的 handler 发布完成事件
        future = event_bus.create_request_future(
            correlation_id=correlation_id,
            agent_id="test_agent",
        )

        # 发布请求事件
        await event_bus.publish(
            event_type=EventType.AGENT_SUMMARY_REQUESTED,
            turn=1,
            phase=game_phase,
            agent_id="test_agent",
            correlation_id=correlation_id,
        )

        # 等待超时
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(future, timeout=0.5)

        # 清理
        event_bus.cancel_request(correlation_id, "test_agent")
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_event_history(self, event_bus, game_phase):
        """测试事件历史记录。"""
        await event_bus.start()

        for i in range(5):
            await event_bus.publish(
                event_type=EventType.PHASE_TRANSITION,
                turn=i,
                phase=game_phase,
            )

        await asyncio.sleep(0.2)

        history = event_bus.get_event_history()
        assert len(history) == 5

        # 按回合过滤
        history_turn_2 = event_bus.get_event_history(turn=2)
        assert len(history_turn_2) == 1

        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_backpressure_drops_low_priority(self, event_bus, game_phase):
        """测试背压控制丢弃低优先级事件。"""
        bus = EventBus(max_queue_size=10)
        await bus.start()

        # 填满队列
        for i in range(15):
            await bus.publish(
                event_type=EventType.PHASE_TRANSITION,
                turn=i,
                phase=game_phase,
                priority=EventPriority.LOW,
            )

        await asyncio.sleep(0.2)

        metrics = bus.get_metrics()
        assert metrics["dropped"] > 0

        await bus.stop()


class TestEventFilter:
    """EventFilter 单元测试。"""

    def test_matches_event_type(self):
        """测试事件类型匹配。"""
        filter = EventFilter(event_types={EventType.AGENT_SUMMARY_REQUESTED})

        matching_event = ControlEvent(
            event_id="1",
            type=EventType.AGENT_SUMMARY_REQUESTED,
            timestamp=0,
            turn=1,
            phase=GamePhase.SUMMARY,
        )
        non_matching_event = ControlEvent(
            event_id="2",
            type=EventType.PHASE_TRANSITION,
            timestamp=0,
            turn=1,
            phase=GamePhase.SUMMARY,
        )

        assert filter.matches(matching_event) is True
        assert filter.matches(non_matching_event) is False

    def test_matches_agent_id(self):
        """测试 Agent ID 匹配。"""
        filter = EventFilter(agent_ids={"agent_a", "agent_b"})

        matching_event = ControlEvent(
            event_id="1",
            type=EventType.AGENT_SUMMARY_REQUESTED,
            timestamp=0,
            turn=1,
            phase=GamePhase.SUMMARY,
            agent_id="agent_a",
        )
        non_matching_event = ControlEvent(
            event_id="2",
            type=EventType.AGENT_SUMMARY_REQUESTED,
            timestamp=0,
            turn=1,
            phase=GamePhase.SUMMARY,
            agent_id="agent_c",
        )

        assert filter.matches(matching_event) is True
        assert filter.matches(non_matching_event) is False

    def test_matches_none_means_all(self):
        """测试 None 表示匹配所有。"""
        filter = EventFilter()  # 所有字段都是 None 或空

        event = ControlEvent(
            event_id="1",
            type=EventType.AGENT_SUMMARY_REQUESTED,
            timestamp=0,
            turn=1,
            phase=GamePhase.SUMMARY,
            agent_id="any_agent",
        )

        assert filter.matches(event) is True
