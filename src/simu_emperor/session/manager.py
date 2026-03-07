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
    from simu_emperor.memory.manifest_index import ManifestIndex
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
        manifest_index: "ManifestIndex",
        tape_writer: "TapeWriter",
    ):
        self.memory_dir = memory_dir
        self.llm_provider = llm_provider
        self.manifest_index = manifest_index
        self.tape_writer = tape_writer

        self.manifest_path = memory_dir / "manifest.json"
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
            status = "WAITING_REPLY" if parent_id else "ACTIVE"

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
                manifest_index=self.manifest_index,
            )
            await cm.load_from_tape()
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
        manifest = await FileOperationsHelper.read_json_file(self.manifest_path)
        if manifest is None:
            manifest = {
                "version": "2.0",
                "last_updated": utcnow().isoformat(),
                "sessions": {},
            }

        manifest["last_updated"] = utcnow().isoformat()

        for session_id, session in self._sessions.items():
            manifest["sessions"][session_id] = session.to_dict()

        await FileOperationsHelper.write_json_file(self.manifest_path, manifest)

    async def load_manifest(self) -> None:
        manifest = await FileOperationsHelper.read_json_file(self.manifest_path)
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
