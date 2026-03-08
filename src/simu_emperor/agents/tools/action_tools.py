"""Action tool handlers for Agent

These handlers execute side effects (send events, write files, etc.).
"""

import logging
import os
from pathlib import Path

from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.session.manager import SessionManager


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
        session_manager=None,
    ):
        self.agent_id = agent_id
        self.event_bus = event_bus
        self.data_dir = data_dir
        self.session_manager = session_manager

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

    async def send_message_to_agent(self, args: dict, event: Event) -> str:
        target_agent = args.get("target_agent", "")
        message = args.get("message", "")
        await_reply = args.get("await_reply", False)  # New parameter: default False

        if not target_agent:
            return "❌ 目标官员不能为空"

        if not message:
            return "❌ 消息内容不能为空"

        # Validate session type (only for task sessions)
        if self.session_manager:
            session = await self.session_manager.get_session(event.session_id)
            if not session:
                return "❌ 会话不存在"

            # If await_reply=true, only allow in task sessions
            if await_reply and not session.is_task:
                return ("❌ await_reply=true 只能在任务会话中使用。\n"
                        "在主会话中发送消息不会等待回复。\n"
                        "如果需要等待其他官员的回复，请先使用 create_task_session 创建任务会话。")

        if not target_agent.startswith("agent:"):
            target_agent = f"agent:{target_agent}"

        logger.info(
            f"📨 [Agent:{self.agent_id}] Sending message to {target_agent}: {message[:50]}..."
            f" (await_reply={await_reply})"
        )

        # Design principle: AGENT_MESSAGE means "send to which agent in which session"
        # Both agents share the same task session - no session switching needed
        new_event = Event(
            src=f"agent:{self.agent_id}",
            dst=[target_agent],
            type=EventType.AGENT_MESSAGE,
            payload={
                "message": message,
                "original_caller": f"agent:{self.agent_id}",
                "await_reply": await_reply,
            },
            session_id=event.session_id,  # Share the same session
            parent_event_id=event.event_id,
            root_event_id=event.root_event_id,
        )
        await self.event_bus.send_event(new_event)
        logger.info(f"✅ Agent {self.agent_id} sent AGENT_MESSAGE to {target_agent}")

        # If await_reply=true, increment pending_async_replies counter
        if await_reply and self.session_manager:
            await self.session_manager.increment_async_replies(
                event.session_id,
                self.agent_id,
                count=1,
            )
            # Also track the message ID for correlation
            session = await self.session_manager.get_session(event.session_id)
            if session:
                session.pending_message_ids.append(new_event.event_id)
                await self.session_manager.save_manifest()
            return "消息已发送，等待回复..."
        else:
            return "✅ 消息已发送"

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
