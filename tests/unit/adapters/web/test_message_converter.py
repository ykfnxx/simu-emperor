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

    def test_convert_response_event(self):
        """测试转换 Agent 响应事件"""
        event = Event(
            src="agent:governor_zhili",
            dst=["player:web"],
            type=EventType.RESPONSE,
            payload={"narrative": "陛下，直隶省..."},
            timestamp="2026-03-06T12:00:00Z",
            session_id="session:web:test"
        )

        converter = MessageConverter()
        result = converter.convert(event)

        assert result is not None
        assert result["kind"] == "chat"
        assert result["data"]["agent"] == "governor_zhili"
        assert result["data"]["agentDisplayName"] == "直隶巡抚"
        assert result["data"]["text"] == "陛下，直隶省..."
        assert result["data"]["timestamp"] == "2026-03-06T12:00:00Z"

    def test_convert_turn_resolved_event(self):
        """测试转换回合结算事件"""
        event = Event(
            src="system:calculator",
            dst=["*"],
            type=EventType.TURN_RESOLVED,
            payload={
                "turn": 5,
                "state": {
                    "turn": 5,
                    "national": {"treasury": 1250000},
                    "provinces": [
                        {
                            "population": {"total": 1000000, "happiness": 85},
                            "military": {"soldiers": 50000}
                        },
                        {
                            "population": {"total": 2000000, "happiness": 75},
                            "military": {"soldiers": 30000}
                        }
                    ]
                }
            },
            session_id="session:web:test"
        )

        converter = MessageConverter()
        result = converter.convert(event)

        assert result is not None
        assert result["kind"] == "state"
        assert result["data"]["turn"] == 5
        assert result["data"]["treasury"] == 1250000
        assert result["data"]["population"] == 3000000
        assert result["data"]["military"] == 80000
        assert result["data"]["happiness"] == 80  # (85 + 75) / 2
        assert result["data"]["agriculture"] == "正常"

    def test_convert_chat_event(self):
        """测试转换聊天事件"""
        event = Event(
            src="player:web",
            dst=["agent:governor_zhili"],
            type=EventType.CHAT,
            payload={"query": "查看直隶省情况"},
            timestamp="2026-03-06T12:00:00Z",
            session_id="session:web:test"
        )

        converter = MessageConverter()
        result = converter.convert(event)

        assert result is not None
        assert result["kind"] == "chat"
        assert result["data"]["agent"] == "player"
        assert result["data"]["agentDisplayName"] == "皇帝"
        assert result["data"]["text"] == "查看直隶省情况"

    def test_convert_command_event_returns_none(self):
        """测试转换命令事件返回 None（不广播）"""
        event = Event(
            src="player:web",
            dst=["agent:governor_zhili"],
            type=EventType.COMMAND,
            payload={"intent": "adjust_tax"},
            session_id="session:web:test"
        )

        converter = MessageConverter()
        result = converter.convert(event)

        assert result is None  # COMMAND 事件不广播

    def test_extract_agent_name(self):
        """测试提取 agent 名称"""
        assert MessageConverter._extract_agent_name("agent:governor_zhili") == "governor_zhili"
        assert MessageConverter._extract_agent_name("agent:minister_of_revenue") == "minister_of_revenue"
        assert MessageConverter._extract_agent_name("player:web") == "player:web"

    def test_get_agent_display_name(self):
        """测试获取 agent 显示名称"""
        assert MessageConverter._get_agent_display_name("agent:governor_zhili") == "直隶巡抚"
        assert MessageConverter._get_agent_display_name("agent:minister_of_revenue") == "户部尚书"
        assert MessageConverter._get_agent_display_name("player:web") == "皇帝"
        # 未知 agent 返回原名称
        assert MessageConverter._get_agent_display_name("agent:unknown") == "unknown"

    def test_calculate_population(self):
        """测试计算总人口"""
        state = {
            "provinces": [
                {"population": {"total": 1000000}},
                {"population": {"total": 2000000}},
            ]
        }
        assert MessageConverter._calculate_population(state) == 3000000

    def test_calculate_population_empty(self):
        """测试空省份数据"""
        state = {"provinces": []}
        assert MessageConverter._calculate_population(state) == 0

    def test_calculate_military(self):
        """测试计算总兵力"""
        state = {
            "provinces": [
                {"military": {"soldiers": 50000}},
                {"military": {"soldiers": 30000}},
            ]
        }
        assert MessageConverter._calculate_military(state) == 80000

    def test_calculate_happiness(self):
        """测试计算平均民心"""
        state = {
            "provinces": [
                {"population": {"happiness": 85}},
                {"population": {"happiness": 75}},
            ]
        }
        assert MessageConverter._calculate_happiness(state) == 80

    def test_calculate_happiness_empty(self):
        """测试空省份数据"""
        state = {"provinces": []}
        assert MessageConverter._calculate_happiness(state) == 0

    def test_describe_agriculture(self):
        """测试描述农业产量"""
        state = {}
        # 目前返回固定值
        assert MessageConverter._describe_agriculture(state) == "正常"

    def test_convert_response_without_narrative(self):
        """测试转换无 narrative 的响应事件"""
        event = Event(
            src="agent:governor_zhili",
            dst=["player:web"],
            type=EventType.RESPONSE,
            payload={},  # 没有 narrative 字段
            timestamp="2026-03-06T12:00:00Z",
            session_id="session:web:test"
        )

        converter = MessageConverter()
        result = converter.convert(event)

        assert result is not None
        assert result["data"]["text"] == ""  # 默认为空字符串

    def test_convert_without_timestamp(self):
        """测试转换无时间戳的事件"""
        event = Event(
            src="agent:governor_zhili",
            dst=["player:web"],
            type=EventType.RESPONSE,
            payload={"narrative": "测试"},
            timestamp=None,  # 无时间戳
            session_id="session:web:test"
        )

        converter = MessageConverter()
        result = converter.convert(event)

        assert result is not None
        # 应该生成 ISO 格式的时间戳
        assert "T" in result["data"]["timestamp"]
        assert result["data"]["timestamp"].endswith("Z")
