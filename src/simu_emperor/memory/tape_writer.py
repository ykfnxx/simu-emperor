"""TapeWriter for writing events to tape.jsonl files."""

import aiofiles
import json
from pathlib import Path
from datetime import datetime, timezone
import uuid


class TapeWriter:
    """Writes events to tape.jsonl files with token counting."""

    def __init__(self, memory_dir: Path):
        """
        Initialize TapeWriter.

        Args:
            memory_dir: Base memory directory path
        """
        self.memory_dir = memory_dir

    async def write_event(
        self,
        session_id: str,
        agent_id: str,
        event_type: str,
        content: dict,
        tokens: int
    ) -> str:
        """
        Write an event to tape.jsonl.

        Args:
            session_id: Session identifier
            agent_id: Agent identifier
            event_type: Event type (USER_QUERY, TOOL_CALL, etc.)
            content: Event content dictionary
            tokens: Token count for the event

        Returns:
            Event ID string
        """
        tape_path = self._get_tape_path(session_id, agent_id)
        event_id = self._generate_event_id()

        event = {
            "event_id": event_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "content": content,
            "tokens": tokens,
            "agent_id": agent_id
        }

        # Ensure directory exists
        tape_path.parent.mkdir(parents=True, exist_ok=True)

        # Append to JSONL file
        async with aiofiles.open(tape_path, mode="a", encoding="utf-8") as f:
            await f.write(json.dumps(event, ensure_ascii=False) + "\n")

        return event_id

    def _get_tape_path(self, session_id: str, agent_id: str) -> Path:
        """
        Get the tape.jsonl path for a session and agent.

        Args:
            session_id: Session identifier
            agent_id: Agent identifier

        Returns:
            Path to tape.jsonl file
        """
        return (
            self.memory_dir
            / "agents"
            / agent_id
            / "sessions"
            / session_id
            / "tape.jsonl"
        )

    def _generate_event_id(self) -> str:
        """
        Generate a unique event ID.

        Returns:
            Event ID string in V2 format: evt_{timestamp}_{random8}
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        random_part = uuid.uuid4().hex[:8]
        return f"evt_{timestamp}_{random_part}"
