import asyncio
import json
import logging
from typing import Any
from uuid import uuid4

from simu_emperor.mq.event import Event
from simu_emperor.persistence.client import SeekDBClient
from simu_emperor.persistence.repositories import TapeRepository, SegmentRepository


logger = logging.getLogger(__name__)


MAX_TOKENS = 8000
THRESHOLD_RATIO = 0.95
KEEP_RECENT_EVENTS = 20


class ContextManager:
    def __init__(
        self,
        session_id: str,
        agent_id: str,
        seekdb: SeekDBClient,
    ):
        self.session_id = session_id
        self.agent_id = agent_id

        self._seekdb = seekdb
        self._tape_repo = TapeRepository(seekdb)
        self._segment_repo = SegmentRepository(seekdb)

        self._events: list[Event] = []
        self._summary: str | None = None
        self._window_offset: int = 0

    async def load(self) -> None:
        session = await self._tape_repo.get_session(self.session_id)
        if session:
            self._window_offset = session.get("window_offset", 0)
            self._summary = session.get("summary")

        events = await self._tape_repo.load_events(
            self.session_id, self.agent_id, self._window_offset
        )
        self._events = [self._parse_event(e) for e in events]

    def _parse_event(self, data: dict[str, Any]) -> Event:
        return Event(
            event_id=data.get("event_id", ""),
            event_type=data.get("event_type", ""),
            src=data.get("src", ""),
            dst=data.get("dst", []),
            session_id=data.get("session_id", ""),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", ""),
        )

    async def add_event(self, event: Event) -> None:
        self._events.append(event)
        await self._tape_repo.append_event(event)

        await self._maybe_compact()

    async def add_observation(self, tool_name: str, result: str) -> None:
        event = Event(
            event_id=str(uuid4()),
            event_type="OBSERVATION",
            src=f"agent:{self.agent_id}",
            dst=[f"agent:{self.agent_id}"],
            session_id=self.session_id,
            payload={"tool": tool_name, "result": result},
            timestamp="",
        )
        await self.add_event(event)

    async def get_llm_messages(self) -> list[dict]:
        messages = []

        system_prompt = await self._get_system_prompt()
        messages.append({"role": "system", "content": system_prompt})

        if self._summary:
            messages.append({"role": "system", "content": f"[历史摘要]\n{self._summary}"})

        for event in self._events:
            messages.extend(self._event_to_messages(event))

        return messages

    async def _get_system_prompt(self) -> str:
        return "You are an AI assistant."

    def _event_to_messages(self, event: Event) -> list[dict]:
        messages = []

        if event.event_type == "COMMAND":
            messages.append(
                {
                    "role": "user",
                    "content": event.payload.get("content", ""),
                }
            )
        elif event.event_type == "AGENT_MESSAGE":
            messages.append(
                {
                    "role": "assistant",
                    "content": event.payload.get("message", ""),
                }
            )
        elif event.event_type == "OBSERVATION":
            tool = event.payload.get("tool", "")
            result = event.payload.get("result", "")
            messages.append(
                {
                    "role": "system",
                    "content": f"[Tool: {tool}]\n{result}",
                }
            )
        else:
            messages.append(
                {
                    "role": "system",
                    "content": json.dumps(event.payload, ensure_ascii=False),
                }
            )

        return messages

    async def _maybe_compact(self) -> None:
        total_tokens = self._count_tokens()
        threshold = int(MAX_TOKENS * THRESHOLD_RATIO)

        if total_tokens < threshold and len(self._events) <= KEEP_RECENT_EVENTS:
            return

        await self._slide_window()

    def _count_tokens(self) -> int:
        total = 0
        for event in self._events:
            total += len(json.dumps(event.payload, ensure_ascii=False)) // 4
        return total

    async def _slide_window(self) -> None:
        anchor_indices = self._find_anchor_events()
        dropped_events = self._select_dropped_events(anchor_indices)

        if not dropped_events:
            return

        summary = await self._summarize_events(dropped_events)
        self._summary = await self._update_cumulative_summary(summary)

        asyncio.create_task(
            self._index_segment(
                start_pos=self._window_offset,
                end_pos=self._window_offset + len(dropped_events),
                summary=summary,
            )
        )

        self._events = self._events[len(dropped_events) :]
        self._window_offset += len(dropped_events)

        await self._tape_repo.update_window_offset(
            self.session_id, self._window_offset, self._summary or ""
        )

    def _find_anchor_events(self) -> set[int]:
        anchors: set[int] = set()
        for i, event in enumerate(self._events):
            if event.event_type in ("COMMAND", "AGENT_MESSAGE"):
                anchors.add(i)
        return anchors

    def _select_dropped_events(self, anchor_indices: set[int]) -> list[Event]:
        if len(self._events) <= KEEP_RECENT_EVENTS:
            return []

        drop_count = len(self._events) - KEEP_RECENT_EVENTS
        candidates = []

        for i, event in enumerate(self._events[:drop_count]):
            if i not in anchor_indices:
                candidates.append(event)

        return candidates[:drop_count]

    async def _summarize_events(self, events: list[Event]) -> str:
        if not events:
            return ""

        summaries = []
        for event in events:
            summaries.append(
                f"- [{event.event_type}] {json.dumps(event.payload, ensure_ascii=False)}"
            )

        return "\n".join(summaries)

    async def _update_cumulative_summary(self, new_summary: str) -> str:
        if not self._summary:
            return new_summary

        return f"{self._summary}\n\n{new_summary}"

    async def _index_segment(self, start_pos: int, end_pos: int, summary: str) -> None:
        try:
            await self._segment_repo.create_segment(
                session_id=self.session_id,
                agent_id=self.agent_id,
                start_pos=start_pos,
                end_pos=end_pos,
                summary=summary,
            )
        except Exception as e:
            logger.error(f"Failed to index segment: {e}")
