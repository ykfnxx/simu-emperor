"""Group Chat data models for multi-agent conversations."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


@dataclass
class GroupChat:
    """群聊数据模型

    支持单用户与多个AI agent的群组对话。
    """

    # 标识
    group_id: str  # 格式: group:web:{timestamp}:{uuid}

    # 基本信息
    name: str  # 群聊名称
    agent_ids: list[str]  # 成员agent列表

    # 创建信息
    created_by: str = "player:web"  # 创建者
    created_at: datetime = field(default_factory=utcnow)

    # 关联信息
    session_id: str = ""  # 关联的主会话ID

    # 统计信息
    message_count: int = 0  # 消息计数

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "group_id": self.group_id,
            "name": self.name,
            "agent_ids": self.agent_ids,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "session_id": self.session_id,
            "message_count": self.message_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GroupChat":
        """Create GroupChat from dictionary."""
        return cls(
            group_id=data["group_id"],
            name=data["name"],
            agent_ids=data.get("agent_ids", []),
            created_by=data.get("created_by", "player:web"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else utcnow(),
            session_id=data.get("session_id", ""),
            message_count=data.get("message_count", 0),
        )
