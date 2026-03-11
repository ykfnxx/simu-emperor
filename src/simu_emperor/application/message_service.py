"""Message Service - Message processing and routing."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simu_emperor.event_bus.core import EventBus
    from simu_emperor.session.manager import SessionManager


logger = logging.getLogger(__name__)


class MessageService:
    """Message processing service.

    Responsibilities:
    - Message parsing
    - Event creation and routing
    - Message delivery to agents
    """

    def __init__(
        self,
        event_bus: "EventBus",
        session_manager: "SessionManager",
    ) -> None:
        """Initialize MessageService.

        Args:
            event_bus: Event bus for publishing events
            session_manager: Session lifecycle manager
        """
        self.event_bus = event_bus
        self.session_manager = session_manager

    async def send_command(
        self,
        agent_id: str,
        command: str,
        session_id: str,
        source: str = "player:web",
    ) -> None:
        """Send a command to an agent.

        Note: Uses EventType.CHAT for both commands and chat messages.

        Args:
            agent_id: Target agent ID
            command: Command text
            session_id: Current session ID
            source: Message source identifier
        """
        from simu_emperor.event_bus.event import Event
        from simu_emperor.event_bus.event_types import EventType

        normalized_agent = self._normalize_agent_id(agent_id)

        event = Event(
            src=source,
            dst=[f"agent:{normalized_agent}"],
            type=EventType.CHAT,
            payload={"query": command},
            session_id=session_id,
        )

        await self.event_bus.publish(event)
        logger.info(f"Sent command to agent:{normalized_agent} in session {session_id}")

    async def send_chat(
        self,
        agent_id: str,
        message: str,
        session_id: str,
        source: str = "player:web",
    ) -> None:
        """Send a chat message to an agent.

        Args:
            agent_id: Target agent ID
            message: Chat message text
            session_id: Current session ID
            source: Message source identifier
        """
        from simu_emperor.event_bus.event import Event
        from simu_emperor.event_bus.event_types import EventType

        normalized_agent = self._normalize_agent_id(agent_id)

        event = Event(
            src=source,
            dst=[f"agent:{normalized_agent}"],
            type=EventType.CHAT,
            payload={"message": message},
            session_id=session_id,
        )

        await self.event_bus.publish(event)
        logger.info(f"Sent chat to agent:{normalized_agent} in session {session_id}")

    async def broadcast(
        self,
        message: str,
        session_id: str,
        agent_ids: list[str] | None = None,
        source: str = "player:web",
    ) -> None:
        """Broadcast a message to multiple agents.

        Args:
            message: Message text
            session_id: Current session ID
            agent_ids: List of target agent IDs (None = broadcast to all)
            source: Message source identifier
        """
        from simu_emperor.event_bus.event import Event
        from simu_emperor.event_bus.event_types import EventType

        if agent_ids:
            dst = [self._normalize_agent_id(a) for a in agent_ids]
            dst = [f"agent:{a}" for a in dst]
        else:
            dst = ["*"]

        event = Event(
            src=source,
            dst=dst,
            type=EventType.CHAT,
            payload={"message": message},
            session_id=session_id,
        )

        await self.event_bus.publish(event)
        logger.info(f"Broadcast message to {dst}")

    async def send_to_group(
        self,
        group_id: str,
        message: str,
        session_id: str,
        source: str = "player:web",
    ) -> list[str]:
        """Send message to all agents in a group chat.

        Args:
            group_id: Group chat ID
            message: Message text
            session_id: Current session ID
            source: Message source identifier

        Returns:
            List of agent IDs that received the message
        """

        # This method would need access to GroupChatService
        # For now, return empty list - will be connected via ApplicationServices
        return []

    def _normalize_agent_id(self, agent_id: str) -> str:
        """Normalize agent ID (remove agent: prefix)."""
        if agent_id.startswith("agent:"):
            return agent_id.replace("agent:", "", 1)
        return agent_id

    async def parse_message(self, text: str) -> dict:
        """Parse a message to extract intent and entities.

        Args:
            text: Message text

        Returns:
            Dict with intent, entities, etc.
        """
        # Simple parsing - full implementation would use LLM
        text = text.strip()

        # Detect command patterns
        if text.startswith("/"):
            command = text[1:].split()[0] if text.split() else ""
            return {
                "type": "command",
                "command": command,
                "args": text[len(command) + 1:].strip(),
                "raw": text,
            }

        return {
            "type": "chat",
            "text": text,
            "raw": text,
        }
