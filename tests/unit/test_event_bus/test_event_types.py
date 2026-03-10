"""
测试 EventType 常量
"""

from simu_emperor.event_bus.event_types import EventType


class TestEventType:
    """测试 EventType 类"""

    def test_all_event_types(self):
        """测试获取所有事件类型"""
        all_types = EventType.all()

        assert EventType.COMMAND in all_types
        assert EventType.CHAT in all_types
        assert EventType.RESPONSE in all_types
        assert EventType.AGENT_MESSAGE in all_types
        assert EventType.SESSION_STATE in all_types
        assert EventType.TICK_COMPLETED in all_types
        assert EventType.TASK_CREATED in all_types
        assert EventType.TASK_FINISHED in all_types
        assert EventType.TASK_FAILED in all_types
        assert EventType.TASK_TIMEOUT in all_types

    def test_is_valid(self):
        """测试验证事件类型"""
        assert EventType.is_valid("command")
        assert EventType.is_valid("chat")

        # 无效类型
        assert not EventType.is_valid("invalid_type")
        assert not EventType.is_valid("")
        assert not EventType.is_valid("query")  # QUERY removed

    def test_player_events(self):
        """测试玩家事件类型"""
        player_events = EventType.player_events()

        assert EventType.COMMAND in player_events
        assert EventType.CHAT in player_events

        assert EventType.RESPONSE not in player_events

    def test_agent_events(self):
        """测试 Agent 事件类型"""
        agent_events = EventType.agent_events()

        assert EventType.RESPONSE in agent_events
        assert EventType.AGENT_MESSAGE in agent_events
        assert EventType.TASK_CREATED in agent_events
        assert EventType.TASK_FINISHED in agent_events
        assert EventType.TASK_FAILED in agent_events

        assert EventType.COMMAND not in agent_events

    def test_system_events(self):
        """测试系统事件类型"""
        system_events = EventType.system_events()

        assert EventType.TASK_TIMEOUT in system_events
        assert EventType.SESSION_STATE in system_events
        assert EventType.TICK_COMPLETED in system_events

        assert EventType.COMMAND not in system_events
        assert EventType.RESPONSE not in system_events
