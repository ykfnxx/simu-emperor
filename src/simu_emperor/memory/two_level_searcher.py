"""TwoLevelSearcher for coordinated two-level memory search (V4)."""

import logging
from typing import TYPE_CHECKING

from simu_emperor.memory.models import TapeSegment
from simu_emperor.memory.query_parser import StructuredQuery
from simu_emperor.memory.config import DEFAULT_MAX_RESULTS

if TYPE_CHECKING:
    from simu_emperor.memory.tape_metadata_index import TapeMetadataIndex
    from simu_emperor.memory.segment_searcher import SegmentSearcher
    from simu_emperor.memory.vector_searcher import VectorSearcher

logger = logging.getLogger(__name__)


class TwoLevelSearcher:
    """
    Two-level search: Level 1 searches tape_meta.jsonl, Level 2 searches specific tapes.

    Coordinates TapeMetadataIndex and SegmentSearcher for efficient memory retrieval.

    Optional Level 1.5: VectorSearcher provides semantic ranking when available.
    """

    def __init__(
        self,
        tape_metadata_index: "TapeMetadataIndex",
        segment_searcher: "SegmentSearcher",
        vector_searcher: "VectorSearcher | None" = None,
    ):
        """
        Initialize TwoLevelSearcher.

        Args:
            tape_metadata_index: Level 1 searcher (metadata filtering)
            segment_searcher: Level 2 searcher (segment retrieval)
            vector_searcher: Optional Level 1.5 searcher (semantic ranking)
        """
        self.metadata_index = tape_metadata_index
        self.segment_searcher = segment_searcher
        self.vector_searcher = vector_searcher

    async def search(
        self,
        query: StructuredQuery,
        agent_id: str,
        exclude_session: str | None = None,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> list[TapeSegment]:
        """
        Execute two-level search with optional vector ranking.

        Args:
            query: Parsed query from QueryParser
            agent_id: Agent identifier
            exclude_session: Session ID to exclude (current session)
            max_results: Maximum segments to return

        Returns:
            List of TapeSegment, sorted by relevance

        Flow:
            Level 1: TapeMetadataIndex.search_tape_metadata()
            Level 1.5: VectorSearcher.search() (optional, for semantic ranking)
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

        # Level 1.5: Vector search for semantic ranking (optional)
        candidate_segment_ids = None
        if self.vector_searcher and query.raw_query:
            try:
                candidate_segment_ids = await self.vector_searcher.search(
                    query=query.raw_query,
                    agent_id=agent_id,
                    n_results=max_results * 2,  # Get more candidates for re-ranking
                )
                logger.debug(f"Level 1.5 found {len(candidate_segment_ids)} vector candidates")
            except Exception as e:
                logger.warning(f"Vector search failed, falling back to keyword search: {e}")

        # Level 2: Search segments within matching tapes
        segments = await self.segment_searcher.search_segments(
            agent_id=agent_id,
            matching_entries=matching_entries,
            query=query,
            max_results=max_results,
            candidate_segment_ids=candidate_segment_ids,  # Pass vector candidates
        )

        logger.debug(f"Level 2 found {len(segments)} matching segments")
        return segments
