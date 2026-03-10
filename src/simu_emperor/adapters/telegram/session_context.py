"""
Session Context Manager - Telegram Bot Session 切换机制

负责管理 Telegram Bot 的 Session 类型：
- Chat Session（聊天会话）：长期会话，可复用，用于维持连续对话上下文
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta


logger = logging.getLogger(__name__)


class SessionType:
    """Session 类型常量"""

    CHAT = "chat"


class EventCategory:
    """事件类别常量"""

    CHAT = "chat"
    OTHER = "other"


class SessionContextManager:
    """
    Session 上下文管理器

    管理单个 Telegram 用户的多种 Session 类型：
    - Chat Session: 24h TTL，可复用

    Attributes:
        chat_id: Telegram 聊天 ID
        base_session_id: 基础会话 ID（格式：session:telegram:{chat_id}）
        chat_ttl_hours: 聊天会话存活时间（小时）
    """

    CHAT_SESSION_TYPE: str = SessionType.CHAT

    def __init__(
        self,
        chat_id: int,
        base_session_id: str,
        chat_ttl_hours: int = 24,
        command_ttl_hours: int = 1,
    ):
        self.chat_id = chat_id
        self.base_session_id = base_session_id
        self.chat_ttl_hours = chat_ttl_hours
        self.command_ttl_hours = command_ttl_hours

        self._chat_session_id: str | None = None
        self._chat_session_expires_at: datetime | None = None

        self._command_sessions: dict[str, datetime] = {}

        self._cleanup_task: asyncio.Task | None = None

        logger.info(
            f"SessionContextManager initialized for chat_id={chat_id}, chat_ttl={chat_ttl_hours}h"
        )

    def _generate_chat_session_id(self) -> str:
        """生成聊天会话 ID（复用或新建）"""
        # 如果已有活跃的 chat session 且未过期，复用
        if self._chat_session_id and self._chat_session_expires_at:
            if datetime.now(timezone.utc) < self._chat_session_expires_at:
                logger.debug(f"Reusing existing chat session: {self._chat_session_id}")
                return self._chat_session_id

        # 创建新的 chat session
        session_uuid = uuid.uuid4().hex[:12]
        new_session_id = f"{self.base_session_id}:chat:{session_uuid}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=self.chat_ttl_hours)

        self._chat_session_id = new_session_id
        self._chat_session_expires_at = expires_at

        logger.info(
            f"Created new chat session: {new_session_id}, expires at {expires_at.isoformat()}"
        )
        return new_session_id

    def _generate_command_session_id(self) -> str:
        """生成命令会话 ID（每次新建）- 已废弃，仅保留向后兼容"""
        timestamp = int(datetime.now(timezone.utc).timestamp())
        session_uuid = uuid.uuid4().hex[:8]
        new_session_id = f"{self.base_session_id}:cmd:{timestamp}_{session_uuid}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=self.command_ttl_hours)
        self._command_sessions[new_session_id] = expires_at
        logger.info(
            f"Created new command session: {new_session_id}, expires at {expires_at.isoformat()}"
        )
        return new_session_id

    async def get_or_create_chat_session(self) -> str:
        """获取或创建聊天会话（复用逻辑）"""
        return self._generate_chat_session_id()

    async def create_command_session(self) -> str:
        """创建新的命令会话（每次新建）- 已废弃，返回 chat session"""
        return await self.get_or_create_chat_session()

    async def get_session_for_event(self, event_category: str = "other") -> str:
        """根据事件类型返回对应的 session_id"""
        if event_category == "chat":
            return await self.get_or_create_chat_session()
        elif event_category == "command":
            return await self.get_or_create_chat_session()
        else:
            return self.base_session_id

    def _cleanup_expired_sessions(self) -> None:
        """清理过期的 session"""
        now = datetime.now(timezone.utc)

        # 清理过期的 chat session
        if self._chat_session_expires_at and now >= self._chat_session_expires_at:
            logger.debug(f"Chat session expired: {self._chat_session_id}")
            self._chat_session_id = None
            self._chat_session_expires_at = None

        # 清理过期的 command sessions
        expired_commands = [
            sid for sid, expires in self._command_sessions.items() if now >= expires
        ]
        for sid in expired_commands:
            logger.debug(f"Command session expired: {sid}")
            del self._command_sessions[sid]

        if expired_commands:
            logger.debug(f"Cleaned up {len(expired_commands)} expired command sessions")

    async def start_cleanup_task(self, interval_seconds: int = 3600) -> None:
        """
        启动定期清理任务

        Args:
            interval_seconds: 清理间隔（秒），默认 3600（1 小时）
        """
        if self._cleanup_task and not self._cleanup_task.done():
            logger.warning("Cleanup task already running")
            return

        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(interval_seconds)
                    self._cleanup_expired_sessions()
                    logger.debug("Session cleanup completed")
                except asyncio.CancelledError:
                    logger.info("Cleanup task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in cleanup task: {e}", exc_info=True)

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(f"Started session cleanup task (interval={interval_seconds}s)")

    async def stop_cleanup_task(self) -> None:
        """停止清理任务"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped session cleanup task")

    def get_active_sessions(self) -> dict[str, dict]:
        """
        获取所有活跃的 session 信息（调试用）

        Returns:
            字典，包含 chat 和 command sessions 信息
        """
        result = {}

        if self._chat_session_id and self._chat_session_expires_at:
            result["chat"] = {
                "session_id": self._chat_session_id,
                "expires_at": self._chat_session_expires_at.isoformat(),
                "ttl_seconds": (
                    self._chat_session_expires_at - datetime.now(timezone.utc)
                ).total_seconds(),
            }

        result["commands"] = [
            {
                "session_id": sid,
                "expires_at": expires.isoformat(),
                "ttl_seconds": (expires - datetime.now(timezone.utc)).total_seconds(),
            }
            for sid, expires in self._command_sessions.items()
        ]

        return result

    def clear_all(self) -> None:
        """清除所有 session（测试用）"""
        self._chat_session_id = None
        self._chat_session_expires_at = None
        self._command_sessions.clear()
        logger.info("Cleared all sessions")
