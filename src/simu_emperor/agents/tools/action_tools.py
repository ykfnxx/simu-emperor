"""Action tool handlers for Agent

These handlers execute side effects (send events, write files, etc.).
"""

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
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
    - send_message: Unified message sending (to player or other agents)
    - finish_loop: End agent loop (when session has > 2 members)
    - write_memory: Write memory summaries to files
    - create_incident: Create time-limited game events
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

    async def send_message(self, args: dict, event: Event) -> str | tuple:
        """统一的消息发送函数

        所有 agent 发出的消息都是 AGENT_MESSAGE 事件类型。
        """
        recipients = args.get("recipients", [])
        content = args.get("content", "")
        await_reply = args.get("await_reply", False)

        if not recipients:
            return "❌ 接收者列表不能为空"
        if not content:
            return "❌ 消息内容不能为空"
        if await_reply and "player" in recipients:
            return "❌ await_reply=true 只能用于 agent 间消息"

        # 标准化 recipients
        normalized_recipients = []
        for r in recipients:
            if r == "player":
                normalized_recipients.append("player")
            elif not r.startswith("agent:"):
                normalized_recipients.append(f"agent:{r}")
            else:
                normalized_recipients.append(r)

        # 防止向自己发送消息
        self_agent = f"agent:{self.agent_id}"
        if self_agent in normalized_recipients:
            return "❌ 不能向自己发送消息"

        # 处理 await_reply
        if await_reply and self.session_manager:
            session = await self.session_manager.get_session(event.session_id)
            if not session or not session.is_task:
                return "❌ await_reply=true 只能在任务会话中使用"
            await self.session_manager.increment_async_replies(
                event.session_id, self.agent_id, count=1
            )

        # 创建 AGENT_MESSAGE 事件
        message_event = Event(
            src=f"agent:{self.agent_id}",
            dst=normalized_recipients,
            type=EventType.AGENT_MESSAGE,
            payload={"content": content, "await_reply": await_reply},
            session_id=event.session_id,
            parent_event_id=event.event_id,
            root_event_id=event.root_event_id,
        )
        await self.event_bus.send_event(message_event)

        status_msg = "等待回复..." if await_reply else "✅ 消息已发送"
        return (status_msg, message_event)

    async def finish_loop(self, args: dict, event: Event) -> str:
        """结束 agent loop（仅在成员 > 2 时生效）"""
        if not self.session_manager:
            return "⚠️ SessionManager 未初始化，finish_loop 不可用"

        session = await self.session_manager.get_session(event.session_id)
        if not session:
            return "❌ Session not found"

        member_count = len(session.agent_states)

        if member_count <= 2:
            return (
                f"⚠️ Session 成员数为 {member_count}，finish_loop 不生效。\n"
                f"原因：防止只有一方在等待。\n"
                f"请使用其他方式继续对话或使用 respond_to_player 结束。"
            )

        reason = args.get("reason", "")
        logger.info(
            f"🔄 [Agent:{self.agent_id}] finish_loop called in session with {member_count} members. Reason: {reason}"
        )
        return f"✅ finish_loop 已执行，agent loop 将退出。原因：{reason}"

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

    async def create_incident(self, args: dict, event: Event) -> str:
        incident_id = (
            f"inc_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
        )

        effects = self._validate_and_build_effects(args["effects"])

        await self.event_bus.send_event(
            Event(
                src=f"agent:{self.agent_id}",
                dst=["system:engine"],
                type=EventType.INCIDENT_CREATED,
                payload={
                    "incident_id": incident_id,
                    "title": args["title"],
                    "description": args["description"],
                    "effects": effects,
                    "source": self.agent_id,
                    "remaining_ticks": args["duration_ticks"],
                },
                session_id=event.session_id,
                parent_event_id=event.event_id,
                root_event_id=event.root_event_id,
            )
        )

        return f"✅ 事件已创建: {args['title']} (ID: {incident_id}, 持续 {args['duration_ticks']} ticks)"

    def _validate_and_build_effects(self, effects_data: list) -> list:
        ALLOWED_ADD_PATHS = [
            r"^provinces\.[a-z_]+\.stockpile$",
            r"^nation\.imperial_treasury$",
        ]
        ALLOWED_FACTOR_PATHS = [
            r"^provinces\.[a-z_]+\.production_value$",
            r"^provinces\.[a-z_]+\.population$",
        ]

        effects = []
        for eff in effects_data:
            target_path = eff["target_path"]

            if "add" in eff and eff["add"] is not None:
                if not any(re.match(pattern, target_path) for pattern in ALLOWED_ADD_PATHS):
                    raise ValueError(
                        f"add 类型效果只能作用于 stockpile 或 imperial_treasury，无效路径: {target_path}"
                    )
                effects.append(
                    {
                        "target_path": target_path,
                        "add": str(Decimal(str(eff["add"]))),
                        "factor": None,
                    }
                )
            elif "factor" in eff and eff["factor"] is not None:
                if not any(re.match(pattern, target_path) for pattern in ALLOWED_FACTOR_PATHS):
                    raise ValueError(
                        f"factor 类型效果只能作用于 production_value 或 population，无效路径: {target_path}"
                    )
                effects.append(
                    {
                        "target_path": target_path,
                        "add": None,
                        "factor": str(Decimal(str(eff["factor"]))),
                    }
                )
            else:
                raise ValueError(f"Effect 必须指定 add 或 factor 其中之一: {target_path}")

        return effects
