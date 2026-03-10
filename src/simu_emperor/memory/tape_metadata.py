"""TapeMetadataManager for managing tape_meta.jsonl files (V4)."""

import aiofiles
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from simu_emperor.memory.models import TapeMetadataEntry
from simu_emperor.memory.config import SEGMENT_SIZE

if TYPE_CHECKING:
    from simu_emperor.event_bus.event import Event
    from simu_emperor.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class TapeMetadataManager:
    """Manages tape_meta.jsonl read/write operations (V4 Memory System)."""

    METADATA_FILE = "tape_meta.jsonl"
    MAX_TITLE_LENGTH = 50

    def __init__(self, memory_dir: Path):
        """
        Initialize TapeMetadataManager.

        Args:
            memory_dir: Base memory directory path
        """
        self.memory_dir = memory_dir

    async def append_or_update_entry(
        self,
        agent_id: str,
        session_id: str,
        first_event: "Event | None" = None,
        llm: "LLMProvider | None" = None,
        current_tick: int | None = None,
    ) -> TapeMetadataEntry:
        """
        Append new entry or update existing entry in tape_meta.jsonl.

        Determines operation internally:
        - If session_id entry doesn't exist → Create new entry with title from first_event
        - If entry exists → Update timestamps and tick only

        Args:
            agent_id: Agent identifier
            session_id: Session identifier
            first_event: First event of session (for title generation on creation)
            llm: LLM provider for title generation
            current_tick: Current game tick

        Returns:
            TapeMetadataEntry instance
        """
        metadata_path = self._get_metadata_path(agent_id)
        existing_entry = await self._find_entry(metadata_path, session_id)
        now = datetime.now(timezone.utc).isoformat()

        if existing_entry:
            # Update existing entry
            updated_entry = TapeMetadataEntry(
                session_id=existing_entry.session_id,
                title=existing_entry.title,
                created_tick=existing_entry.created_tick,
                created_time=existing_entry.created_time,
                last_updated_tick=current_tick or existing_entry.last_updated_tick,
                last_updated_time=now,
                event_count=existing_entry.event_count,
                segment_index=existing_entry.segment_index,
            )
            await self._update_entry_in_file(metadata_path, session_id, updated_entry)
            logger.debug(f"Updated tape metadata for {agent_id}/{session_id}")
            return updated_entry

        # Create new entry
        title = "Untitled Session"
        if first_event and llm:
            try:
                title = await self._generate_title(first_event, llm)
            except Exception as e:
                logger.warning(f"Failed to generate title: {e}")

        new_entry = TapeMetadataEntry(
            session_id=session_id,
            title=title,
            created_tick=current_tick,
            created_time=now,
            last_updated_tick=current_tick,
            last_updated_time=now,
            event_count=0,
            segment_index=[],
        )

        await self._append_entry_to_file(metadata_path, new_entry)
        logger.info(f"Created tape metadata for {agent_id}/{session_id}: {title}")
        return new_entry

    async def update_entry(
        self,
        agent_id: str,
        entry: TapeMetadataEntry,
    ) -> None:
        """
        Update existing entry (for segment_index updates).

        Args:
            agent_id: Agent identifier
            entry: Updated entry to write
        """
        metadata_path = self._get_metadata_path(agent_id)
        await self._update_entry_in_file(metadata_path, entry.session_id, entry)

    async def _generate_title(
        self, first_event: "Event", llm: "LLMProvider"
    ) -> str:
        """
        Use LLM to generate session title.

        Args:
            first_event: First event of session
            llm: LLM provider

        Returns:
            Generated title string (≤MAX_TITLE_LENGTH chars)

        Example:
            Input: Event(type="command", payload={"query": "调整直隶税收"})
            Output: "直隶税收政策调整"
        """
        event_type = first_event.type
        payload = first_event.payload or {}

        # Extract relevant context from payload
        query = payload.get("query", "")
        intent = payload.get("intent", "")
        province = payload.get("province", "")

        prompt = f"""Generate a concise title (≤{self.MAX_TITLE_LENGTH} Chinese characters) for this session.

Event type: {event_type}
Query: {query}
Intent: {intent}
Province: {province}

Guidelines:
- Focus on the main topic (e.g., "税收调整", "赈灾拨款", "人事任免")
- Include province name if relevant
- Use简洁的中文
- Return ONLY the title, no explanation"""

        try:
            response = await llm.call(
                prompt=prompt,
                system_prompt="You are a title generator for a historical Chinese emperor simulation game.",
                temperature=0.3,
                max_tokens=100,
            )
            # Clean up response
            title = response.strip().strip('"').strip("'")
            # Truncate if needed
            if len(title) > self.MAX_TITLE_LENGTH:
                title = title[: self.MAX_TITLE_LENGTH]
            return title if title else "Session"
        except Exception as e:
            logger.warning(f"LLM title generation failed: {e}")
            return "Session"

    async def update_segment_index(
        self,
        agent_id: str,
        session_id: str,
        segment_info: dict,
    ) -> None:
        """
        Update segment_index for a specific tape.

        Called by ContextManager.slide_window() after compaction.

        Args:
            agent_id: Agent identifier
            session_id: Session identifier
            segment_info: {"start": 0, "end": 10, "summary": "...", "tick": 5}
        """
        metadata_path = self._get_metadata_path(agent_id)
        existing_entry = await self._find_entry(metadata_path, session_id)

        if not existing_entry:
            logger.warning(f"Cannot update segment_index: entry not found for {session_id}")
            return

        # Add new segment to index
        updated_index = list(existing_entry.segment_index)
        updated_index.append(segment_info)

        updated_entry = TapeMetadataEntry(
            session_id=existing_entry.session_id,
            title=existing_entry.title,
            created_tick=existing_entry.created_tick,
            created_time=existing_entry.created_time,
            last_updated_tick=existing_entry.last_updated_tick,
            last_updated_time=existing_entry.last_updated_time,
            event_count=existing_entry.event_count,
            segment_index=updated_index,
        )

        await self._update_entry_in_file(metadata_path, session_id, updated_entry)
        logger.debug(f"Updated segment_index for {agent_id}/{session_id}")

    async def increment_event_count(
        self,
        agent_id: str,
        session_id: str,
    ) -> None:
        """
        Increment event count for a tape.

        Called after writing events to tape.jsonl.

        Args:
            agent_id: Agent identifier
            session_id: Session identifier
        """
        metadata_path = self._get_metadata_path(agent_id)
        existing_entry = await self._find_entry(metadata_path, session_id)

        if not existing_entry:
            logger.warning(f"Cannot increment event count: entry not found for {session_id}")
            return

        updated_entry = TapeMetadataEntry(
            session_id=existing_entry.session_id,
            title=existing_entry.title,
            created_tick=existing_entry.created_tick,
            created_time=existing_entry.created_time,
            last_updated_tick=existing_entry.last_updated_tick,
            last_updated_time=existing_entry.last_updated_time,
            event_count=existing_entry.event_count + 1,
            segment_index=existing_entry.segment_index,
        )

        await self._update_entry_in_file(metadata_path, session_id, updated_entry)

    def _get_metadata_path(self, agent_id: str) -> Path:
        """
        Get the tape_meta.jsonl path for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Path to tape_meta.jsonl file
        """
        return (
            self.memory_dir / "agents" / agent_id / self.METADATA_FILE
        )

    async def _find_entry(
        self, metadata_path: Path, session_id: str
    ) -> TapeMetadataEntry | None:
        """
        Find an entry by session_id in tape_meta.jsonl.

        Args:
            metadata_path: Path to tape_meta.jsonl
            session_id: Session identifier to find

        Returns:
            TapeMetadataEntry if found, None otherwise
        """
        if not metadata_path.exists():
            return None

        try:
            async with aiofiles.open(metadata_path, mode="r", encoding="utf-8") as f:
                async for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if data.get("session_id") == session_id:
                                return TapeMetadataEntry.from_dict(data)
                        except json.JSONDecodeError:
                            continue
        except (IOError, OSError) as e:
            logger.warning(f"Failed to read metadata file {metadata_path}: {e}")

        return None

    async def _append_entry_to_file(
        self, metadata_path: Path, entry: TapeMetadataEntry
    ) -> None:
        """
        Append a new entry to tape_meta.jsonl.

        Args:
            metadata_path: Path to tape_meta.jsonl
            entry: Entry to append
        """
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(metadata_path, mode="a", encoding="utf-8") as f:
            await f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    async def _update_entry_in_file(
        self, metadata_path: Path, session_id: str, updated_entry: TapeMetadataEntry
    ) -> None:
        """
        Update an existing entry in tape_meta.jsonl.

        Since JSONL is append-only, we rewrite the entire file
        with the updated entry replacing the old one.

        Args:
            metadata_path: Path to tape_meta.jsonl
            session_id: Session identifier to update
            updated_entry: Updated entry data
        """
        if not metadata_path.exists():
            logger.warning(f"Cannot update non-existent file: {metadata_path}")
            return

        # Read all entries
        entries = []
        try:
            async with aiofiles.open(metadata_path, mode="r", encoding="utf-8") as f:
                async for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if data.get("session_id") != session_id:
                                entries.append(data)
                        except json.JSONDecodeError:
                            continue
        except (IOError, OSError) as e:
            logger.warning(f"Failed to read metadata file: {e}")
            return

        # Add updated entry
        entries.append(updated_entry.to_dict())

        # Rewrite file
        async with aiofiles.open(metadata_path, mode="w", encoding="utf-8") as f:
            for entry_data in entries:
                await f.write(json.dumps(entry_data, ensure_ascii=False) + "\n")

    async def get_all_entries(self, agent_id: str) -> list[TapeMetadataEntry]:
        """
        Get all metadata entries for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            List of all TapeMetadataEntry for the agent
        """
        metadata_path = self._get_metadata_path(agent_id)
        entries = []

        if not metadata_path.exists():
            return entries

        try:
            async with aiofiles.open(metadata_path, mode="r", encoding="utf-8") as f:
                async for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            entries.append(TapeMetadataEntry.from_dict(data))
                        except json.JSONDecodeError:
                            continue
        except (IOError, OSError) as e:
            logger.warning(f"Failed to read metadata file: {e}")

        return entries
