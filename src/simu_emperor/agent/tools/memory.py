"""
Memory tool handlers for V5 Agent

Memory tools retrieve and store memories using SeekDB.
"""

import json
import logging
from pathlib import Path
from typing import Any

from simu_emperor.mq.event import Event
from simu_emperor.persistence.repositories.tape import TapeRepository
from simu_emperor.persistence.repositories.segment import SegmentRepository
from simu_emperor.persistence.embedding import EmbeddingService


logger = logging.getLogger(__name__)


class MemoryTools:
    """Memory tool handlers - retrieve and store memories"""

    def __init__(
        self,
        agent_id: str,
        tape_repo: TapeRepository,
        segment_repo: SegmentRepository,
        embedding_service: EmbeddingService,
    ):
        self.agent_id = agent_id
        self.tape_repo = tape_repo
        self.segment_repo = segment_repo
        self.embedding_service = embedding_service

    async def retrieve_memory(self, args: dict, event: Event) -> str:
        query = args.get("query", "")
        max_results = args.get("max_results", 5)

        if not query:
            return "❌ 查询不能为空"

        try:
            session = await self.tape_repo.get_session(event.session_id)
            if not session:
                return f"❌ 未找到会话 {event.session_id}"

            events = await self.tape_repo.load_events(
                session_id=event.session_id,
                agent_id=self.agent_id,
                limit=max_results * 3,
            )

            if not events:
                return "## 检索结果\n\n未找到相关记忆。"

            lines = [
                "## 检索结果",
                "",
                f"找到 {len(events)} 条相关记录：",
                "",
            ]

            for evt in events[-max_results:]:
                event_type = evt.get("event_type", "UNKNOWN")
                payload = evt.get("payload", {})
                timestamp = evt.get("created_at", "")

                lines.append(f"**{event_type}** ({timestamp})")
                if isinstance(payload, dict):
                    content = payload.get("content") or payload.get("message") or str(payload)
                    lines.append(f"{content[:200]}...")
                else:
                    lines.append(str(payload)[:200])
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error retrieving memory: {e}")
            return f"❌ 记忆检索失败：{str(e)}"

    async def write_memory(self, args: dict, event: Event) -> str:
        content = args.get("content", "")
        tags = args.get("tags", [])

        if not content:
            return "❌ 记忆内容不能为空"

        try:
            tick = event.payload.get("tick", 0)

            segment = await self.segment_repo.create_segment(
                session_id=event.session_id,
                agent_id=self.agent_id,
                summary=content,
                tick=tick,
            )

            if segment:
                logger.info(f"Agent {self.agent_id} wrote memory segment {segment.get('id')}")
                return f"✅ 记忆已保存 (ID: {segment.get('id')})"
            else:
                return "❌ 记忆保存失败"

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error writing memory: {e}")
            return f"❌ 记忆写入失败：{str(e)}"
