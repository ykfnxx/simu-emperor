"""
测试 EventBus 核心功能
"""

import pytest
import asyncio

from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType


class TestEventBus:
    """测试 EventBus 类"""

    @pytest.fixture
    def event_bus(self):
        """创建 EventBus 实例"""
        return EventBus()

    @pytest.mark.asyncio
    async def test_subscribe_and_unsubscribe(self, event_bus):
        """测试订阅和取消订阅"""

        async def handler(event: Event):
            pass

        # 订阅
        event_bus.subscribe("player", handler)
        subscribers = event_bus.get_subscribers()
        assert "player" in subscribers
        assert handler in subscribers["player"]

        # 取消订阅
        result = event_bus.unsubscribe("player", handler)
        assert result is True

        subscribers = event_bus.get_subscribers()
        assert "player" not in subscribers

    @pytest.mark.asyncio
    async def test_unsubscribe_non_existent(self, event_bus):
        """测试取消不存在的订阅"""

        async def handler(event: Event):
            pass

        result = event_bus.unsubscribe("player", handler)
        assert result is False

    @pytest.mark.asyncio
    async def test_subscribe_non_callable(self, event_bus):
        """测试订阅非可调用对象"""
        with pytest.raises(TypeError):
            event_bus.subscribe("player", "not_callable")

    @pytest.mark.asyncio
    async def test_exact_match_routing(self, event_bus):
        """测试精确匹配路由"""
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        event_bus.subscribe("player", handler)

        event = Event(src="agent:test", dst=["player"], type=EventType.RESPONSE, session_id="session:test")
        await event_bus.send_event(event)

        # 等待异步任务完成
        await asyncio.sleep(0.1)

        assert len(received_events) == 1
        assert received_events[0].type == EventType.RESPONSE

    @pytest.mark.asyncio
    async def test_wildcard_routing(self, event_bus):
        """测试广播路由"""
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        event_bus.subscribe("*", handler)

        event = Event(src="player", dst=["agent:test"], type=EventType.COMMAND, session_id="session:test")
        await event_bus.send_event(event)

        await asyncio.sleep(0.1)

        assert len(received_events) == 1

    @pytest.mark.asyncio
    async def test_agent_prefix_routing(self, event_bus):
        """测试 Agent 前缀路由"""
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        event_bus.subscribe("agent:*", handler)

        event = Event(src="player", dst=["agent:revenue_minister"], type=EventType.COMMAND, session_id="session:test")
        await event_bus.send_event(event)

        await asyncio.sleep(0.1)

        assert len(received_events) == 1

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, event_bus):
        """测试多个订阅者"""
        received_1 = []
        received_2 = []

        async def handler_1(event: Event):
            received_1.append(event)

        async def handler_2(event: Event):
            received_2.append(event)

        event_bus.subscribe("player", handler_1)
        event_bus.subscribe("player", handler_2)

        event = Event(src="agent:test", dst=["player"], type=EventType.RESPONSE, session_id="session:test")
        await event_bus.send_event(event)

        await asyncio.sleep(0.1)

        assert len(received_1) == 1
        assert len(received_2) == 1

    @pytest.mark.asyncio
    async def test_no_handler_for_event(self, event_bus):
        """测试没有处理器的事件"""
        # 不应该抛出异常
        event = Event(src="player", dst=["non_existent"], type=EventType.COMMAND, session_id="session:test")
        await event_bus.send_event(event)

        await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_deduplicate_handlers(self, event_bus):
        """测试处理器去重"""
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        # 同一个处理器订阅多次
        event_bus.subscribe("*", handler)
        event_bus.subscribe("player", handler)

        event = Event(src="agent:test", dst=["player"], type=EventType.RESPONSE, session_id="session:test")
        await event_bus.send_event(event)

        await asyncio.sleep(0.1)

        # 应该只调用一次
        assert len(received_events) == 1

    @pytest.mark.asyncio
    async def test_sync_handler(self, event_bus):
        """测试同步处理器"""
        received_events = []

        def handler(event: Event):
            received_events.append(event)

        event_bus.subscribe("player", handler)

        event = Event(src="agent:test", dst=["player"], type=EventType.RESPONSE, session_id="session:test")
        await event_bus.send_event(event)

        await asyncio.sleep(0.1)

        assert len(received_events) == 1

    @pytest.mark.asyncio
    async def test_clear_subscribers(self, event_bus):
        """测试清除所有订阅者"""

        async def handler(event: Event):
            pass

        event_bus.subscribe("player", handler)
        event_bus.subscribe("agent:*", handler)

        assert len(event_bus.get_subscribers()) > 0

        event_bus.clear_subscribers()

        assert len(event_bus.get_subscribers()) == 0

    @pytest.mark.asyncio
    async def test_multiple_dst(self, event_bus):
        """测试多个目标"""
        received_player = []
        received_agent = []

        async def player_handler(event: Event):
            received_player.append(event)

        async def agent_handler(event: Event):
            received_agent.append(event)

        event_bus.subscribe("player", player_handler)
        event_bus.subscribe("agent:test", agent_handler)

        event = Event(
            src="system",
            dst=["player", "agent:test"],
            type=EventType.TURN_RESOLVED,
            session_id="session:test",
        )
        await event_bus.send_event(event)

        await asyncio.sleep(0.1)

        assert len(received_player) == 1
        assert len(received_agent) == 1

    def test_send_event_sync(self, event_bus):
        """测试同步发送事件"""
        received_events = []

        def handler(event: Event):
            received_events.append(event)

        event_bus.subscribe("player", handler)

        event = Event(src="agent:test", dst=["player"], type=EventType.RESPONSE, session_id="session:test")
        event_bus.send_event_sync(event)

        # 由于是 fire-and-forget，需要等待事件循环
        import asyncio

        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.1))

        assert len(received_events) == 1
