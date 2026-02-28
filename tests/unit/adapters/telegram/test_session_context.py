"""
SessionContextManager 单元测试

测试 Session 上下文管理器的各种功能：
- Chat Session 复用逻辑
- Command Session 每次新建逻辑
- Session 过期清理
- Session 类型查询
"""

import asyncio
import pytest
from datetime import datetime, timezone, timedelta

from simu_emperor.adapters.telegram.session_context import (
    SessionContextManager,
    EventCategory,
)


class TestSessionContextManager:
    """SessionContextManager 单元测试"""

    def test_init(self):
        """测试初始化"""
        manager = SessionContextManager(
            chat_id=123,
            base_session_id="session:telegram:123",
            chat_ttl_hours=24,
            command_ttl_hours=1,
        )

        assert manager.chat_id == 123
        assert manager.base_session_id == "session:telegram:123"
        assert manager.chat_ttl_hours == 24
        assert manager.command_ttl_hours == 1
        assert manager._chat_session_id is None
        assert manager._chat_session_expires_at is None
        assert manager._command_sessions == {}

    @pytest.mark.asyncio
    async def test_get_or_create_chat_session_first_time(self):
        """测试首次创建聊天会话"""
        manager = SessionContextManager(
            chat_id=123,
            base_session_id="session:telegram:123",
        )

        session_id = await manager.get_or_create_chat_session()

        assert session_id.startswith("session:telegram:123:chat:")
        assert manager._chat_session_id == session_id
        assert manager._chat_session_expires_at is not None

        # 检查过期时间是否正确（约 24 小时后）
        now = datetime.now(timezone.utc)
        ttl = (manager._chat_session_expires_at - now).total_seconds()
        assert 86300 <= ttl <= 86500  # 约 24 小时（允许 100 秒误差）

    @pytest.mark.asyncio
    async def test_get_or_create_chat_session_reuse(self):
        """测试聊天会话复用"""
        manager = SessionContextManager(
            chat_id=123,
            base_session_id="session:telegram:123",
        )

        # 第一次创建
        session_id_1 = await manager.get_or_create_chat_session()
        # 第二次获取（应该复用）
        session_id_2 = await manager.get_or_create_chat_session()

        assert session_id_1 == session_id_2
        assert manager._chat_session_id == session_id_1

    @pytest.mark.asyncio
    async def test_get_or_create_chat_session_expired(self):
        """测试聊天会话过期后创建新会话"""
        manager = SessionContextManager(
            chat_id=123,
            base_session_id="session:telegram:123",
            chat_ttl_hours=1,
        )

        # 创建会话
        session_id_1 = await manager.get_or_create_chat_session()

        # 手动设置过期时间为过去
        manager._chat_session_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        # 再次获取（应该创建新会话）
        session_id_2 = await manager.get_or_create_chat_session()

        assert session_id_1 != session_id_2
        assert manager._chat_session_id == session_id_2

    @pytest.mark.asyncio
    async def test_create_command_session_always_new(self):
        """测试命令会话每次都创建新的"""
        manager = SessionContextManager(
            chat_id=123,
            base_session_id="session:telegram:123",
        )

        # 创建多个命令会话
        session_id_1 = await manager.create_command_session()
        session_id_2 = await manager.create_command_session()
        session_id_3 = await manager.create_command_session()

        # 所有会话 ID 都应该不同
        assert session_id_1 != session_id_2
        assert session_id_2 != session_id_3
        assert session_id_1 != session_id_3

        # 检查格式
        assert session_id_1.startswith("session:telegram:123:cmd:")

        # 检查是否都存储在 command_sessions 中
        assert len(manager._command_sessions) == 3
        assert session_id_1 in manager._command_sessions
        assert session_id_2 in manager._command_sessions
        assert session_id_3 in manager._command_sessions

    @pytest.mark.asyncio
    async def test_get_session_for_event_chat(self):
        """测试获取聊天事件的 session_id"""
        manager = SessionContextManager(
            chat_id=123,
            base_session_id="session:telegram:123",
        )

        session_id = await manager.get_session_for_event(EventCategory.CHAT)

        assert session_id.startswith("session:telegram:123:chat:")

    @pytest.mark.asyncio
    async def test_get_session_for_event_command(self):
        """测试获取命令事件的 session_id"""
        manager = SessionContextManager(
            chat_id=123,
            base_session_id="session:telegram:123",
        )

        session_id_1 = await manager.get_session_for_event(EventCategory.COMMAND)
        session_id_2 = await manager.get_session_for_event(EventCategory.COMMAND)

        assert session_id_1.startswith("session:telegram:123:cmd:")
        assert session_id_2.startswith("session:telegram:123:cmd:")
        assert session_id_1 != session_id_2  # 每次都不同

    @pytest.mark.asyncio
    async def test_get_session_for_event_other(self):
        """测试获取其他事件的 session_id"""
        manager = SessionContextManager(
            chat_id=123,
            base_session_id="session:telegram:123",
        )

        session_id = await manager.get_session_for_event(EventCategory.OTHER)

        assert session_id == "session:telegram:123"

    def test_cleanup_expired_sessions_chat(self):
        """测试清理过期的聊天会话"""
        manager = SessionContextManager(
            chat_id=123,
            base_session_id="session:telegram:123",
            chat_ttl_hours=1,
        )

        # 创建聊天会话
        manager._chat_session_id = "session:telegram:123:chat:test"
        manager._chat_session_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        # 清理
        manager._cleanup_expired_sessions()

        assert manager._chat_session_id is None
        assert manager._chat_session_expires_at is None

    def test_cleanup_expired_sessions_command(self):
        """测试清理过期的命令会话"""
        manager = SessionContextManager(
            chat_id=123,
            base_session_id="session:telegram:123",
            command_ttl_hours=1,
        )

        # 添加命令会话（一个过期，一个未过期）
        manager._command_sessions = {
            "session:telegram:123:cmd:expired": datetime.now(timezone.utc) - timedelta(hours=1),
            "session:telegram:123:cmd:active": datetime.now(timezone.utc) + timedelta(hours=1),
        }

        # 清理
        manager._cleanup_expired_sessions()

        assert len(manager._command_sessions) == 1
        assert "session:telegram:123:cmd:active" in manager._command_sessions
        assert "session:telegram:123:cmd:expired" not in manager._command_sessions

    @pytest.mark.asyncio
    async def test_cleanup_task(self):
        """测试清理任务的启动和停止"""
        manager = SessionContextManager(
            chat_id=123,
            base_session_id="session:telegram:123",
        )

        # 启动清理任务
        await manager.start_cleanup_task(interval_seconds=0.1)
        assert manager._cleanup_task is not None

        # 等待一小段时间让任务运行
        await asyncio.sleep(0.2)

        # 停止清理任务
        await manager.stop_cleanup_task()

        # 等待任务停止
        await asyncio.sleep(0.1)

    def test_get_active_sessions(self):
        """测试获取活跃会话信息"""
        manager = SessionContextManager(
            chat_id=123,
            base_session_id="session:telegram:123",
        )

        # 添加一些会话
        manager._chat_session_id = "session:telegram:123:chat:test"
        manager._chat_session_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        manager._command_sessions = {
            "session:telegram:123:cmd:cmd1": datetime.now(timezone.utc) + timedelta(hours=1),
        }

        active = manager.get_active_sessions()

        assert "chat" in active
        assert active["chat"]["session_id"] == "session:telegram:123:chat:test"
        assert active["chat"]["expires_at"] is not None
        assert active["chat"]["ttl_seconds"] > 0

        assert "commands" in active
        assert len(active["commands"]) == 1
        assert active["commands"][0]["session_id"] == "session:telegram:123:cmd:cmd1"

    def test_clear_all(self):
        """测试清除所有会话"""
        manager = SessionContextManager(
            chat_id=123,
            base_session_id="session:telegram:123",
        )

        # 添加一些会话
        manager._chat_session_id = "session:telegram:123:chat:test"
        manager._chat_session_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        manager._command_sessions = {
            "session:telegram:123:cmd:cmd1": datetime.now(timezone.utc) + timedelta(hours=1),
        }

        # 清除所有
        manager.clear_all()

        assert manager._chat_session_id is None
        assert manager._chat_session_expires_at is None
        assert len(manager._command_sessions) == 0

    @pytest.mark.asyncio
    async def test_chat_session_reuse_scenario(self):
        """测试聊天会话复用场景"""
        manager = SessionContextManager(
            chat_id=123,
            base_session_id="session:telegram:123",
        )

        # 用户发送多条聊天消息
        session_ids = []
        for _ in range(5):
            session_id = await manager.get_session_for_event(EventCategory.CHAT)
            session_ids.append(session_id)

        # 所有聊天消息应该使用同一个 session_id
        assert len(set(session_ids)) == 1
        assert all(sid.startswith("session:telegram:123:chat:") for sid in session_ids)

    @pytest.mark.asyncio
    async def test_command_session_isolation_scenario(self):
        """测试命令会话隔离场景"""
        manager = SessionContextManager(
            chat_id=123,
            base_session_id="session:telegram:123",
        )

        # 用户执行多条命令
        session_ids = []
        for _ in range(5):
            session_id = await manager.get_session_for_event(EventCategory.COMMAND)
            session_ids.append(session_id)

        # 所有命令应该使用不同的 session_id
        assert len(set(session_ids)) == 5
        assert all(sid.startswith("session:telegram:123:cmd:") for sid in session_ids)

    @pytest.mark.asyncio
    async def test_mixed_chat_and_command_scenario(self):
        """测试混合聊天和命令场景"""
        manager = SessionContextManager(
            chat_id=123,
            base_session_id="session:telegram:123",
        )

        # 用户：聊天 -> 命令 -> 聊天 -> 命令 -> 聊天
        chat_1 = await manager.get_session_for_event(EventCategory.CHAT)
        cmd_1 = await manager.get_session_for_event(EventCategory.COMMAND)
        chat_2 = await manager.get_session_for_event(EventCategory.CHAT)
        cmd_2 = await manager.get_session_for_event(EventCategory.COMMAND)
        chat_3 = await manager.get_session_for_event(EventCategory.CHAT)

        # 聊天消息应该使用同一个 session
        assert chat_1 == chat_2 == chat_3
        assert chat_1.startswith("session:telegram:123:chat:")

        # 命令应该各自独立
        assert cmd_1 != cmd_2
        assert cmd_1.startswith("session:telegram:123:cmd:")
        assert cmd_2.startswith("session:telegram:123:cmd:")

        # 命令 session 不应该和聊天 session 混淆
        assert cmd_1 != chat_1
        assert cmd_2 != chat_2
