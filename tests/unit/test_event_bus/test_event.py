"""
测试 Event 数据模型
"""

from datetime import datetime, timezone

from simu_emperor.event_bus.event import Event


class TestEvent:
    """测试 Event 类"""

    def test_event_creation(self):
        """测试事件创建"""
        event = Event(
            src="player",
            dst=["agent:revenue_minister"],
            type="command",
            payload={"action": "adjust_tax", "rate": 0.1},
            session_id="session:test",
        )

        assert event.src == "player"
        assert event.dst == ["agent:revenue_minister"]
        assert event.type == "command"
        assert event.payload == {"action": "adjust_tax", "rate": 0.1}
        assert event.event_id.startswith("evt_")
        assert event.timestamp is not None
        assert event.session_id == "session:test"

    def test_event_auto_id(self):
        """测试自动生成 event_id"""
        event1 = Event(src="player", dst=["*"], type="test", session_id="session:test")
        event2 = Event(src="player", dst=["*"], type="test", session_id="session:test")

        assert event1.event_id != event2.event_id

    def test_event_auto_timestamp(self):
        """测试自动生成 timestamp"""
        before = datetime.now(timezone.utc)
        event = Event(src="player", dst=["*"], type="test", session_id="session:test")
        after = datetime.now(timezone.utc)

        timestamp = datetime.fromisoformat(event.timestamp)
        assert before <= timestamp <= after

    def test_to_json(self):
        """测试序列化为 JSON"""
        event = Event(
            src="player",
            dst=["agent:revenue_minister"],
            type="command",
            payload={"action": "adjust_tax"},
            session_id="session:test",
        )

        json_str = event.to_json()
        assert "player" in json_str
        assert "agent:revenue_minister" in json_str
        assert "command" in json_str
        assert "session:test" in json_str

    def test_from_json(self):
        """测试从 JSON 反序列化"""
        original = Event(
            src="player",
            dst=["agent:revenue_minister"],
            type="command",
            payload={"action": "adjust_tax", "rate": 0.1},
            session_id="session:test",
        )

        json_str = original.to_json()
        restored = Event.from_json(json_str)

        assert restored.src == original.src
        assert restored.dst == original.dst
        assert restored.type == original.type
        assert restored.payload == original.payload
        assert restored.event_id == original.event_id
        assert restored.session_id == original.session_id

    def test_to_dict(self):
        """测试转换为字典"""
        event = Event(
            src="player",
            dst=["agent:revenue_minister"],
            type="command",
            payload={"action": "adjust_tax"},
            session_id="session:test",
        )

        data = event.to_dict()
        assert data["src"] == "player"
        assert data["dst"] == ["agent:revenue_minister"]
        assert data["type"] == "command"
        assert data["payload"] == {"action": "adjust_tax"}
        assert data["session_id"] == "session:test"

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "event_id": "evt_test",
            "src": "player",
            "dst": ["agent:revenue_minister"],
            "type": "command",
            "payload": {"action": "adjust_tax"},
            "timestamp": "2026-02-26T12:00:00+00:00",
        }

        event = Event.from_dict(data)
        assert event.event_id == "evt_test"
        assert event.src == "player"
        assert event.dst == ["agent:revenue_minister"]
        assert event.type == "command"
        assert event.payload == {"action": "adjust_tax"}

    def test_str_representation(self):
        """测试字符串表示"""
        event = Event(
            src="player",
            dst=["agent:revenue_minister"],
            type="command",
            event_id="evt_test",
            session_id="session:test",
        )

        str_repr = str(event)
        assert "evt_test" in str_repr
        assert "player" in str_repr
        assert "agent:revenue_minister" in str_repr
        assert "command" in str_repr
