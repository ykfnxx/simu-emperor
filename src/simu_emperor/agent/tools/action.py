"""
Action tool handlers for V5 Agent

Action tools execute side effects (send events, create incidents, etc.)
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from simu_emperor.mq.event import Event
from simu_emperor.mq.dealer import MQDealer
from simu_emperor.persistence.repositories.tape import TapeRepository


logger = logging.getLogger(__name__)


class ActionTools:
    """Action tool handlers - execute side effects"""

    def __init__(
        self,
        agent_id: str,
        dealer: MQDealer,
        tape_repo: TapeRepository,
        data_dir=None,
    ):
        self.agent_id = agent_id
        self.dealer = dealer
        self.tape_repo = tape_repo
        self.data_dir = data_dir

    async def send_message(self, args: dict, event: Event) -> str | tuple:
        recipients = args.get("recipients", [])
        content = args.get("content", "")
        await_reply = args.get("await_reply", False)

        if not recipients:
            return "❌ 接收者列表不能为空"
        if not content:
            return "❌ 消息内容不能为空"

        normalized_recipients = []
        for r in recipients:
            if r == "player":
                normalized_recipients.append("player")
            elif not r.startswith("agent:"):
                normalized_recipients.append(f"agent:{r}")
            else:
                normalized_recipients.append(r)

        self_agent = f"agent:{self.agent_id}"
        if self_agent in normalized_recipients:
            return "❌ 不能向自己发送消息"

        message_event = Event(
            event_id="",
            event_type="AGENT_MESSAGE",
            src=f"agent:{self.agent_id}",
            dst=normalized_recipients,
            session_id=event.session_id,
            payload={"content": content, "await_reply": await_reply},
            timestamp="",
        )
        await self.dealer.send_event(message_event)

        status_msg = "等待回复..." if await_reply else "✅ 消息已发送"
        return (status_msg, message_event)

    async def finish_loop(self, args: dict, event: Event) -> str:
        reason = args.get("reason", "Task completed")
        return f"✅ finish_loop 已执行。原因：{reason}"

    async def create_incident(
        self,
        args: dict,
        event: Event,
    ) -> str:
        incident_type = args.get("incident_type", "general")
        title = args.get("title", "")
        description = args.get("description", "")
        severity = args.get("severity", "medium")
        duration = args.get("duration", 1)

        if not title:
            return "❌ 事件标题不能为空"

        incident_id = f"incident_{uuid.uuid4().hex[:8]}"
        tick = event.payload.get("tick", 0)

        incident_event = Event(
            event_id="",
            event_type="INCIDENT_CREATED",
            src=f"agent:{self.agent_id}",
            dst=["engine:*"],
            session_id=event.session_id,
            payload={
                "incident_id": incident_id,
                "incident_type": incident_type,
                "title": title,
                "description": description,
                "severity": severity,
                "duration": duration,
                "tick_created": tick,
            },
            timestamp="",
        )
        await self.dealer.send_event(incident_event)

        logger.info(f"Agent {self.agent_id} created incident: {title}")
        return f"✅ 事件已创建: {title} (ID: {incident_id})"

    async def write_memory(self, args: dict, event: Event) -> str:
        content = args.get("content", "")
        if not content.strip():
            return "❌ 记忆内容不能为空"

        tick = event.payload.get("tick", 0)

        await self.tape_repo.append_event(
            event=Event(
                event_id="",
                event_type="MEMORY_WRITE",
                src=f"agent:{self.agent_id}",
                dst=[f"agent:{self.agent_id}"],
                session_id=event.session_id,
                payload={"content": content, "tick": tick},
                timestamp="",
            ),
            tick=tick,
        )

        logger.info(f"Agent {self.agent_id} wrote memory at tick {tick}")
        return f"✅ 记忆已写入 (Tick {tick})"
