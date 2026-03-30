"""SegmentSearcher for searching event segments within tape.jsonl files (V4)."""

import asyncio
import aiofiles
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from simu_emperor.memory.models import TapeView, TapeMetadataEntry
from simu_emperor.memory.query_parser import StructuredQuery
from simu_emperor.memory.config import SEGMENT_SIZE

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SegmentSearcher:
    """Searches continuous event segments within tape.jsonl files (Level 2 Search)."""

    def __init__(self, memory_dir: Path):
        """
        Initialize SegmentSearcher.

        Args:
            memory_dir: Base memory directory path
        """
        self.memory_dir = memory_dir

    async def search_segments(
        self,
        agent_id: str,
        matching_entries: list[TapeMetadataEntry],
        query: StructuredQuery,
        max_results: int = 5,
        candidate_segment_ids: list[str] | None = None,
    ) -> list[TapeView]:
        """
        Search segments within matching tapes.

        Args:
            agent_id: Agent identifier
            matching_entries: TapeMetadataEntry list from Level 1
            query: Parsed query from QueryParser
            max_results: Maximum segments to return
            candidate_segment_ids: Optional list from vector search for re-ranking

        Returns:
            List of TapeView, sorted by relevance_score descending

        Flow:
            1. For each entry, read corresponding tape.jsonl
            2. Split into SEGMENT_SIZE chunks
            3. Calculate score for each segment
            4. Merge and sort, return top N

        If candidate_segment_ids provided, boost relevance for matching segments.
        """
        if not matching_entries:
            return []

        # Search all tapes concurrently
        search_tasks = [
            self._search_single_tape(
                self._get_tape_path(agent_id, entry.session_id),
                entry,
                query,
            )
            for entry in matching_entries
        ]

        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Flatten results, filtering out exceptions
        all_segments = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Error searching tape: {result}")
                continue
            all_segments.extend(result)

        # Apply vector ranking boost if candidates provided
        if candidate_segment_ids:
            all_segments = self._apply_vector_ranking(all_segments, candidate_segment_ids)

        # Sort by score and return top N
        all_segments.sort(key=lambda s: s.relevance_score, reverse=True)
        return all_segments[:max_results]

    def _apply_vector_ranking(
        self,
        segments: list[TapeView],
        candidate_ids: list[str],
        boost_factor: float = 2.0,
    ) -> list[TapeView]:
        """
        Boost relevance scores for segments that match vector search results.

        Args:
            segments: List of views to re-rank
            candidate_ids: Segment IDs from vector search (ordered by relevance)
            boost_factor: Score multiplier for vector matches

        Returns:
            List of views with updated relevance scores
        """
        # Create position map for ranked candidates
        id_to_rank = {seg_id: idx for idx, seg_id in enumerate(candidate_ids)}

        boosted_segments = []
        for segment in segments:
            seg_id = self._make_segment_id(segment)
            base_score = segment.relevance_score

            if seg_id in id_to_rank:
                # Boost score based on vector rank (higher rank = bigger boost)
                rank = id_to_rank[seg_id]
                rank_bonus = (len(candidate_ids) - rank) / len(candidate_ids)
                new_score = base_score + (boost_factor * rank_bonus)
            else:
                new_score = base_score * 0.5  # Penalize non-vector matches

            # Create new TapeView with updated score
            boosted_segments.append(
                TapeView(
                    view_id=segment.view_id,
                    session_id=segment.session_id,
                    agent_id=segment.agent_id,
                    anchor_start_id=segment.anchor_start_id,
                    anchor_end_id=segment.anchor_end_id,
                    tape_position_start=segment.tape_position_start,
                    tape_position_end=segment.tape_position_end,
                    events=segment.events,
                    anchor_state=segment.anchor_state,
                    tick_start=segment.tick_start,
                    tick_end=segment.tick_end,
                    event_count=segment.event_count,
                    relevance_score=new_score,
                )
            )

        return boosted_segments

    def _make_segment_id(self, view: TapeView) -> str:
        """Generate segment ID matching VectorSearcher format."""
        return f"{view.session_id}:{view.tape_position_start}:{view.tape_position_end}"

    async def _search_single_tape(
        self,
        tape_path: Path,
        entry: TapeMetadataEntry,
        query: StructuredQuery,
    ) -> list[TapeView]:
        """
        Search a single tape file for matching segments.

        Args:
            tape_path: Path to tape.jsonl
            entry: TapeMetadataEntry for this tape
            query: Parsed query

        Returns:
            List of TapeView from this tape
        """
        if not tape_path.exists():
            return []

        # Read all events from tape
        events = []
        try:
            async with aiofiles.open(tape_path, mode="r", encoding="utf-8") as f:
                line_count = 0
                async for line in f:
                    if line.strip():
                        try:
                            event = json.loads(line)
                            events.append(event)
                            line_count += 1
                        except json.JSONDecodeError:
                            continue
        except (IOError, OSError) as e:
            logger.warning(f"Failed to read tape {tape_path}: {e}")
            return []

        if not events:
            return []

        # Split into segments and score
        segments = []
        for i in range(0, len(events), SEGMENT_SIZE):
            segment_events = events[i : i + SEGMENT_SIZE]
            view = self._create_view(
                segment_events, i, entry, agent_id=self._extract_agent_id(tape_path)
            )
            # Calculate relevance score
            segment_score = self._calculate_segment_score(segment_events, query.entities)

            # Create new TapeView with score (frozen dataclass, so we recreate)
            scored_view = TapeView(
                view_id=view.view_id,
                session_id=view.session_id,
                agent_id=view.agent_id,
                anchor_start_id=view.anchor_start_id,
                anchor_end_id=view.anchor_end_id,
                tape_position_start=view.tape_position_start,
                tape_position_end=view.tape_position_end,
                events=view.events,
                anchor_state=view.anchor_state,
                tick_start=view.tick_start,
                tick_end=view.tick_end,
                event_count=view.event_count,
                relevance_score=segment_score,
            )

            if segment_score > 0:
                segments.append(scored_view)

        return segments

    def _create_view(
        self,
        events: list[dict],
        start_pos: int,
        entry: TapeMetadataEntry,
        agent_id: str,
    ) -> TapeView:
        """
        Create a TapeView from event list.

        Args:
            events: List of event dicts
            start_pos: Starting position in tape
            entry: TapeMetadataEntry for this tape
            agent_id: Agent identifier

        Returns:
            TapeView instance
        """
        tick_start, tick_end = self._extract_tick_range(events)

        return TapeView(
            view_id=f"view:{entry.session_id}:{start_pos}:{start_pos + len(events) - 1}",
            session_id=entry.session_id,
            agent_id=agent_id,
            anchor_start_id=None,
            anchor_end_id=None,
            tape_position_start=start_pos,
            tape_position_end=start_pos + len(events) - 1,
            events=events,
            anchor_state=None,
            tick_start=tick_start,
            tick_end=tick_end,
            event_count=len(events),
            relevance_score=0.0,
        )

    def _calculate_segment_score(self, segment_events: list[dict], entities: dict) -> float:
        """
        Calculate relevance score for a segment.

        Args:
            segment_events: List of event dicts in segment
            entities: {action: [], target: [], time: ""}

        Returns:
            Relevance score (0.0 - 1.0+)
        """
        score = 0.0

        actions = entities.get("action", [])
        targets = entities.get("target", [])
        time_entity = entities.get("time", "")

        # Build segment text content
        segment_text = ""
        for event in segment_events:
            event_payload = event.get("payload") or event.get("content", {})
            if isinstance(event_payload, dict):
                segment_text += str(event_payload) + " "
            else:
                segment_text += str(event_payload) + " "

            event_type = event.get("type") or event.get("event_type", "")
            segment_text += event_type + " "

        segment_text_lower = segment_text.lower()

        # Action matching
        for action in actions:
            if action.lower() in segment_text_lower:
                score += 0.4

        # Target matching
        for target in targets:
            if target.lower() in segment_text_lower:
                score += 0.3

        # Time matching
        if time_entity == "history":
            score += 0.2

        return score

    def _extract_tick_range(self, events: list[dict]) -> tuple[int | None, int | None]:
        """
        Extract tick range from event list.

        Args:
            events: List of event dicts

        Returns:
            Tuple of (tick_start, tick_end) or (None, None)
        """
        ticks = []
        for event in events:
            # Check various possible locations for tick
            tick = None
            if "tick" in event:
                tick = event.get("tick")
            elif "payload" in event:
                tick = event["payload"].get("tick")

            if tick is not None:
                try:
                    ticks.append(int(tick))
                except (ValueError, TypeError):
                    pass

        if ticks:
            return min(ticks), max(ticks)
        return None, None

    def _extract_timestamp_range(self, events: list[dict]) -> tuple[str | None, str | None]:
        """
        Extract timestamp range from event list.

        Args:
            events: List of event dicts

        Returns:
            Tuple of (timestamp_start, timestamp_end) or (None, None)
        """
        timestamps = []
        for event in events:
            timestamp = event.get("timestamp") or event.get("created_at")
            if timestamp:
                timestamps.append(timestamp)

        if timestamps:
            return min(timestamps), max(timestamps)
        return None, None

    def _get_tape_path(self, agent_id: str, session_id: str) -> Path:
        """Get tape.jsonl path for a session."""
        return self.memory_dir / "agents" / agent_id / "sessions" / session_id / "tape.jsonl"

    def _extract_agent_id(self, tape_path: Path) -> str:
        """Extract agent_id from tape_path."""
        # Expected path: .../agents/{agent_id}/sessions/...
        parts = tape_path.parts
        if "agents" in parts:
            idx = parts.index("agents")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        return "unknown"
