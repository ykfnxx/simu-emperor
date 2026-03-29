"""
Event数据模型测试
"""

import pytest
from simu_emperor.mq.event import Event


def test_event_creation():
    """测试Event创建"""
    event = Event(
        event_id="",
        event_type="CHAT",
        src="player:web:client_001",
        dst=["agent:governor_zhili"],
        session_id="session:web:001",
        payload={"message": "测试消息"},
        timestamp="",
    )

    # 自动生成event_id和timestamp
    assert event.event_id.startswith("evt_")
    assert event.timestamp != ""
    assert event.event_type == "CHAT"
    assert event.src == "player:web:client_001"
    assert event.dst == ["agent:governor_zhili"]


def test_event_serialization():
    """测试Event序列化/反序列化"""
    event = Event(
        event_id="evt_test",
        event_type="CHAT",
        src="player:web:001",
        dst=["agent:governor_zhili"],
        session_id="session:001",
        payload={"message": "测试"},
        timestamp="2026-03-29T10:00:00",
    )

    # 序列化
    json_str = event.to_json()
    assert isinstance(json_str, str)
    assert "evt_test" in json_str

    # 反序列化
    deserialized = Event.from_json(json_str)
    assert deserialized.event_id == event.event_id
    assert deserialized.event_type == event.event_type
    assert deserialized.src == event.src
    assert deserialized.dst == event.dst
    assert deserialized.session_id == event.session_id
    assert deserialized.payload == event.payload


def test_event_multicast():
    """测试多播事件"""
    event = Event(
        event_id="",
        event_type="AGENT_MESSAGE",
        src="agent:governor",
        dst=["agent:minister1", "agent:minister2", "agent:minister3"],
        session_id="session:group",
        payload={"message": "群聊消息"},
        timestamp="",
    )

    assert len(event.dst) == 3
    assert "agent:minister1" in event.dst


def test_event_to_dict_from_dict():
    """测试dict转换"""
    event = Event(
        event_id="evt_dict_test",
        event_type="COMMAND",
        src="player:cli",
        dst=["engine:*"],
        session_id="session:cli:001",
        payload={"command": "tick"},
        timestamp="2026-03-29T11:00:00",
    )

    d = event.to_dict()
    assert d["event_id"] == "evt_dict_test"
    assert d["event_type"] == "COMMAND"

    restored = Event.from_dict(d)
    assert restored.event_id == event.event_id
    assert restored.event_type == event.event_type
    assert restored.payload == event.payload
