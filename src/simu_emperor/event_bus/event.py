"""
Event 数据模型

定义事件的数据结构和序列化方法。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import uuid
from typing import Any


@dataclass
class Event:
    """
    事件数据类

    Attributes:
        event_id: 事件唯一标识符（自动生成）
        src: 事件源标识符（如 "player", "agent:revenue_minister"）
        dst: 目标标识符列表（如 ["player"], ["agent:*"], ["*"]）
        type: 事件类型（参见 EventType 类）
        payload: 事件负载数据（任意 JSON 可序列化数据）
        timestamp: 事件时间戳（自动生成，UTC 时间）
    """

    event_id: str = field(
        default_factory=lambda: (
            f"evt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
        )
    )
    src: str = ""
    dst: list[str] = field(default_factory=list)
    type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json(self) -> str:
        """
        序列化为 JSON 字符串

        Returns:
            JSON 字符串（单行，用于 JSONL 格式）
        """
        return json.dumps(
            {
                "event_id": self.event_id,
                "src": self.src,
                "dst": self.dst,
                "type": self.type,
                "payload": self.payload,
                "timestamp": self.timestamp,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "Event":
        """
        从 JSON 字符串反序列化

        Args:
            json_str: JSON 字符串

        Returns:
            Event 对象
        """
        data = json.loads(json_str)
        return cls(
            event_id=data["event_id"],
            src=data["src"],
            dst=data["dst"],
            type=data["type"],
            payload=data["payload"],
            timestamp=data["timestamp"],
        )

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典

        Returns:
            字典表示
        """
        return {
            "event_id": self.event_id,
            "src": self.src,
            "dst": self.dst,
            "type": self.type,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """
        从字典创建 Event

        Args:
            data: 字典数据

        Returns:
            Event 对象
        """
        return cls(
            event_id=data["event_id"],
            src=data["src"],
            dst=data["dst"],
            type=data["type"],
            payload=data["payload"],
            timestamp=data["timestamp"],
        )

    def __str__(self) -> str:
        """字符串表示"""
        return f"Event(id={self.event_id}, src={self.src}, dst={self.dst}, type={self.type})"

    def __repr__(self) -> str:
        """调试表示"""
        return self.__str__()
