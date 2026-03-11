"""
Unit tests for MessageConverter
"""

import pytest
from datetime import datetime

from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.adapters.web.message_converter import MessageConverter


class TestMessageConverter:
    """测试 MessageConverter 类"""

    @pytest.mark.asyncio
    async def test_convert_response_event(self):
        """测试转换 Agent 响应事件"""
        event = Event(
            src="agent:governor_zhili",
            dst=["player:web"],
            type=EventType.RESPONSE,
            payload={"narrative": "陛下，直隶省..."},
            timestamp="2026-03-06T12:00:00Z",
            session_id="session:web:test",
        )

        converter = MessageConverter()
        result = await converter.convert(event)

        assert result is not None
        assert result["kind"] == "chat"
        assert result["data"]["agent"] == "governor_zhili"
        assert result["data"]["agentDisplayName"] == "直隶巡抚"
        assert result["data"]["text"] == "陛下，直隶省..."
        assert result["data"]["timestamp"] == "2026-03-06T12:00:00Z"
        assert result["data"]["session_id"] == "session:web:test"

    @pytest.mark.asyncio
    async def test_convert_chat_event(self):
        """测试转换聊天事件"""
        event = Event(
            src="player:web",
            dst=["agent:governor_zhili"],
            type=EventType.CHAT,
            payload={"message": "查看直隶省情况"},
            timestamp="2026-03-06T12:00:00Z",
            session_id="session:web:test",
        )

        converter = MessageConverter()
        result = await converter.convert(event)

        assert result is not None
        assert result["kind"] == "chat"
        assert result["data"]["agent"] == "player"
        assert result["data"]["agentDisplayName"] == "皇帝"
        assert result["data"]["text"] == "查看直隶省情况"
        assert result["data"]["session_id"] == "session:web:test"

    @pytest.mark.asyncio
    async def test_convert_unsupported_event_returns_none(self):
        """测试转换不支持的事件类型返回 None（不广播）"""
        event = Event(
            src="player:web",
            dst=["agent:governor_zhili"],
            type=EventType.USER_QUERY,
            payload={"query": "test query"},
            session_id="session:web:test",
        )

        converter = MessageConverter()
        result = await converter.convert(event)

        assert result is None  # USER_QUERY 事件不广播

    def test_extract_agent_name(self):
        """测试提取 agent 名称"""
        assert MessageConverter._extract_agent_name("agent:governor_zhili") == "governor_zhili"
        assert (
            MessageConverter._extract_agent_name("agent:minister_of_revenue")
            == "minister_of_revenue"
        )
        assert MessageConverter._extract_agent_name("player:web") == "player:web"

    def test_get_agent_display_name(self):
        """测试获取 agent 显示名称"""
        assert MessageConverter._get_agent_display_name("agent:governor_zhili") == "直隶巡抚"
        assert MessageConverter._get_agent_display_name("agent:minister_of_revenue") == "户部尚书"
        assert MessageConverter._get_agent_display_name("player:web") == "皇帝"
        # 未知 agent 返回原名称
        assert MessageConverter._get_agent_display_name("agent:unknown") == "unknown"

    def test_describe_agriculture(self):
        """测试描述农业产量"""
        # 丰收
        metrics = {"total_food_production": 1200000}
        assert MessageConverter._describe_agriculture(metrics) == "丰收"

        # 正常
        metrics = {"total_food_production": 800000}
        assert MessageConverter._describe_agriculture(metrics) == "正常"

        # 歉收
        metrics = {"total_food_production": 300000}
        assert MessageConverter._describe_agriculture(metrics) == "歉收"

    @pytest.mark.asyncio
    async def test_convert_response_without_narrative(self):
        """测试转换无 narrative 的响应事件"""
        event = Event(
            src="agent:governor_zhili",
            dst=["player:web"],
            type=EventType.RESPONSE,
            payload={},  # 没有 narrative 字段
            timestamp="2026-03-06T12:00:00Z",
            session_id="session:web:test",
        )

        converter = MessageConverter()
        result = await converter.convert(event)

        assert result is not None
        assert result["data"]["text"] == ""  # 默认为空字符串

    @pytest.mark.asyncio
    async def test_convert_without_timestamp(self):
        """测试转换无时间戳的事件"""
        event = Event(
            src="agent:governor_zhili",
            dst=["player:web"],
            type=EventType.RESPONSE,
            payload={"narrative": "测试"},
            timestamp=None,  # 无时间戳
            session_id="session:web:test",
        )

        converter = MessageConverter()
        result = await converter.convert(event)

        assert result is not None
        # 应该生成 ISO 格式的时间戳
        assert "T" in result["data"]["timestamp"]
        assert result["data"]["timestamp"].endswith("+00:00")
