"""TapeMetadataManager for managing tape_meta.jsonl files (V4)."""

import asyncio
import aiofiles
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
import uuid

from simu_emperor.memory.models import TapeMetadataEntry

if TYPE_CHECKING:
    from simu_emperor.event_bus.event import Event
    from simu_emperor.event_bus.core import EventBus
    from simu_emperor.llm.base import LLMProvider

logger = logging.getLogger(__name__)


async def _atomic_write(path: Path, content: str) -> None:
    """
    Write content to a file atomically using temp file + rename pattern.

    This prevents data corruption when multiple processes/threads write
    to the same file simultaneously. On POSIX systems, rename() is atomic.

    Args:
        path: Target file path
        content: Content to write

    Raises:
        IOError: If write or rename operation fails
    """
    # Create temp file in same directory (ensures same filesystem)
    temp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")

    try:
        # Write to temp file
        async with aiofiles.open(temp_path, mode="w", encoding="utf-8") as f:
            await f.write(content)

        # Atomic rename (overwrites target if exists)
        temp_path.replace(path)

    except Exception as e:
        # Clean up temp file on failure
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        raise IOError(f"Atomic write failed for {path}: {e}") from e


class TapeMetadataManager:
    """Manages tape_meta.jsonl read/write operations (V4 Memory System)."""

    METADATA_FILE = "tape_meta.jsonl"
    MAX_TITLE_LENGTH = 50

    def __init__(
        self,
        memory_dir: Path,
        event_bus: "EventBus | None" = None,
    ):
        """
        Initialize TapeMetadataManager.

        Args:
            memory_dir: Base memory directory path
            event_bus: Optional event bus for broadcasting metadata updates
        """
        self.memory_dir = memory_dir
        self._event_bus = event_bus
        self._metadata_lock = asyncio.Lock()

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
        async with self._metadata_lock:
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
                    window_offset=existing_entry.window_offset,
                    summary=existing_entry.summary,
                    segment_index=existing_entry.segment_index,
                )
                await self._update_entry_in_file(metadata_path, session_id, updated_entry)
                logger.debug(f"Updated tape metadata for {agent_id}/{session_id}")
                return updated_entry

            # Create new entry with placeholder title
            title = f"Session {session_id[:8]}"  # Use session ID prefix as temp title

            new_entry = TapeMetadataEntry(
                session_id=session_id,
                title=title,
                created_tick=current_tick,
                created_time=now,
                last_updated_tick=current_tick,
                last_updated_time=now,
                event_count=0,
                window_offset=0,
                summary="",
                segment_index=[],
            )

            await self._append_entry_to_file(metadata_path, new_entry)
            logger.info(f"Created tape metadata for {agent_id}/{session_id}: {title}")

        # Generate title asynchronously (non-blocking)
        if first_event and llm:
            asyncio.create_task(self._generate_and_update_title(
                agent_id, session_id, first_event, llm, metadata_path
            ))

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
        async with self._metadata_lock:
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
        query = payload.get("query", "") or payload.get("message", "")
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
                task_type="title_generation",
            )
            # Clean up response
            title = response.strip().strip('"').strip("'")
            # Truncate if needed
            if len(title) > self.MAX_TITLE_LENGTH:
                title = title[: self.MAX_TITLE_LENGTH]
            return title if title else "Untitled (LLM failed)"
        except Exception as e:
            logger.warning(f"LLM title generation failed: {type(e).__name__}: {e}")
            return "Untitled (LLM failed)"

    async def _generate_and_update_title(
        self,
        agent_id: str,
        session_id: str,
        first_event: "Event",
        llm: "LLMProvider",
        metadata_path: Path,
    ) -> None:
        """Generate title asynchronously and update metadata file."""
        try:
            from simu_emperor.event_bus.event import Event
            from simu_emperor.event_bus.event_types import EventType

            title = await self._generate_title(first_event, llm)
            async with self._metadata_lock:
                existing_entry = await self._find_entry(metadata_path, session_id)

                if existing_entry:
                    updated_time = datetime.now(timezone.utc).isoformat()
                    updated_entry = TapeMetadataEntry(
                        session_id=existing_entry.session_id,
                        title=title,
                        created_tick=existing_entry.created_tick,
                        created_time=existing_entry.created_time,
                        last_updated_tick=existing_entry.last_updated_tick,
                        last_updated_time=updated_time,
                        event_count=existing_entry.event_count,
                        window_offset=existing_entry.window_offset,
                        summary=existing_entry.summary,
                        segment_index=existing_entry.segment_index,
                    )
                    await self._update_entry_in_file(metadata_path, session_id, updated_entry)
                    logger.info(f"Updated title for {agent_id}/{session_id}: {title}")

            if existing_entry and self._event_bus is not None:
                await self._event_bus.send_event(
                    Event(
                        src="system:memory",
                        dst=["*"],
                        type=EventType.SESSION_STATE,
                        session_id=session_id,
                        payload={
                            "session_id": session_id,
                            "agent_id": agent_id,
                            "title": title,
                            "event_count": updated_entry.event_count,
                            "last_update": updated_entry.last_updated_time,
                        },
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to update title for {session_id}: {e}")

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
        async with self._metadata_lock:
            metadata_path = self._get_metadata_path(agent_id)
            existing_entry = await self._find_entry(metadata_path, session_id)

            if not existing_entry:
                logger.warning(f"Cannot update segment_index: entry not found for {session_id}")
                return

            # Check for duplicate ranges and remove them
            updated_index = []
            for seg in existing_entry.segment_index:
                # Keep only segments with different ranges
                if not (
                    seg.get("start") == segment_info.get("start")
                    and seg.get("end") == segment_info.get("end")
                ):
                    updated_index.append(seg)

            # Append new segment
            updated_index.append(segment_info)

            updated_entry = TapeMetadataEntry(
                session_id=existing_entry.session_id,
                title=existing_entry.title,
                created_tick=existing_entry.created_tick,
                created_time=existing_entry.created_time,
                last_updated_tick=existing_entry.last_updated_tick,
                last_updated_time=existing_entry.last_updated_time,
                event_count=existing_entry.event_count,
                window_offset=existing_entry.window_offset,
                summary=existing_entry.summary,
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
        async with self._metadata_lock:
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
                window_offset=existing_entry.window_offset,
                summary=existing_entry.summary,
                segment_index=existing_entry.segment_index,
            )

            await self._update_entry_in_file(metadata_path, session_id, updated_entry)

    async def update_summary(
        self,
        agent_id: str,
        session_id: str,
        summary: str,
    ) -> None:
        """
        Update the cumulative summary for a tape.

        Called by ContextManager.slide_window() after compacting events.

        Args:
            agent_id: Agent identifier
            session_id: Session identifier
            summary: New cumulative summary
        """
        async with self._metadata_lock:
            metadata_path = self._get_metadata_path(agent_id)
            existing_entry = await self._find_entry(metadata_path, session_id)

            if not existing_entry:
                logger.warning(f"Cannot update summary: entry not found for {session_id}")
                return

            updated_entry = TapeMetadataEntry(
                session_id=existing_entry.session_id,
                title=existing_entry.title,
                created_tick=existing_entry.created_tick,
                created_time=existing_entry.created_time,
                last_updated_tick=existing_entry.last_updated_tick,
                last_updated_time=existing_entry.last_updated_time,
                event_count=existing_entry.event_count,
                window_offset=existing_entry.window_offset,
                summary=summary,
                segment_index=existing_entry.segment_index,
            )

            await self._update_entry_in_file(metadata_path, session_id, updated_entry)
        logger.debug(f"Updated summary for {agent_id}/{session_id}")

    async def update_window_offset(
        self,
        agent_id: str,
        session_id: str,
        window_offset: int,
    ) -> None:
        """
        Update the window offset position anchor for a tape.

        Called by ContextManager.slide_window() after compacting events.

        Args:
            agent_id: Agent identifier
            session_id: Session identifier
            window_offset: New window offset position
        """
        async with self._metadata_lock:
            metadata_path = self._get_metadata_path(agent_id)
            existing_entry = await self._find_entry(metadata_path, session_id)

            if not existing_entry:
                logger.warning(f"Cannot update window_offset: entry not found for {session_id}")
                return

            updated_entry = TapeMetadataEntry(
                session_id=existing_entry.session_id,
                title=existing_entry.title,
                created_tick=existing_entry.created_tick,
                created_time=existing_entry.created_time,
                last_updated_tick=existing_entry.last_updated_tick,
                last_updated_time=existing_entry.last_updated_time,
                event_count=existing_entry.event_count,
                window_offset=window_offset,
                summary=existing_entry.summary,
                segment_index=existing_entry.segment_index,
            )

            await self._update_entry_in_file(metadata_path, session_id, updated_entry)
        logger.debug(f"Updated window_offset for {agent_id}/{session_id}: {window_offset}")

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
        Append a new entry to tape_meta.jsonl using atomic write pattern.

        Uses atomic write pattern (temp file + rename) to prevent
        data loss from concurrent modifications.

        Args:
            metadata_path: Path to tape_meta.jsonl
            entry: Entry to append
        """
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        # Read existing content (if file exists)
        existing_content = ""
        if metadata_path.exists():
            try:
                async with aiofiles.open(metadata_path, mode="r", encoding="utf-8") as f:
                    existing_content = await f.read()
            except (IOError, OSError) as e:
                logger.warning(f"Failed to read existing metadata file: {e}")
                # Continue with empty content

        # Append new entry
        new_entry_json = json.dumps(entry.to_dict(), ensure_ascii=False) + "\n"
        updated_content = existing_content + new_entry_json

        # Atomic write using temp file + rename
        try:
            await _atomic_write(metadata_path, updated_content)
        except IOError as e:
            logger.error(f"Failed to atomically append to metadata file: {e}")
            raise

    async def _update_entry_in_file(
        self, metadata_path: Path, session_id: str, updated_entry: TapeMetadataEntry
    ) -> None:
        """
        Update an existing entry in tape_meta.jsonl using atomic write pattern.

        Since JSONL is append-only, we rewrite the entire file
        with the updated entry replacing the old one.

        Uses atomic write pattern (temp file + rename) to prevent
        data loss from concurrent modifications.

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

        # Build content for atomic write
        content = "\n".join(
            json.dumps(entry_data, ensure_ascii=False) for entry_data in entries
        )
        if content:  # Ensure trailing newline
            content += "\n"

        # Atomic write using temp file + rename
        try:
            await _atomic_write(metadata_path, content)
        except IOError as e:
            logger.error(f"Failed to atomically write metadata file: {e}")
            raise

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
