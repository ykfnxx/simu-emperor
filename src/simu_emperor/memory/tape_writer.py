"""TapeWriter for writing events to tape.jsonl files（V4 更新）。"""

import asyncio
import aiofiles
from pathlib import Path
from datetime import datetime, timezone
import uuid
from typing import TYPE_CHECKING
import logging

from simu_emperor.event_bus.event import Event

if TYPE_CHECKING:
    from simu_emperor.memory.tape_metadata import TapeMetadataManager
    from simu_emperor.llm.base import LLMProvider


logger = logging.getLogger(__name__)


class TapeWriter:
    """
    Writes events to tape.jsonl files with token counting.

    V4 变更：
    - 直接调用 tape_metadata_mgr.increment_event_count()
    - 添加首事件检测和标题生成支持
    """

    def __init__(
        self,
        memory_dir: Path,
        tape_metadata_mgr: "TapeMetadataManager | None" = None,
        llm_provider: "LLMProvider | None" = None,
    ):
        """
        Initialize TapeWriter.

        Args:
            memory_dir: Base memory directory path
            tape_metadata_mgr: TapeMetadataManager 用于标题生成和事件计数
            llm_provider: LLM provider 用于标题生成
        """
        self.memory_dir = memory_dir
        self._tape_metadata_mgr = tape_metadata_mgr
        self._llm_provider = llm_provider

    async def write_event(
        self, event: Event, agent_id: str | None = None
    ) -> str:
        """
        Write an event to tape.jsonl（V4 更新：首事件检测 + 标题生成）。

        Args:
            event: Event object to write
            agent_id: Optional agent ID to specify which agent's tape to write to.
                     If not provided, extracts from event.src (must start with "agent:")

        Returns:
            Event ID string
        """
        # Determine which agent's tape to write to
        if agent_id:
            # Use provided agent_id
            pass
        elif event.src.startswith("agent:"):
            # Extract from event.src
            agent_id = event.src.replace("agent:", "")
        else:
            # No agent_id available, cannot determine tape path
            return event.event_id

        # Extract metadata from event
        session_id = event.session_id
        content = event.payload

        # Count tokens if not provided
        tokens = event.payload.get("tokens")
        if tokens is None:
            # Count tokens based on content
            text = str(content)
            tokens = len(text) // 2  # Simple fallback: 2 chars ≈ 1 token

        tape_path = self._get_tape_path(session_id, agent_id)

        # V4: 检测是否是首事件（用于标题生成）
        is_first_event = not tape_path.exists() or tape_path.stat().st_size == 0

        # Ensure directory exists
        tape_path.parent.mkdir(parents=True, exist_ok=True)

        # Append to JSONL file (use event's to_json but override type for tape)
        async with aiofiles.open(tape_path, mode="a", encoding="utf-8") as f:
            await f.write(event.to_json() + "\n")

        # V4: 异步生成标题（首事件，且不是 TICK_COMPLETED）
        if is_first_event and self._tape_metadata_mgr and self._llm_provider:
            # 排除 TICK_COMPLETED 事件，因为它不适合作为标题依据
            if event.type != "tick_completed":
                logger.info(f"[TapeWriter] First event for {agent_id}/{session_id}, generating title...")
                asyncio.create_task(
                    self._generate_title_async(agent_id, session_id, event)
                )
        else:
            # Debug: log why title wasn't generated
            if is_first_event and event.type != "tick_completed":
                logger.warning(
                    f"[TapeWriter] Skipping title generation for {agent_id}/{session_id}: "
                    f"is_first={is_first_event}, "
                    f"metadata_mgr={self._tape_metadata_mgr is not None}, "
                    f"llm={self._llm_provider is not None}, "
                    f"event_type={event.type}"
                )

        # V4: 触发回调更新 event_count（已废弃：直接调用 increment_event_count）
        if self._tape_metadata_mgr and agent_id and session_id:
            try:
                await self._tape_metadata_mgr.increment_event_count(agent_id, session_id)
            except Exception as e:
                # 更新失败不应阻塞写入流程
                logger.debug(f"Failed to increment event count: {e}")

        return event.event_id

    async def _generate_title_async(
        self, agent_id: str, session_id: str, first_event: Event
    ) -> None:
        """
        异步生成 session 标题（V4 新增）。

        Args:
            agent_id: Agent 标识符
            session_id: Session 标识符
            first_event: 首事件
        """
        try:
            await self._tape_metadata_mgr.append_or_update_entry(
                agent_id=agent_id,
                session_id=session_id,
                first_event=first_event,
                llm=self._llm_provider,
                current_tick=None,  # 首事件时可能没有 tick
            )
            logger.debug(f"Generated title for {agent_id}/{session_id}")
        except Exception as e:
            logger.warning(f"Failed to generate title for {session_id}: {e}")

    def _get_tape_path(self, session_id: str, agent_id: str) -> Path:
        """
        Get the tape.jsonl path for a session and agent.

        Args:
            session_id: Session identifier
            agent_id: Agent identifier

        Returns:
            Path to tape.jsonl file
        """
        return self.memory_dir / "agents" / agent_id / "sessions" / session_id / "tape.jsonl"

    def _generate_event_id(self) -> str:
        """
        Generate a unique event ID.

        Returns:
            Event ID string in V2 format: evt_{timestamp}_{random8}
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        random_part = uuid.uuid4().hex[:8]
        return f"evt_{timestamp}_{random_part}"
