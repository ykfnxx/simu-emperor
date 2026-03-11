"""Tape Service - Event tape query service."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simu_emperor.session.manager import SessionManager
    from simu_emperor.memory.tape_writer import TapeWriter


logger = logging.getLogger(__name__)


class TapeService:
    """Tape query service.

    Responsibilities:
    - Tape event queries
    - Sub-session management
    - Event retrieval from tape files
    """

    def __init__(
        self,
        session_manager: "SessionManager",
        tape_writer: "TapeWriter",
        memory_dir: Path,
    ) -> None:
        """Initialize TapeService.

        Args:
            session_manager: Session lifecycle manager
            tape_writer: Tape writer for getting tape paths
            memory_dir: Memory storage directory
        """
        self.session_manager = session_manager
        self.tape_writer = tape_writer
        self.memory_dir = memory_dir

    async def get_current_tape(
        self,
        limit: int = 100,
        agent_id: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        """Get tape events for current (or specified) agent/session.

        Args:
            limit: Maximum number of events to return (0 = all)
            agent_id: Agent ID filter
            session_id: Session ID filter

        Returns:
            Dict with agent_id, session_id, events list, and total count
        """
        from simu_emperor.common.file_utils import FileOperationsHelper

        normalized_agent = self._normalize_agent_id(agent_id) if agent_id else None
        target_session_id = session_id or "session:web:main"

        events: list[dict] = []

        # Get tape paths
        tape_paths = self._iter_session_tape_paths(target_session_id, normalized_agent)
        if not tape_paths and normalized_agent is None:
            tape_paths = self._iter_session_tape_paths(target_session_id)

        # Read events from tape files
        for tape_path in tape_paths:
            current_agent_id = tape_path.parent.parent.parent.name
            tape_events = await FileOperationsHelper.read_jsonl_file(tape_path)
            for event in tape_events:
                event["agent_id"] = current_agent_id
                events.append(event)

        # Sort by timestamp
        events.sort(key=lambda item: item.get("timestamp", ""))
        total_events = len(events)

        # Apply limit
        if limit > 0:
            events = events[-limit:]

        return {
            "agent_id": normalized_agent,
            "session_id": target_session_id,
            "events": events,
            "total": total_events,
        }

    async def get_tape_with_subs(
        self,
        limit: int = 100,
        agent_id: str | None = None,
        session_id: str | None = None,
        sub_sessions: list[str] | None = None,
    ) -> dict:
        """Get tape events including sub-sessions.

        Args:
            limit: Maximum events per session
            agent_id: Agent ID filter
            session_id: Main session ID
            sub_sessions: List of sub-session IDs to include

        Returns:
            Dict with main session events and sub-session events
        """
        result = await self.get_current_tape(limit, agent_id, session_id)
        result["sub_sessions"] = []

        if sub_sessions:
            for sub_id in sub_sessions:
                sub_tape = await self.get_current_tape(limit, agent_id, sub_id)
                sub_tape["session_id"] = sub_id
                result["sub_sessions"].append(sub_tape)

        return result

    async def get_sub_sessions(
        self,
        parent_session_id: str,
        agent_id: str | None = None,
    ) -> list[dict]:
        """Get all sub-sessions (task sessions) for a parent session.

        Args:
            parent_session_id: Parent session ID
            agent_id: Optional agent filter

        Returns:
            List of sub-session info dicts
        """
        from simu_emperor.common.file_utils import FileOperationsHelper

        if not self.session_manager:
            return []

        sub_sessions = []
        manifest = await FileOperationsHelper.read_json_file(self.memory_dir / "manifest.json") or {}
        manifest_sessions = manifest.get("sessions", {}) if isinstance(manifest, dict) else {}

        for session_id, session_data in manifest_sessions.items():
            # Skip non-task sessions
            if not self._is_task_session(session_id):
                continue

            # Check parent
            parent_id = session_data.get("parent_id")
            if parent_id != parent_session_id:
                continue

            # Filter by agent if specified
            if agent_id:
                agent_data = session_data.get("agents", {}).get(agent_id)
                if not agent_data:
                    continue

            # Calculate depth
            depth = self._calculate_depth(session_id, manifest_sessions)

            sub_sessions.append({
                "session_id": session_id,
                "parent_id": parent_id,
                "status": session_data.get("status", "ACTIVE"),
                "created_at": session_data.get("created_at", ""),
                "event_count": session_data.get("event_count", 0),
                "depth": depth,
            })

        return sorted(sub_sessions, key=lambda s: s["created_at"], reverse=True)

    def _iter_session_tape_paths(
        self,
        session_id: str,
        agent_id: str | None = None,
    ) -> list[Path]:
        """Get tape file paths for a session.

        Args:
            session_id: Session ID
            agent_id: Optional agent filter

        Returns:
            List of tape file paths
        """
        if agent_id:
            tape_path = (
                self.memory_dir
                / "agents"
                / agent_id
                / "sessions"
                / session_id
                / "tape.jsonl"
            )
            return [tape_path] if tape_path.exists() else []

        agent_root = self.memory_dir / "agents"
        if not agent_root.exists():
            return []

        paths: list[Path] = []
        for agent_dir in agent_root.iterdir():
            if not agent_dir.is_dir():
                continue
            tape_path = agent_dir / "sessions" / session_id / "tape.jsonl"
            if tape_path.exists():
                paths.append(tape_path)
        return paths

    def _is_main_session(self, session_id: str) -> bool:
        """Check if session is a main session."""
        return session_id.startswith("session:web:") or session_id.startswith("session:telegram:")

    def _is_task_session(self, session_id: str) -> bool:
        """Check if session is a task session."""
        return session_id.startswith("task:")

    def _calculate_depth(self, session_id: str, sessions: dict) -> int:
        """Calculate nesting depth of a session."""
        depth = 0
        current = sessions.get(session_id, {})

        while current:
            parent_id = current.get("parent_id")
            if not parent_id:
                break
            depth += 1
            current = sessions.get(parent_id, {})

        return depth

    def _normalize_agent_id(self, agent_id: str) -> str:
        """Normalize agent ID (remove agent: prefix)."""
        if agent_id.startswith("agent:"):
            return agent_id.replace("agent:", "", 1)
        return agent_id
