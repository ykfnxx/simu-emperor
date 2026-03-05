"""TapeWriter for writing events to tape.jsonl files."""

import aiofiles
from pathlib import Path
from datetime import datetime, timezone
import uuid

from simu_emperor.event_bus.event import Event


class TapeWriter:
    """Writes events to tape.jsonl files with token counting."""

    def __init__(self, memory_dir: Path):
        """
        Initialize TapeWriter.

        Args:
            memory_dir: Base memory directory path
        """
        self.memory_dir = memory_dir

    async def write_event(self, event: Event) -> str:
        """
        Write an event to tape.jsonl.

        Args:
            event: Event object to write

        Returns:
            Event ID string
        """
        # Extract metadata from event
        session_id = event.session_id
        agent_id = event.src.replace("agent:", "") if event.src.startswith("agent:") else event.src
        event_type = event.type
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
