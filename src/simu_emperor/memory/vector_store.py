"""Enhanced VectorStore with async retry and failure tracking (V4.2 Phase 3)."""

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Callable, Awaitable

from simu_emperor.config import settings
from simu_emperor.memory.models import TapeView

if TYPE_CHECKING:
    from simu_emperor.memory.vector_searcher import VectorSearcher

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Enhanced vector store with async retry and failure tracking.

    Wraps VectorSearcher with:
    - Async retry with exponential backoff
    - Failed embedding tracking via callback
    - Graceful degradation when ChromaDB unavailable
    """

    def __init__(
        self,
        vector_searcher: "VectorSearcher | None" = None,
        on_embedding_failed: "Callable[[str, str, dict, str], Awaitable[None]] | None" = None,
    ):
        """
        Initialize VectorStore.

        Args:
            vector_searcher: Optional VectorSearcher instance for embeddings
            on_embedding_failed: Optional callback for failed embeddings
                (segment_id, document, metadata, error_message)
        """
        self._searcher = vector_searcher
        self._on_embedding_failed = on_embedding_failed
        self._max_retries = settings.embedding.max_retries
        self._retry_delay = settings.embedding.retry_delay

    @property
    def enabled(self) -> bool:
        """Check if vector store is enabled."""
        return (
            settings.embedding.enabled and settings.chromadb.enabled and self._searcher is not None
        )

    async def add_segments_with_retry(self, segments: list[TapeView]) -> None:
        """
        Add segments to vector store with retry logic.

        Args:
            segments: List of TapeView to add
        """
        if not self.enabled or not segments:
            return

        for segment in segments:
            segment_id = f"seg_{segment.session_id}_{segment.tape_position_start}_{segment.tape_position_end}"
            metadata = {
                "agent_id": segment.agent_id,
                "session_id": segment.session_id,
                "segment_start": segment.tape_position_start,
                "segment_end": segment.tape_position_end,
                "tick": segment.tick_start,
            }
            doc = self._searcher._segment_to_text(segment) if self._searcher else segment.to_text()
            try:
                await self._store_with_retry(segment_id, doc, metadata, segment)
            except Exception:
                pass  # Failure already logged and tracked via on_embedding_failed

    async def _store_with_retry(
        self, segment_id: str, document: str, metadata: dict, segment: TapeView
    ) -> None:
        """
        Store a segment with exponential backoff retry.

        Args:
            segment_id: Unique segment identifier
            document: Text document for embedding
            metadata: Metadata dict
            segment: TapeView object
        """
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                if self._searcher:
                    await asyncio.to_thread(self._searcher.add_segments, [segment])
                logger.info(f"Stored embedding for {segment_id}")
                return
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Embedding attempt {attempt + 1}/{self._max_retries} failed for {segment_id}: {e}"
                )
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_delay * (attempt + 1))

        if self._on_embedding_failed and last_error:
            await self._on_embedding_failed(segment_id, document[:500], metadata, str(last_error))
            logger.error(f"All retries failed for {segment_id}, recorded to failed_embeddings")

        if last_error:
            raise last_error

    async def search(self, query: str, agent_id: str, n_results: int = 5) -> list[str]:
        """
        Search for similar segments by query text.

        Args:
            query: Query text
            agent_id: Agent identifier for filtering
            n_results: Maximum number of results to return

        Returns:
            List of segment IDs, ordered by relevance (empty list on failure)
        """
        if not self.enabled or not self._searcher:
            return []
        try:
            return await self._searcher.search(query, agent_id, n_results)
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []

    async def retry_failed_embeddings(
        self, get_failed: Callable, mark_retried: Callable, remove_failed: Callable, limit: int = 50
    ) -> int:
        """
        Retry failed embeddings from a persistent store.

        Args:
            get_failed: Async callable to get failed records (limit) -> list[dict]
            mark_retried: Async callable to mark a record as retried (segment_id)
            remove_failed: Async callable to remove a failed record (segment_id)
            limit: Maximum number of failed records to process

        Returns:
            Number of successfully retried embeddings
        """
        failed = await get_failed(limit)
        retried = 0
        for record in failed:
            try:
                metadata = (
                    json.loads(record["metadata"])
                    if isinstance(record["metadata"], str)
                    else record["metadata"]
                )
                segment = TapeView(
                    view_id=f"view:{metadata.get('session_id', '')}:{metadata.get('segment_start', 0)}:{metadata.get('segment_end', 0)}",
                    session_id=metadata.get("session_id", ""),
                    agent_id=metadata.get("agent_id", ""),
                    anchor_start_id=None,
                    anchor_end_id=None,
                    tape_position_start=metadata.get("segment_start", 0),
                    tape_position_end=metadata.get("segment_end", 0),
                    events=[],
                    anchor_state=None,
                    tick_start=metadata.get("tick"),
                    tick_end=metadata.get("tick"),
                    event_count=0,
                )
                await self._store_with_retry(
                    record["segment_id"], record["summary"], metadata, segment
                )
                await remove_failed(record["segment_id"])
                retried += 1
            except Exception as e:
                await mark_retried(record["segment_id"])
                logger.warning(f"Retry failed for {record['segment_id']}: {e}")
        return retried
