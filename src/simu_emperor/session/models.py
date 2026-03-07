"""Session data models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


@dataclass
class Session:
    """统一的 Session 数据结构

    Main Session 和 Task Session 使用相同结构，通过 parent_id 区分。
    Task 嵌套深度上限为 5 层。
    """

    # 标识
    session_id: str

    # 层级关系
    parent_id: str | None = None
    child_ids: list[str] = field(default_factory=list)

    # 状态
    status: str = "ACTIVE"
    # ACTIVE: 活跃（Main Session 默认）
    # WAITING_REPLY: 等待回复
    #   - Task Session: 等待其他 Agent 处理
    #   - Main Session: Agent 创建了 task，暂停处理
    # FINISHED: 已完成
    # FAILED: 已失败

    # 创建者
    created_by: str = ""  # "player" 或 "agent:xxx"

    # Task 专用字段 (Main Session 时为 None)
    timeout_at: datetime | None = None  # 超时时间
    timeout_notified_at: datetime | None = None  # 超时通知时间（单次通知）
    root_event_id: str | None = None  # 触发此 Task 的事件 ID

    # 等待管理（Main Session 专用）
    waiting_for_tasks: list[str] = field(default_factory=list)  # 正在等待的 task 列表

    # 时间戳
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    @property
    def is_task(self) -> bool:
        """是否为 Task Session"""
        return self.parent_id is not None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "parent_id": self.parent_id,
            "child_ids": self.child_ids,
            "status": self.status,
            "created_by": self.created_by,
            "timeout_at": self.timeout_at.isoformat() if self.timeout_at else None,
            "timeout_notified_at": self.timeout_notified_at.isoformat()
            if self.timeout_notified_at
            else None,
            "root_event_id": self.root_event_id,
            "waiting_for_tasks": self.waiting_for_tasks,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, session_id: str, data: dict) -> "Session":
        """Create Session from dictionary."""

        def parse_datetime(value: str | None) -> datetime | None:
            if value is None:
                return None
            return datetime.fromisoformat(value)

        return cls(
            session_id=session_id,
            parent_id=data.get("parent_id"),
            child_ids=data.get("child_ids", []),
            status=data.get("status", "ACTIVE"),
            created_by=data.get("created_by", ""),
            timeout_at=parse_datetime(data.get("timeout_at")),
            timeout_notified_at=parse_datetime(data.get("timeout_notified_at")),
            root_event_id=data.get("root_event_id"),
            waiting_for_tasks=data.get("waiting_for_tasks", []),
            created_at=parse_datetime(data.get("created_at")) or utcnow(),
            updated_at=parse_datetime(data.get("updated_at")) or utcnow(),
        )
