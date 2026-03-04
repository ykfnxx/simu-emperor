"""Action tool handlers for Agent

These handlers execute side effects (send events, write files, etc.).
"""

import logging
import os
from pathlib import Path

from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType


logger = logging.getLogger(__name__)


class ActionTools:
    """Action tool handlers - execute side effects

    This class contains all action-type tool handlers that perform
    side effects like sending events or writing files.

    Action functions:
    - send_game_event: Send game events to Calculator
    - send_message_to_agent: Send messages to other agents
    - respond_to_player: Send responses to player
    - send_ready: Send ready signal to Calculator
    - write_memory: Write memory summaries to files
    """

    def __init__(
        self,
        agent_id: str,
        event_bus: EventBus,
        data_dir: Path,
    ):
        """
        Initialize ActionTools

        Args:
            agent_id: Agent unique identifier
            event_bus: EventBus for sending events
            data_dir: Data directory path
        """
        self.agent_id = agent_id
        self.event_bus = event_bus
        self.data_dir = data_dir

    async def send_game_event(self, args: dict, event: Event) -> None:
        """Send game events to Calculator"""
        event_type_str = args.get("event_type")
        payload = args.get("payload", {})

        logger.info(
            f"🎮 [Agent:{self.agent_id}] Sending game event: {event_type_str} with payload: {payload}"
        )

        # 映射到 EventType
        event_type = self._str_to_event_type(event_type_str)
        if not event_type:
            logger.warning(f"⚠️  [Agent:{self.agent_id}] Unknown event type: {event_type_str}")
            return

        new_event = Event(
            src=f"agent:{self.agent_id}",
            dst=["system:calculator"],
            type=event_type,
            payload=payload,
            session_id=event.session_id,
            parent_event_id=event.event_id,
            root_event_id=event.root_event_id,
        )
        await self.event_bus.send_event(new_event)
        logger.info(f"✅ [Agent:{self.agent_id}] Sent {event_type_str} event to system:calculator")

    async def send_message_to_agent(self, args: dict, event: Event) -> None:
        """Send messages to other agents"""
        target_agent = args.get("target_agent")
        message = args.get("message")

        logger.info(
            f"📨 [Agent:{self.agent_id}] Sending message to {target_agent}: {message[:50]}..."
        )

        if not target_agent.startswith("agent:"):
            target_agent = f"agent:{target_agent}"

        new_event = Event(
            src=f"agent:{self.agent_id}",
            dst=[target_agent],
            type=EventType.AGENT_MESSAGE,
            payload={"message": message},
            session_id=event.session_id,
            parent_event_id=event.event_id,
            root_event_id=event.root_event_id,
        )
        await self.event_bus.send_event(new_event)
        logger.info(f"✅ Agent {self.agent_id} sent AGENT_MESSAGE to {target_agent}")

    async def respond_to_player(self, args: dict, event: Event) -> None:
        """Send responses to player"""
        content = args.get("content", "")

        logger.info(f"💬 [Agent:{self.agent_id}] Responding to {event.src}: {content[:50]}...")

        new_event = Event(
            src=f"agent:{self.agent_id}",
            dst=[event.src],
            type=EventType.RESPONSE,
            payload={"narrative": content},
            session_id=event.session_id,
            parent_event_id=event.event_id,
            root_event_id=event.root_event_id,
        )
        await self.event_bus.send_event(new_event)
        logger.info(f"✅ [Agent:{self.agent_id}] Sent RESPONSE event to {event.src}")

    async def send_ready(self, args: dict, event: Event) -> None:
        """Send ready signal to Calculator"""
        new_event = Event(
            src=f"agent:{self.agent_id}",
            dst=["system:calculator"],
            type=EventType.READY,
            payload={},
            session_id=event.session_id,
            parent_event_id=event.event_id,
            root_event_id=event.root_event_id,
        )
        await self.event_bus.send_event(new_event)
        logger.info(f"✅ Agent {self.agent_id} sent READY to system:calculator")

    async def write_memory(self, args: dict, event: Event) -> None:
        """Write memory summaries to files"""
        content = args.get("content", "")
        turn = event.payload.get("turn", 0)

        # 创建 memory 目录
        memory_dir = self.data_dir / "memory"
        recent_dir = memory_dir / "recent"
        recent_dir.mkdir(parents=True, exist_ok=True)

        # 写入文件
        turn_file = recent_dir / f"turn_{turn:03d}.md"
        with open(turn_file, "w", encoding="utf-8") as f:
            f.write(f"# Turn {turn} Summary\n\n")
            f.write(f"Agent: {self.agent_id}\n")
            f.write(f"Date: {event.timestamp}\n\n")
            f.write(f"## Summary\n\n{content}\n")

        # 清理旧记忆
        self._cleanup_old_memories(recent_dir, turn)

        logger.info(f"✅ Agent {self.agent_id} wrote memory for turn {turn}")

    @staticmethod
    def _str_to_event_type(event_type_str: str) -> str | None:
        """将字符串映射到 EventType"""
        event_map = {
            "allocate_funds": EventType.ALLOCATE_FUNDS,
            "adjust_tax": EventType.ADJUST_TAX,
            "build_irrigation": EventType.BUILD_IRRIGATION,
            "recruit_troops": EventType.RECRUIT_TROOPS,
        }
        return event_map.get(event_type_str)

    @staticmethod
    def _cleanup_old_memories(recent_dir: Path, current_turn: int) -> None:
        """清理旧记忆（只保留最近3回合）"""
        if not recent_dir.exists():
            return

        for filename in os.listdir(recent_dir):
            if filename.startswith("turn_") and filename.endswith(".md"):
                try:
                    turn_str = filename[5:8]
                    file_turn = int(turn_str)

                    if file_turn <= current_turn - 3:
                        file_path = recent_dir / filename
                        file_path.unlink()
                        logger.debug(f"Cleaned up old memory: {filename}")
                except (ValueError, IndexError):
                    continue
