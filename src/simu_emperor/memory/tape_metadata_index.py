"""TapeMetadataIndex for searching tape_meta.jsonl files (V4)."""

import logging
from pathlib import Path

from simu_emperor.memory.models import TapeMetadataEntry
from simu_emperor.memory.query_parser import StructuredQuery
from simu_emperor.memory.config import (
    TITLE_MATCH_WEIGHT,
    SUMMARY_MATCH_WEIGHT,
    SEGMENT_MATCH_WEIGHT,
)

logger = logging.getLogger(__name__)


class TapeMetadataIndex:
    """Searches tape_meta.jsonl, returns matching tape metadata (Level 1 Search)."""

    def __init__(self, memory_dir: Path):
        """
        Initialize TapeMetadataIndex.

        Args:
            memory_dir: Base memory directory path
        """
        self.memory_dir = memory_dir

    async def search_tape_metadata(
        self,
        agent_id: str,
        query: StructuredQuery,
    ) -> list[TapeMetadataEntry]:
        """
        Search tape_meta.jsonl, return matching tape list.

        Args:
            agent_id: Agent identifier
            query: Parsed query from QueryParser

        Returns:
            List of matching TapeMetadataEntry, sorted by relevance

        Strategy:
            1. Read tape_meta.jsonl
            2. Calculate match score for each entry (title + summary)
            3. Return entries with score > 0
        """
        from simu_emperor.memory.tape_metadata import TapeMetadataManager

        mgr = TapeMetadataManager(memory_dir=self.memory_dir)
        all_entries = await mgr.get_all_entries(agent_id)

        if not all_entries:
            return []

        # Score each entry
        scored_entries = []
        entities = query.entities

        for entry in all_entries:
            score = self._calculate_entry_score(entry, entities)
            if score > 0:
                # Attach score for sorting (not persisted)
                scored_entries.append((entry, score))

        # Sort by score descending
        scored_entries.sort(key=lambda x: x[1], reverse=True)

        # Return entries only (without scores)
        return [entry for entry, _ in scored_entries]

    def _calculate_entry_score(
        self, entry: TapeMetadataEntry, entities: dict
    ) -> float:
        """
        Calculate relevance score for a metadata entry.

        Args:
            entry: TapeMetadataEntry
            entities: {action: [], target: [], time: ""}

        Returns:
            Relevance score (0.0 - 1.0+)

        Scoring:
            - title match: +TITLE_MATCH_WEIGHT per keyword
            - summary match: +SUMMARY_MATCH_WEIGHT per keyword
            - segment_index match: +SEGMENT_MATCH_WEIGHT per matching segment
        """
        score = 0.0

        # Extract keywords from entities
        actions = entities.get("action", [])
        targets = entities.get("target", [])
        time_entity = entities.get("time", "")

        # Combine all keywords for matching
        all_keywords = actions + targets

        # Score title (highest weight)
        title_lower = entry.title.lower()
        for keyword in all_keywords:
            if keyword.lower() in title_lower:
                score += TITLE_MATCH_WEIGHT

        # Score segment_index summaries (medium weight)
        for segment in entry.segment_index:
            summary = segment.get("summary", "").lower()
            for keyword in all_keywords:
                if keyword.lower() in summary:
                    score += SUMMARY_MATCH_WEIGHT
                    break  # Count each segment once

        # Score segment_index tick ranges (context bonus)
        if time_entity and time_entity == "history":
            # Bonus for having historical segments
            if entry.segment_index:
                score += SEGMENT_MATCH_WEIGHT

        return score
