"""Group Chat Service - Multi-agent chat management."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
import uuid

from simu_emperor.common import DEFAULT_WEB_SESSION_ID, strip_agent_prefix

if TYPE_CHECKING:
    from simu_emperor.session.manager import SessionManager
    from simu_emperor.session.group_chat import GroupChat


logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GroupChatService:
    """Group chat business service.

    Responsibilities:
    - Group chat creation/management
    - Agent addition/removal from groups
    - Group chat message handling
    """

    def __init__(
        self,
        session_manager: "SessionManager",
        memory_dir: Path,
    ) -> None:
        """Initialize GroupChatService.

        Args:
            session_manager: Session lifecycle manager
            memory_dir: Memory storage directory
        """
        self.session_manager = session_manager
        self.memory_dir = memory_dir
        self._group_chats: dict[str, "GroupChat"] = {}

    async def create_group_chat(
        self,
        name: str,
        agent_ids: list[str],
        session_id: str = DEFAULT_WEB_SESSION_ID,
    ) -> "GroupChat":
        """Create a new group chat.

        Args:
            name: Group chat name
            agent_ids: List of agents to include
            session_id: Associated session ID

        Returns:
            Created GroupChat instance
        """
        from simu_emperor.session.group_chat import GroupChat

        now = utcnow()
        stamp = now.strftime("%Y%m%d%H%M%S")
        suffix = uuid.uuid4().hex[:8]
        group_id = f"group:web:{stamp}:{suffix}"

        group_chat = GroupChat(
            group_id=group_id,
            name=name,
            agent_ids=agent_ids,
            created_by="player:web",
            created_at=now,
            session_id=session_id,
            message_count=0,
        )

        self._group_chats[group_id] = group_chat
        await self._save_group_chats()

        logger.info(f"Created group chat: {group_id} with agents: {agent_ids}")
        return group_chat

    async def list_group_chats(self) -> list["GroupChat"]:
        """List all group chats.

        Returns:
            List of GroupChat instances
        """
        return list(self._group_chats.values())

    async def get_group_chat(self, group_id: str) -> "GroupChat | None":
        """Get a group chat by ID.

        Args:
            group_id: Group chat ID

        Returns:
            GroupChat instance or None
        """
        return self._group_chats.get(group_id)

    async def send_to_group_chat(
        self,
        group_id: str,
        message: str,
    ) -> list[str]:
        """Send message to all agents in a group chat.

        Args:
            group_id: Group chat ID
            message: Message to send

        Returns:
            List of agent IDs that received the message

        Raises:
            ValueError: If group chat not found
        """
        group = self._group_chats.get(group_id)
        if not group:
            raise ValueError(f"Group chat not found: {group_id}")

        # Increment message count
        group.message_count += 1
        await self._save_group_chats()

        # Return list of agent IDs
        # The actual message sending is handled by MessageService
        return group.agent_ids

    async def add_agent_to_group(
        self,
        group_id: str,
        agent_id: str,
    ) -> bool:
        """Add an agent to a group chat.

        Args:
            group_id: Group chat ID
            agent_id: Agent to add

        Returns:
            True if agent was added, False if already present

        Raises:
            ValueError: If group chat not found
        """
        group = self._group_chats.get(group_id)
        if not group:
            raise ValueError(f"Group chat not found: {group_id}")

        normalized = strip_agent_prefix(agent_id)
        if normalized not in group.agent_ids:
            group.agent_ids.append(normalized)
            await self._save_group_chats()
            logger.info(f"Added agent {normalized} to group {group_id}")
            return True

        return False

    async def remove_agent_from_group(
        self,
        group_id: str,
        agent_id: str,
    ) -> bool:
        """Remove an agent from a group chat.

        Args:
            group_id: Group chat ID
            agent_id: Agent to remove

        Returns:
            True if agent was removed, False if not present

        Raises:
            ValueError: If group chat not found
        """
        group = self._group_chats.get(group_id)
        if not group:
            raise ValueError(f"Group chat not found: {group_id}")

        normalized = strip_agent_prefix(agent_id)
        if normalized in group.agent_ids:
            group.agent_ids.remove(normalized)
            await self._save_group_chats()
            logger.info(f"Removed agent {normalized} from group {group_id}")
            return True

        return False

    async def _load_group_chats(self) -> None:
        """Load group chats from storage."""
        group_chats_path = self.memory_dir / "group_chats.json"
        if not group_chats_path.exists():
            return

        try:
            data = json.loads(group_chats_path.read_text())
            from simu_emperor.session.group_chat import GroupChat

            for group_data in data.get("group_chats", []):
                group = GroupChat.from_dict(group_data)
                self._group_chats[group.group_id] = group

            logger.info(f"Loaded {len(self._group_chats)} group chats")
        except Exception as e:
            logger.error(f"Failed to load group chats: {e}")

    async def _save_group_chats(self) -> None:
        """Save group chats to storage."""
        group_chats_path = self.memory_dir / "group_chats.json"
        group_chats_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "group_chats": [group.to_dict() for group in self._group_chats.values()],
            "last_updated": utcnow().isoformat(),
        }

        try:
            group_chats_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Failed to save group chats: {e}")

    async def load_from_storage(self) -> None:
        """Load group chats from storage (public method)."""
        await self._load_group_chats()

    async def save_to_storage(self) -> None:
        """Save group chats to storage (public method)."""
        await self._save_group_chats()
