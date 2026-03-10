"""TwoLevelSearcher for coordinated two-level memory search (V4)."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from simu_emperor.memory.models import TapeSegment
from simu_emperor.memory.query_parser import StructuredQuery
from simu_emperor.memory.config import DEFAULT_MAX_RESULTS

if TYPE_CHECKING:
    from simu_emperor.memory.tape_metadata_index import TapeMetadataIndex
    from simu_emperor.memory.segment_searcher import SegmentSearcher

logger = logging.getLogger(__name__)


class TwoLevelSearcher:
    """
    Two-level search: Level 1 searches tape_meta.jsonl, Level 2 searches specific tapes.

    Coordinates TapeMetadataIndex and SegmentSearcher for efficient memory retrieval.
    """

    def __init__(
        self,
        tape_metadata_index: "TapeMetadataIndex",
        segment_searcher: "SegmentSearcher",
    ):
        """
        Initialize TwoLevelSearcher.

        Args:
            tape_metadata_index: Level 1 searcher (metadata filtering)
            segment_searcher: Level 2 searcher (segment retrieval)
        """
        self.metadata_index = tape_metadata_index
        self.segment_searcher = segment_searcher

    async def search(
        self,
        query: StructuredQuery,
        agent_id: str,
        exclude_session: str | None = None,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> list[TapeSegment]:
        """
        Execute two-level search.

        Args:
            query: Parsed query from QueryParser
            agent_id: Agent identifier
            exclude_session: Session ID to exclude (current session)
            max_results: Maximum segments to return

        Returns:
            List of TapeSegment, sorted by relevance

        Flow:
            Level 1: TapeMetadataIndex.search_tape_metadata()
            Level 2: SegmentSearcher.search_segments()
        """
        # Level 1: Search metadata to find relevant tapes
        matching_entries = await self.metadata_index.search_tape_metadata(
            agent_id=agent_id,
            query=query,
        )

        # Filter out excluded session if specified
        if exclude_session:
            matching_entries = [
                e for e in matching_entries if e.session_id != exclude_session
            ]

        if not matching_entries:
            logger.debug(f"No matching tapes found for agent {agent_id}")
            return []

        logger.debug(
            f"Level 1 found {len(matching_entries)} matching tapes for agent {agent_id}"
        )

        # Level 2: Search segments within matching tapes
        segments = await self.segment_searcher.search_segments(
            agent_id=agent_id,
            matching_entries=matching_entries,
            query=query,
            max_results=max_results,
        )

        logger.debug(f"Level 2 found {len(segments)} matching segments")
        return segments
