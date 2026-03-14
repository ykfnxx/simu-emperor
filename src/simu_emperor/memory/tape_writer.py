"""TapeWriter for writing events to tape.jsonl files（V4 更新）."""

import aiofiles
from pathlib import Path
from datetime import datetime, timezone
import uuid
from typing import TYPE_CHECKING, Callable, Awaitable

from simu_emperor.event_bus.event import Event

if TYPE_CHECKING:
    pass


class TapeWriter:
    """
    Writes events to tape.jsonl files with token counting.

    V4 变更：
    - 添加 on_event_written 回调支持
    - 写入完成后触发回调更新 event_count
    """

    def __init__(
        self,
        memory_dir: Path,
        on_event_written: Callable[[str, str], Awaitable[None]] | None = None,
    ):
        """
        Initialize TapeWriter.

        Args:
            memory_dir: Base memory directory path
            on_event_written: V4 新增：事件写入后的回调函数
                回调签名: async def callback(agent_id: str, session_id: str) -> None
        """
        self.memory_dir = memory_dir
        self._on_event_written = on_event_written

    async def write_event(
        self, event: Event, agent_id: str | None = None
    ) -> str:
        """
        Write an event to tape.jsonl（V4 更新：添加回调触发）。

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
            # Not an agent event, skip writing
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

        # Ensure directory exists
        tape_path.parent.mkdir(parents=True, exist_ok=True)

        # Append to JSONL file (use event's to_json but override type for tape)
        async with aiofiles.open(tape_path, mode="a", encoding="utf-8") as f:
            await f.write(event.to_json() + "\n")

        # V4: 触发回调更新 event_count
        if self._on_event_written and agent_id and session_id:
            try:
                await self._on_event_written(agent_id, session_id)
            except Exception as e:
                # 回调失败不应阻塞写入流程
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"on_event_written callback failed: {e}")

        return event.event_id

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
