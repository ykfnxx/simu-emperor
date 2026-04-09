"""ContextManager — builds the LLM context window from local Tape events.

Implements a sliding-window strategy with anchor-aware compression.
When the event count exceeds the budget, older events are summarized
into ViewSegments and stored in ChromaDB for later retrieval.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from simu_shared.constants import EventType
from simu_shared.models import ContextConfig, MemoryConfig, TapeEvent
from simu_sdk.memory.models import ViewSegment
from simu_sdk.tape.manager import TapeManager

if TYPE_CHECKING:
    from simu_sdk.llm.base import LLMProvider
    from simu_sdk.memory.metadata import TapeMetadataManager
    from simu_sdk.memory.store import MemoryStore

logger = logging.getLogger(__name__)

# Event types that should be preserved as anchors during compression
_ANCHOR_TYPES = frozenset(
    {
        EventType.CHAT,
        EventType.RESPONSE,
        EventType.TASK_CREATED,
        EventType.TASK_FINISHED,
        EventType.TASK_FAILED,
        EventType.INCIDENT_CREATED,
    }
)


@dataclass
class ContextWindow:
    """The assembled context ready for the LLM prompt."""

    events: list[TapeEvent] = field(default_factory=list)
    summary: str = ""
    total_events: int = 0


class ContextManager:
    """Builds a bounded context window from local Tape.

    When the event count exceeds ``keep_recent_events``, older events
    are compressed into ViewSegments via LLM summarization.
    """

    def __init__(
        self,
        tape: TapeManager,
        config: ContextConfig,
        *,
        memory_config: MemoryConfig | None = None,
        metadata_manager: TapeMetadataManager | None = None,
        memory_store: MemoryStore | None = None,
        llm: LLMProvider | None = None,
        memory_dir: Path | None = None,
        agent_id: str = "",
    ) -> None:
        self._tape = tape
        self._config = config
        self._memory_config = memory_config or MemoryConfig()
        self._metadata = metadata_manager
        self._store = memory_store
        self._llm = llm
        self._memory_dir = memory_dir
        self._agent_id = agent_id

    async def get_context(self, session_id: str) -> ContextWindow:
        """Return the most recent events, plus a summary of older ones."""
        total = await self._tape.count(session_id)

        # Check if we need compression before building context
        if self._needs_compression(total) and self._metadata and self._llm:
            await self._compress(session_id, total)

        recent = await self._tape.query(
            session_id,
            limit=self._config.keep_recent_events,
        )

        # Get summary from metadata if available
        summary = ""
        if self._metadata:
            meta = await self._metadata.get_metadata(session_id)
            if meta:
                summary = meta.summary

        return ContextWindow(
            events=recent,
            summary=summary,
            total_events=total,
        )

    def _needs_compression(self, total_events: int) -> bool:
        """Check if compression should be triggered."""
        return total_events > self._config.keep_recent_events * 2

    async def _compress(self, session_id: str, total: int) -> ViewSegment | None:
        """Compress older events into a ViewSegment."""
        if not self._metadata or not self._llm:
            return None

        meta = await self._metadata.get_metadata(session_id)
        start = meta.window_offset if meta else 0
        end = total - self._config.keep_recent_events

        if end <= start:
            return None

        # Fetch events in the compression range
        events = await self._tape.query_range(session_id, offset=start, limit=end - start)
        if not events:
            return None

        # Identify compressible events (non-anchor events)
        compressible = self._identify_compressible(events)
        if not compressible:
            # All events are anchors — do NOT advance window
            return None

        # Generate summary via LLM
        summary = await self._summarize_events(compressible)
        if not summary:
            return None

        # Create ViewSegment
        view = ViewSegment(
            view_id=f"view_{session_id}_{start}_{end}",
            session_id=session_id,
            start_index=start,
            end_index=end,
            summary=summary,
            event_count=len(compressible),
        )

        # Persist
        await self._metadata.add_view(session_id, view)
        await self._metadata.advance_window(session_id, end)

        if self._store:
            await self._store.upsert_view(view)

        # Mirror to debug file
        self._mirror_view(view)

        logger.info(
            "Compressed %d events [%d:%d] for session %s",
            len(compressible),
            start,
            end,
            session_id,
        )
        return view

    def _identify_compressible(self, events: list[TapeEvent]) -> list[TapeEvent]:
        """Separate compressible events from anchors.

        Anchors and their surrounding buffer events are excluded.
        """
        buffer = self._memory_config.anchor_buffer
        n = len(events)
        keep = set()

        for i, evt in enumerate(events):
            if evt.event_type in _ANCHOR_TYPES:
                for j in range(max(0, i - buffer), min(n, i + buffer + 1)):
                    keep.add(j)

        return [evt for i, evt in enumerate(events) if i not in keep]

    async def _summarize_events(self, events: list[TapeEvent]) -> str:
        """Use LLM to generate a compressed summary of events."""
        if not self._llm:
            return ""

        formatted = []
        for evt in events:
            content = evt.payload.get("content", "")
            if not content:
                # For tool calls/results, extract meaningful text
                if evt.event_type == EventType.TOOL_CALL:
                    calls = evt.payload.get("tool_calls", [])
                    content = "; ".join(
                        f"{c.get('name', '?')}({c.get('arguments', {})})" for c in calls
                    )
                elif evt.event_type == EventType.TOOL_RESULT:
                    content = evt.payload.get("output", "")[:200]
                else:
                    content = str(evt.payload)[:200]
            formatted.append(f"[{evt.event_type}] {evt.src}: {content}")

        events_text = "\n".join(formatted)

        response = await self._llm.call(
            messages=[
                {
                    "role": "user",
                    "content": (
                        "将以下对话事件压缩为 2-3 句话的中文摘要，"
                        "保留关键决策、数值和结果。不超过 200 token。\n\n"
                        f"事件：\n{events_text}"
                    ),
                }
            ],
            system="你是一个简洁的摘要生成器。只输出摘要本身。",
        )
        return response.content.strip()

    async def update_session_summary(
        self,
        session_id: str,
        recent_events: list[TapeEvent],
    ) -> str | None:
        """Generate a replacement session summary after agent response.

        Called by the agent after each response. Takes the old summary
        + recent events and produces a new fixed-length summary.
        """
        if not self._metadata or not self._llm:
            return None

        meta = await self._metadata.get_metadata(session_id)
        old_summary = meta.summary if meta else ""

        # Extract content from recent events
        recent_parts = []
        for evt in recent_events:
            content = evt.payload.get("content", "")
            if content:
                recent_parts.append(f"[{evt.event_type}] {evt.src}: {content}")
        recent_text = "\n".join(recent_parts)

        if not recent_text and not old_summary:
            return None

        # Generate replacement summary via LLM
        prompt_parts = [
            "你是一个会话摘要生成器。根据旧摘要和新增对话内容，"
            "生成一段完整的中文摘要。\n\n要求：\n"
            "- 不超过 300 token\n"
            "- 保留关键决策、数值、人名和结果\n"
            "- 新内容优先级高于旧摘要中的过时信息\n"
            "- 只输出摘要本身\n",
        ]
        if old_summary:
            prompt_parts.append(f"旧摘要：\n{old_summary}\n")
        prompt_parts.append(f"新增内容：\n{recent_text}")

        response = await self._llm.call(
            messages=[{"role": "user", "content": "\n".join(prompt_parts)}],
            system="你是一个简洁的摘要生成器。只输出摘要本身。",
        )
        new_summary = response.content.strip()

        # Persist and update ChromaDB
        await self._metadata.update_summary(session_id, new_summary)
        if self._store and meta:
            await self._store.upsert_session_summary(
                session_id,
                new_summary,
                title=meta.title,
            )

        # Mirror to debug file (overwrite)
        self._mirror_summary(session_id, new_summary, title=meta.title if meta else "")

        logger.debug("Updated session summary for %s", session_id)
        return new_summary

    async def generate_title(self, event: TapeEvent) -> str:
        """Generate a session title from the first event via LLM."""
        if not self._llm:
            return event.session_id

        content = event.payload.get("content", "")
        if not content:
            return event.session_id

        try:
            response = await self._llm.call(
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "根据以下对话的开头，生成一个简短的中文标题（不超过20字）。"
                            "只输出标题本身，不要加引号或其他标点。\n\n"
                            f"内容：{content}"
                        ),
                    }
                ],
                system="你是一个标题生成器。只输出标题。",
            )
            title = response.content.strip()
            return title if title else event.session_id
        except Exception:
            logger.warning(
                "Title generation failed for session %s", event.session_id, exc_info=True
            )
            return event.session_id

    # ------------------------------------------------------------------
    # Debug mirrors — write views/summaries to data/memory/ for debugging
    # ------------------------------------------------------------------

    def _get_mirror_dir(self) -> Path | None:
        """Return the agent's mirror directory, or None if mirroring is disabled."""
        if not self._memory_dir or not self._agent_id:
            return None
        d = self._memory_dir / "agents" / self._agent_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _mirror_view(self, view: ViewSegment) -> None:
        """Append a ViewSegment to views.jsonl for debugging."""
        mirror_dir = self._get_mirror_dir()
        if not mirror_dir:
            return
        try:
            line = json.dumps(
                {
                    "view_id": view.view_id,
                    "session_id": view.session_id,
                    "start_index": view.start_index,
                    "end_index": view.end_index,
                    "summary": view.summary,
                    "event_count": view.event_count,
                },
                ensure_ascii=False,
            )
            with open(mirror_dir / "views.jsonl", "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            logger.warning("Failed to mirror view", exc_info=True)

    def _mirror_summary(self, session_id: str, summary: str, *, title: str = "") -> None:
        """Overwrite summaries.jsonl with current session summaries.

        Unlike views.jsonl (append), this file is rewritten each time
        so it always reflects the latest replacement summary per session.
        """
        mirror_dir = self._get_mirror_dir()
        if not mirror_dir:
            return
        try:
            path = mirror_dir / "summaries.jsonl"

            # Read existing entries (one JSON object per line)
            existing: dict[str, dict] = {}
            if path.exists():
                for raw_line in path.read_text(encoding="utf-8").splitlines():
                    raw_line = raw_line.strip()
                    if raw_line:
                        obj = json.loads(raw_line)
                        existing[obj["session_id"]] = obj

            # Upsert current session
            existing[session_id] = {
                "session_id": session_id,
                "title": title,
                "summary": summary,
            }

            # Rewrite file
            with open(path, "w", encoding="utf-8") as f:
                for obj in existing.values():
                    f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        except Exception:
            logger.warning("Failed to mirror summary", exc_info=True)
