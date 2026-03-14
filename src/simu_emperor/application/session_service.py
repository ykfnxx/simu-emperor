"""Session Service - Session management business logic."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
import uuid

from simu_emperor.common import DEFAULT_WEB_SESSION_ID, get_agent_display_name, strip_agent_prefix
from simu_emperor.common.utils import FileOperationsHelper

if TYPE_CHECKING:
    from simu_emperor.session.manager import SessionManager
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
        memory_dir: Path,
        agent_service: "AgentService | None" = None,
    ) -> None:
        """Initialize SessionService.

        Args:
            session_manager: Session lifecycle manager
            memory_dir: Memory storage directory
            agent_service: Agent service for availability checks
        """
        self.session_manager = session_manager
        self.memory_dir = memory_dir
        self.agent_service = agent_service

        # Track session metadata
        self._session_titles: dict[str, str] = {}
        self._current_session_by_agent: dict[str, str] = {}
        self._main_session_id = DEFAULT_WEB_SESSION_ID

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
        normalized_agent = strip_agent_prefix(agent_id or "governor_zhili")
        now = utcnow()
        stamp = now.strftime("%Y%m%d%H%M%S")
        suffix = uuid.uuid4().hex[:6]
        session_id = f"session:web:{normalized_agent}:{stamp}:{suffix}"

        default_title = f"{get_agent_display_name(normalized_agent)}会话 {stamp}"
        title = name.strip() if name and name.strip() else default_title
        self._session_titles[session_id] = title

        # Create session in manager
        await self.session_manager.create_session(
            session_id=session_id,
            created_by="player:web",
            status="ACTIVE",
        )

        # Register agent in session's agent_states
        await self.session_manager.set_agent_state(
            session_id=session_id,
            agent_id=normalized_agent,
            status="ACTIVE",
        )

        # Update agent binding
        self._current_session_by_agent[normalized_agent] = session_id

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
        normalized_agent = strip_agent_prefix(agent_id or "governor_zhili")

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

        # V4: Read from session_manifest.json instead of manifest.json
        manifest = await FileOperationsHelper.read_json_file(self.memory_dir / "session_manifest.json") or {}
        sessions_data = manifest.get("sessions", {}) if isinstance(manifest, dict) else {}

        # V4: Pre-load titles from tape_meta.jsonl for all agents
        await self._preload_titles_from_tape_meta()

        # Group sessions by agent
        agent_sessions: dict[str, list[dict]] = {}

        for session_id, session_data in sessions_data.items():
            # Skip task sessions (sub-sessions)
            if session_id.startswith("task:"):
                continue

            # Get agents in this session - support both old and new formats
            # New format (V2): agent_states is a dict of agent_id -> status
            # Old format (V1): agents is a dict of agent_id -> agent_data
            agent_states = session_data.get("agent_states", {})
            old_agents = session_data.get("agents", {})

            # Use new format if available, otherwise fall back to old format
            agents_to_process: list[str] = []
            if agent_states:
                # New V2 format: agent_states keys are agent IDs (with or without "agent:" prefix)
                for agent_id in agent_states.keys():
                    # Strip "agent:" prefix for consistency
                    normalized = agent_id.replace("agent:", "") if agent_id.startswith("agent:") else agent_id
                    agents_to_process.append(normalized)
            elif old_agents:
                # Old V1 format: agents dict keys are agent IDs
                if isinstance(old_agents, dict):
                    agents_to_process.extend(old_agents.keys())

            # If no agents found but session has created_by info with agent prefix, use that
            if not agents_to_process:
                created_by = session_data.get("created_by", "")
                if created_by.startswith("agent:"):
                    agent_id = created_by.replace("agent:", "")
                    agents_to_process.append(agent_id)

            for agent_id in agents_to_process:
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
                "agent_name": get_agent_display_name(agent_id),
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
        normalized = strip_agent_prefix(agent_id)
        return self._current_session_by_agent.get(normalized, self._main_session_id)

    async def _get_title_from_tape_meta(self, session_id: str, agent_id: str) -> str | None:
        """Get session title from tape_meta.jsonl (V4).

        Args:
            session_id: Session identifier
            agent_id: Agent identifier

        Returns:
            Title string if found, None otherwise
        """
        metadata_path = self.memory_dir / "agents" / agent_id / "tape_meta.jsonl"
        if not metadata_path.exists():
            return None

        try:
            entries = await FileOperationsHelper.read_jsonl_file(metadata_path)
            for entry in entries:
                if entry.get("session_id") == session_id:
                    title = entry.get("title")
                    if title:
                        # Cache the title
                        self._session_titles[session_id] = title
                        return title
        except Exception as e:
            logger.warning(f"Failed to read tape_meta.jsonl for {agent_id}: {e}")

        return None

    def _extract_title_from_id(self, session_id: str) -> str:
        """Extract title from session ID if no title stored."""
        if session_id == self._main_session_id:
            return "主会话"
        return session_id

    async def _preload_titles_from_tape_meta(self) -> None:
        """Pre-load all session titles from tape_meta.jsonl files.

        V4: Reads tape_meta.jsonl for each agent to populate _session_titles cache.
        This is more efficient than reading the file for each session individually.
        """
        agents_dir = self.memory_dir / "agents"
        if not agents_dir.exists():
            return

        # Iterate through each agent's directory
        for agent_dir in agents_dir.iterdir():
            if not agent_dir.is_dir():
                continue

            agent_id = agent_dir.name
            metadata_path = agent_dir / "tape_meta.jsonl"
            if not metadata_path.exists():
                continue

            try:
                entries = await FileOperationsHelper.read_jsonl_file(metadata_path)
                for entry in entries:
                    session_id = entry.get("session_id")
                    title = entry.get("title")
                    if session_id and title:
                        # Always use tape_meta title as source of truth (overwrites default titles)
                        self._session_titles[session_id] = title
            except Exception as e:
                logger.debug(f"Failed to preload titles for {agent_id}: {e}")

    async def _find_agent_for_session(self, session_id: str) -> str | None:
        """Find which agent owns a session."""
        for group in await self.list_agent_sessions():
            for session in group["sessions"]:
                if session["session_id"] == session_id:
                    return group["agent_id"]
        return None

    def set_current_context(self, agent_id: str, session_id: str) -> None:
        """Set current session context for agent."""
        normalized_agent = strip_agent_prefix(agent_id)
        self._current_session_by_agent[normalized_agent] = session_id

    @property
    def main_session_id(self) -> str:
        """Get the main session ID."""
        return self._main_session_id
