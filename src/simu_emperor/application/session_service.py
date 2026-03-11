"""Session Service - Session management business logic."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from simu_emperor.session.manager import SessionManager
    from simu_emperor.memory.manifest_index import ManifestIndex
    from simu_emperor.application.agent_service import AgentService


logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SessionService:
    """Session business service.

    Responsibilities:
    - Session creation/selection/listing
    - Agent-to-session binding
    - Session context management
    """

    def __init__(
        self,
        session_manager: "SessionManager",
        manifest_index: "ManifestIndex",
        memory_dir: Path,
        agent_service: "AgentService | None" = None,
    ) -> None:
        """Initialize SessionService.

        Args:
            session_manager: Session lifecycle manager
            manifest_index: Session metadata index
            memory_dir: Memory storage directory
            agent_service: Agent service for availability checks
        """
        self.session_manager = session_manager
        self.manifest_index = manifest_index
        self.memory_dir = memory_dir
        self.agent_service = agent_service

        # Track session metadata
        self._session_titles: dict[str, str] = {}
        self._current_session_by_agent: dict[str, str] = {}
        self._main_session_id = "session:web:main"

    async def create_session(
        self,
        name: str | None = None,
        agent_id: str | None = None,
    ) -> dict:
        """Create a new session for an agent.

        Args:
            name: Optional session name
            agent_id: Agent to associate with session

        Returns:
            Session info dict with session_id, title, created_at, etc.
        """
        normalized_agent = self._normalize_agent_id(agent_id)
        now = utcnow()
        stamp = now.strftime("%Y%m%d%H%M%S")
        suffix = uuid.uuid4().hex[:6]
        session_id = f"session:web:{normalized_agent}:{stamp}:{suffix}"

        default_title = f"{self._get_agent_display_name(normalized_agent)}会话 {stamp}"
        title = name.strip() if name and name.strip() else default_title
        self._session_titles[session_id] = title

        # Create session in manager
        await self.session_manager.create_session(
            session_id=session_id,
            created_by="player:web",
            status="ACTIVE",
        )

        # Update agent binding
        self._current_session_by_agent[normalized_agent] = session_id

        # Register in manifest
        await self._ensure_session_registered(session_id, [normalized_agent])

        return {
            "session_id": session_id,
            "title": title,
            "created_at": now.isoformat(),
            "is_current": True,
            "event_count": 0,
            "agents": [normalized_agent],
            "agent_id": normalized_agent,
        }

    async def select_session(
        self,
        session_id: str,
        agent_id: str | None = None,
    ) -> dict:
        """Select an existing session for an agent.

        Args:
            session_id: Session to select
            agent_id: Optional agent to bind to session

        Returns:
            Session info dict
        """
        normalized_agent = self._normalize_agent_id(agent_id)

        # Find agent if not provided
        if not agent_id:
            detected_agent = await self._find_agent_for_session(session_id)
            if not detected_agent:
                # Check if session exists
                session = await self.session_manager.get_session(session_id)
                if not session:
                    raise ValueError(f"Session not found: {session_id}")
                # Use first available agent
                if self.agent_service:
                    available = await self.agent_service.get_available_agents()
                    if available:
                        detected_agent = available[0]
            if not detected_agent:
                raise ValueError(f"Cannot determine agent for session: {session_id}")
            normalized_agent = detected_agent

        # Verify session exists for this agent
        sessions = await self.list_agent_sessions()
        matched = False
        for group in sessions:
            if group["agent_id"] != normalized_agent:
                continue
            matched = any(s["session_id"] == session_id for s in group["sessions"])
            break

        if not matched:
            # Check if session exists at all
            session = await self.session_manager.get_session(session_id)
            if not session:
                raise ValueError(f"Session not found: {session_id}")

        # Update binding
        self._current_session_by_agent[normalized_agent] = session_id

        return {
            "session_id": session_id,
            "is_current": True,
            "agent_id": normalized_agent,
        }

    async def list_sessions(self) -> list[dict]:
        """List all sessions.

        Returns:
            List of session info dicts
        """
        all_sessions = []
        for group in await self.list_agent_sessions():
            all_sessions.extend(group["sessions"])
        return all_sessions

    async def list_agent_sessions(self) -> list[dict]:
        """List sessions grouped by agent.

        Returns:
            List of dicts with agent_id and sessions list
        """
        from simu_emperor.common.file_utils import FileOperationsHelper

        manifest = await FileOperationsHelper.read_json_file(self.memory_dir / "manifest.json") or {}
        sessions_data = manifest.get("sessions", {}) if isinstance(manifest, dict) else {}

        # Group sessions by agent
        agent_sessions: dict[str, list[dict]] = {}

        for session_id, session_data in sessions_data.items():
            # Skip task sessions (sub-sessions)
            if session_id.startswith("task:"):
                continue

            # Get agents in this session
            agents = session_data.get("agents", {})
            if not isinstance(agents, dict):
                continue

            for agent_id in agents.keys():
                if agent_id not in agent_sessions:
                    agent_sessions[agent_id] = []

                agent_sessions[agent_id].append({
                    "session_id": session_id,
                    "title": self._session_titles.get(session_id, self._extract_title_from_id(session_id)),
                    "created_at": session_data.get("created_at", ""),
                    "event_count": session_data.get("event_count", 0),
                    "is_current": self._current_session_by_agent.get(agent_id) == session_id,
                })

        # Convert to list format
        result = []
        for agent_id, sessions in sorted(agent_sessions.items()):
            result.append({
                "agent_id": agent_id,
                "sessions": sorted(sessions, key=lambda s: s["created_at"], reverse=True),
            })

        return result

    async def get_session_for_agent(self, agent_id: str) -> str:
        """Get the current session for an agent.

        Args:
            agent_id: Agent to query

        Returns:
            Current session ID for the agent
        """
        normalized = self._normalize_agent_id(agent_id)
        return self._current_session_by_agent.get(normalized, self._main_session_id)

    def _normalize_agent_id(self, agent_id: str | None) -> str:
        """Normalize agent ID."""
        if agent_id:
            return agent_id.replace("agent:", "")
        # Return default agent
        return "governor_zhili"

    def _get_agent_display_name(self, agent_id: str) -> str:
        """Get display name for agent."""
        mapping = {
            "governor_zhili": "直隶巡抚",
            "minister_of_revenue": "户部尚书",
        }
        return mapping.get(agent_id, agent_id)

    def _extract_title_from_id(self, session_id: str) -> str:
        """Extract title from session ID if no title stored."""
        if session_id == self._main_session_id:
            return "主会话"
        return session_id

    async def _find_agent_for_session(self, session_id: str) -> str | None:
        """Find which agent owns a session."""
        for group in await self.list_agent_sessions():
            for session in group["sessions"]:
                if session["session_id"] == session_id:
                    return group["agent_id"]
        return None

    async def _ensure_session_registered(
        self,
        session_id: str,
        agent_ids: list[str],
    ) -> None:
        """Register session in manifest if not already registered."""
        # This would update the manifest index
        # Full implementation would register the session with metadata
        pass

    def set_current_context(self, agent_id: str, session_id: str) -> None:
        """Set current session context for agent."""
        normalized_agent = self._normalize_agent_id(agent_id)
        self._current_session_by_agent[normalized_agent] = session_id

    @property
    def main_session_id(self) -> str:
        """Get the main session ID."""
        return self._main_session_id
