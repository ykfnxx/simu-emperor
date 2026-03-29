"""
Event数据模型 - V5 ZeroMQ消息格式

基于 SPEC 01-event-bus.md §3.1
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass
class Event:
    """
    ZeroMQ事件消息

    Attributes:
        event_id: UUID, 唯一标识
        event_type: 事件类型(见 SPEC §3.2)
        src: 发送方ID, 如 "player:web:client_001"
        dst: 目标列表, 支持多播
        session_id: 会话ID
        payload: 事件内容
        timestamp: ISO 8601格式
    """

    event_id: str
    event_type: str
    src: str
    dst: list[str]
    session_id: str
    payload: dict[str, Any]
    timestamp: str

    def __post_init__(self):
        """自动生成event_id和timestamp(如果未提供)"""
        if not self.event_id:
            self.event_id = f"evt_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}"
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_json(self) -> str:
        """序列化为JSON字符串"""
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> "Event":
        """从JSON字符串反序列化"""
        obj = json.loads(data)
        return cls(**obj)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """从字典创建"""
        return cls(**data)
