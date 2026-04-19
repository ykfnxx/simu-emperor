"""MemoryRetriever — two-level memory search.

L1: Session-level — keyword + vector search to find relevant sessions.
L2: View-level — vector search within matched sessions for precise results.
"""

from __future__ import annotations

import asyncio
import logging

from simu_sdk.memory.metadata import TapeMetadataManager
from simu_sdk.memory.models import MemoryResult
from simu_sdk.memory.store import MemoryStore

logger = logging.getLogger(__name__)


class MemoryRetriever:
    """Two-level retrieval: session summary → view segments."""

    def __init__(
        self,
        metadata_manager: TapeMetadataManager,
        memory_store: MemoryStore,
    ) -> None:
        self._metadata = metadata_manager
        self._store = memory_store

    async def search(
        self,
        query: str,
        current_session_id: str,
        max_sessions: int = 5,
        max_views: int = 5,
    ) -> list[MemoryResult]:
        """Search agent memory using two-level retrieval.

        L1: Find relevant sessions via keyword + vector search.
        L2: Find relevant views within those sessions via vector search.
        """
        if not query.strip():
            return []

        # L1: Session-level search
        # Keyword search
        keyword_hits = await self._metadata.keyword_search(
            query,
            exclude_session=current_session_id,
            max_results=max_sessions * 2,
        )

        # Vector search on session summaries
        vector_hits = await self._store.search_sessions(
            query,
            n_results=max_sessions * 2,
        )

        # Merge and rank
        session_scores: dict[str, float] = {}
        for session_id, score in keyword_hits:
            if session_id != current_session_id:
                session_scores[session_id] = session_scores.get(session_id, 0) + score

        for hit in vector_hits:
            if hit.session_id != current_session_id:
                session_scores[hit.session_id] = session_scores.get(hit.session_id, 0) + hit.score

        # Sort by combined score, take top N
        ranked_sessions = sorted(
            session_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:max_sessions]

        if not ranked_sessions:
            return []

        session_ids = [s[0] for s in ranked_sessions]

        # L2: View-level search within matched sessions
        view_hits = await self._store.search_views(
            query,
            n_results=max_views,
            session_ids=session_ids,
        )

        if not view_hits:
            # Fall back to session summaries if no views exist yet
            # Parallel metadata fetch (skip views — only need title/summary)
            metas = await asyncio.gather(
                *(self._metadata.get_metadata(sid, load_views=False)
                  for sid, _ in ranked_sessions)
            )
            results: list[MemoryResult] = []
            for (session_id, score), meta in zip(ranked_sessions, metas):
                if meta and meta.summary:
                    results.append(
                        MemoryResult(
                            session_id=session_id,
                            session_title=meta.title,
                            view_summary=meta.summary,
                            relevance_score=score,
                        )
                    )
            return results[:max_views]

        # Build results from view hits, enriching with session title
        # Parallel metadata fetch for all unique sessions (skip views)
        unique_sids = list({v.session_id for v in view_hits})
        metas = await asyncio.gather(
            *(self._metadata.get_metadata(sid, load_views=False)
              for sid in unique_sids)
        )
        title_cache = {
            sid: (meta.title if meta else "")
            for sid, meta in zip(unique_sids, metas)
        }

        results = []
        for view in view_hits:
            results.append(
                MemoryResult(
                    session_id=view.session_id,
                    session_title=title_cache.get(view.session_id, ""),
                    view_summary=view.summary,
                    relevance_score=view.score,
                )
            )

        return results
