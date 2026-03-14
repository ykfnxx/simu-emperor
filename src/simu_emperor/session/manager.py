"""SessionManager for managing session lifecycle."""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from simu_emperor.common import FileOperationsHelper
from simu_emperor.session.constants import MAX_TASK_DEPTH
from simu_emperor.session.models import Session

if TYPE_CHECKING:
    from simu_emperor.llm.base import LLMProvider
    from simu_emperor.memory.tape_metadata import TapeMetadataManager
    from simu_emperor.memory.tape_writer import TapeWriter
    from simu_emperor.memory.context_manager import ContextManager


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SessionManager:
    """Session 生命周期管理器"""

    def __init__(
        self,
        memory_dir: Path,
        llm_provider: "LLMProvider",
        tape_metadata_mgr: "TapeMetadataManager",
        tape_writer: "TapeWriter",
    ):
        self.memory_dir = memory_dir
        self.llm_provider = llm_provider
        self.tape_metadata_mgr = tape_metadata_mgr
        self.tape_writer = tape_writer

        # V4: Session 状态持久化到 session_manifest.json（与 tape_meta.jsonl 分离）
        self.session_manifest_path = memory_dir / "session_manifest.json"
        self._sessions: dict[str, Session] = {}
        self._context_managers: dict[str, "ContextManager"] = {}

    def get_tape_path(self, session_id: str, agent_id: str) -> Path:
        return self.tape_writer._get_tape_path(session_id, agent_id)

    async def create_session(
        self,
        session_id: str | None = None,
        parent_id: str | None = None,
        created_by: str = "",
        timeout_seconds: int | None = None,
        status: str | None = None,
        **kwargs,
    ) -> Session:
        if parent_id:
            parent = self._sessions.get(parent_id)
            if parent is None:
                raise ValueError(f"Parent session not found: {parent_id}")

            depth = self._calculate_depth(parent_id)
            if depth >= MAX_TASK_DEPTH:
                raise ValueError(f"Task nesting depth exceeded: {depth + 1} > {MAX_TASK_DEPTH}")

        if session_id is None:
            session_id = self._generate_session_id(created_by)

        if status is None:
            # All sessions (including task sessions) default to ACTIVE status
            # WAITING_REPLY status is only set when async tool calls are made
            status = "ACTIVE"

        session = Session(
            session_id=session_id,
            parent_id=parent_id,
            created_by=created_by,
            status=status,
            timeout_at=self._calc_timeout(timeout_seconds),
        )

        if parent_id:
            parent = self._sessions.get(parent_id)
            if parent:
                parent.child_ids.append(session_id)

        self._sessions[session_id] = session
        await self.save_manifest()

        return session

    async def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    async def set_agent_state(self, session_id: str, agent_id: str, status: str) -> None:
        """设置某个 agent 在 session 中的状态

        Args:
            session_id: Session ID
            agent_id: Agent ID (格式: "agent:xxx" 或 "xxx")
            status: 状态 (ACTIVE/WAITING_REPLY/FINISHED/FAILED)
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # 规范化 agent_id 格式
        normalized_id = agent_id if agent_id.startswith("agent:") else f"agent:{agent_id}"

        session.agent_states[normalized_id] = status
        session.updated_at = datetime.now(timezone.utc)
        await self.save_manifest()

    async def get_agent_state(self, session_id: str, agent_id: str) -> str | None:
        """获取某个 agent 在 session 中的状态

        如果 agent 未在 session 中注册，自动初始化为 ACTIVE 状态（惰性初始化）。

        Args:
            session_id: Session ID
            agent_id: Agent ID (格式: "agent:xxx" 或 "xxx")

        Returns:
            Agent 状态 (ACTIVE/WAITING_REPLY/FINISHED/FAILED)，如果 session 不存在则返回 None
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        # 规范化 agent_id 格式
        normalized_id = agent_id if agent_id.startswith("agent:") else f"agent:{agent_id}"

        # 惰性初始化：首次访问时自动设置为 ACTIVE
        if normalized_id not in session.agent_states:
            session.agent_states[normalized_id] = "ACTIVE"
            await self.save_manifest()

        return session.agent_states[normalized_id]

    async def update_session(self, session_id: str, **updates) -> None:
        session = self._sessions.get(session_id)
        if session:
            for key, value in updates.items():
                if hasattr(session, key):
                    setattr(session, key, value)
            session.updated_at = datetime.now(timezone.utc)
            await self.save_manifest()

    async def add_child(self, parent_id: str, child_id: str) -> None:
        parent = self._sessions.get(parent_id)
        if parent and child_id not in parent.child_ids:
            parent.child_ids.append(child_id)
            await self.save_manifest()

    def get_parent_chain(self, session_id: str) -> list[Session]:
        chain = []
        current = self._sessions.get(session_id)

        while current and current.parent_id:
            parent = self._sessions.get(current.parent_id)
            if parent:
                chain.append(parent)
                current = parent
            else:
                break

        return chain

    def _calculate_depth(self, session_id: str) -> int:
        depth = 0
        current = self._sessions.get(session_id)

        while current and current.parent_id:
            depth += 1
            parent = self._sessions.get(current.parent_id)
            if parent:
                current = parent
            else:
                break

        return depth

    def get_waiting_sessions(self) -> list[Session]:
        return [s for s in self._sessions.values() if s.status == "WAITING_REPLY"]

    async def increment_async_replies(self, session_id: str, agent_id: str, count: int = 1) -> None:
        """增加异步响应计数，并设置调用者 agent 的状态为 WAITING_REPLY

        Args:
            session_id: Session ID
            agent_id: 发起异步调用的 agent ID
            count: 增加的计数
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        session.pending_async_replies += count
        session.updated_at = datetime.now(timezone.utc)

        # 设置调用者 agent 的状态为 WAITING_REPLY
        await self.set_agent_state(session_id, agent_id, "WAITING_REPLY")

        await self.save_manifest()

    async def decrement_async_replies(
        self, session_id: str, agent_id: str, count: int = 1
    ) -> tuple[bool, int]:
        """减少异步响应计数，当计数归零时恢复 agent 状态为 ACTIVE

        Args:
            session_id: Session ID
            agent_id: 发起异步调用的 agent ID
            count: 减少的计数

        Returns:
            (是否收到所有回复, 当前剩余计数)
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        session.pending_async_replies = max(0, session.pending_async_replies - count)
        session.updated_at = datetime.now(timezone.utc)

        all_replies_received = session.pending_async_replies == 0

        if all_replies_received:
            # 恢复 agent 状态为 ACTIVE
            await self.set_agent_state(session_id, agent_id, "ACTIVE")

        await self.save_manifest()

        return (all_replies_received, session.pending_async_replies)

    async def get_context_manager(
        self, session_id: str, agent_id: str, include_ancestors: bool = False
    ) -> "ContextManager":
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")

        cache_key = f"{session_id}:{agent_id}"

        if cache_key not in self._context_managers:
            from simu_emperor.memory.context_manager import ContextManager, ContextConfig

            tape_path = self.get_tape_path(session_id, agent_id)
            cm = ContextManager(
                session_id=session_id,
                agent_id=agent_id,
                tape_path=tape_path,
                config=ContextConfig(),
                llm_provider=self.llm_provider,
                session_manager=self,
                # V4: 传递 tape_metadata_mgr 和 tape_writer
                tape_metadata_mgr=self.tape_metadata_mgr,
                tape_writer=self.tape_writer,
            )
            await cm.load_from_tape(include_ancestors=include_ancestors)
            self._context_managers[cache_key] = cm

        return self._context_managers[cache_key]

    async def remove_from_waiting_list(
        self,
        parent_session_id: str,
        task_session_id: str,
    ) -> tuple[bool, list[str]]:
        parent = self._sessions.get(parent_session_id)
        if not parent:
            raise ValueError(f"Parent session not found: {parent_session_id}")

        if task_session_id in parent.waiting_for_tasks:
            parent.waiting_for_tasks.remove(task_session_id)
            await self.save_manifest()

        return (len(parent.waiting_for_tasks) == 0, parent.waiting_for_tasks)

    async def save_manifest(self) -> None:
        """V4: 保存 Session 状态到 session_manifest.json"""
        manifest = await FileOperationsHelper.read_json_file(self.session_manifest_path)
        if manifest is None:
            manifest = {
                "version": "2.0",
                "last_updated": utcnow().isoformat(),
                "sessions": {},
            }

        # Ensure "sessions" key exists
        if "sessions" not in manifest:
            manifest["sessions"] = {}

        manifest["last_updated"] = utcnow().isoformat()

        for session_id, session in self._sessions.items():
            manifest["sessions"][session_id] = session.to_dict()

        await FileOperationsHelper.write_json_file(self.session_manifest_path, manifest)

    async def load_manifest(self) -> None:
        """V4: 从 session_manifest.json 加载 Session 状态"""
        manifest = await FileOperationsHelper.read_json_file(self.session_manifest_path)
        if manifest is None:
            return

        sessions_data = manifest.get("sessions", {})
        for session_id, session_data in sessions_data.items():
            self._sessions[session_id] = Session.from_dict(session_id, session_data)

    def _generate_session_id(self, created_by: str) -> str:
        timestamp = utcnow().strftime("%Y%m%d%H%M%S")
        suffix = uuid.uuid4().hex[:8]

        if created_by.startswith("agent:"):
            agent_name = created_by.replace("agent:", "")
            return f"task:{agent_name}:{timestamp}:{suffix}"
        else:
            return f"session:{timestamp}:{suffix}"

    def _calc_timeout(self, timeout_seconds: int | None) -> datetime | None:
        if timeout_seconds is None:
            return None
        return utcnow() + timedelta(seconds=timeout_seconds)


from datetime import timedelta
