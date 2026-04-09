"""GroupStore — in-memory group chat management with JSON persistence.

Preserves V4 group functionality: create, list, add/remove agents, messaging.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GroupChat:
    """A named group of agents that can receive broadcast messages."""

    group_id: str
    name: str
    agent_ids: list[str] = field(default_factory=list)
    created_by: str = "player:web"
    created_at: str = ""
    session_id: str = ""
    message_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GroupStore:
    """In-memory group store with optional JSON file persistence."""

    def __init__(self, persist_path: Path | None = None) -> None:
        self._groups: dict[str, GroupChat] = {}
        self._persist_path = persist_path
        if persist_path and persist_path.exists():
            self._load()

    def list_all(self) -> list[dict[str, Any]]:
        return [g.to_dict() for g in self._groups.values()]

    def get(self, group_id: str) -> GroupChat | None:
        return self._groups.get(group_id)

    def create(self, name: str, agent_ids: list[str], session_id: str = "") -> GroupChat:
        group_id = f"group:web:{uuid.uuid4().hex[:8]}"
        group = GroupChat(
            group_id=group_id,
            name=name,
            agent_ids=[_normalize_agent_id(a) for a in agent_ids],
            created_at=datetime.now(timezone.utc).isoformat(),
            session_id=session_id,
        )
        self._groups[group_id] = group
        self._save()
        return group

    def add_agent(self, group_id: str, agent_id: str) -> GroupChat | None:
        group = self._groups.get(group_id)
        if group is None:
            return None
        normalized = _normalize_agent_id(agent_id)
        if normalized not in group.agent_ids:
            group.agent_ids.append(normalized)
            self._save()
        return group

    def remove_agent(self, group_id: str, agent_id: str) -> GroupChat | None:
        group = self._groups.get(group_id)
        if group is None:
            return None
        normalized = _normalize_agent_id(agent_id)
        if normalized in group.agent_ids:
            group.agent_ids.remove(normalized)
            self._save()
        return group

    def record_message(self, group_id: str) -> list[str]:
        """Increment message count and return the list of agent IDs to broadcast to."""
        group = self._groups.get(group_id)
        if group is None:
            return []
        group.message_count += 1
        self._save()
        return list(group.agent_ids)

    def _save(self) -> None:
        if self._persist_path is None:
            return
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "group_chats": [g.to_dict() for g in self._groups.values()],
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        self._persist_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def _load(self) -> None:
        assert self._persist_path is not None
        try:
            data = json.loads(self._persist_path.read_text())
            for entry in data.get("group_chats", []):
                group = GroupChat(**{k: v for k, v in entry.items() if k in GroupChat.__dataclass_fields__})
                self._groups[group.group_id] = group
        except Exception:
            logger.warning("Failed to load group store from %s", self._persist_path, exc_info=True)


def _normalize_agent_id(agent_id: str) -> str:
    """Strip 'agent:' prefix if present."""
    return agent_id.removeprefix("agent:")
