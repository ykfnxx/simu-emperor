"""MemoryStore — ChromaDB vector storage for views and session summaries.

Each agent gets one ChromaDB collection containing two document types:
  - view: view segment summaries
  - session_summary: per-session replacement summaries
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

import chromadb

from simu_sdk.memory.models import ViewSegment

logger = logging.getLogger(__name__)


@dataclass
class ViewSearchResult:
    """A single view result from vector search."""

    view_id: str
    session_id: str
    session_title: str
    summary: str
    score: float  # distance → lower is closer


@dataclass
class SessionSearchResult:
    """A single session result from vector search."""

    session_id: str
    title: str
    summary: str
    score: float


class MemoryStore:
    """ChromaDB-backed vector store for agent memory.

    All ChromaDB operations are synchronous; we wrap them in
    ``asyncio.to_thread()`` to avoid blocking the event loop.
    """

    def __init__(self, agent_id: str, persist_dir: Path) -> None:
        self._agent_id = agent_id
        self._persist_dir = persist_dir
        self._client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None

    async def initialize(self) -> None:
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = await asyncio.to_thread(
            chromadb.PersistentClient,
            path=str(self._persist_dir),
        )
        self._collection = await asyncio.to_thread(
            self._client.get_or_create_collection,
            name=f"agent_{self._agent_id}",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "MemoryStore initialized for agent %s at %s",
            self._agent_id,
            self._persist_dir,
        )

    async def close(self) -> None:
        self._collection = None
        self._client = None

    # ------------------------------------------------------------------
    # Upsert operations
    # ------------------------------------------------------------------

    async def upsert_view(self, view: ViewSegment) -> None:
        """Store or update a view segment's embedding."""
        if not self._collection:
            return
        try:
            await asyncio.to_thread(
                self._collection.upsert,
                ids=[view.view_id],
                documents=[view.summary],
                metadatas=[
                    {
                        "type": "view",
                        "session_id": view.session_id,
                        "start_index": view.start_index,
                        "end_index": view.end_index,
                    }
                ],
            )
        except Exception:
            logger.warning("Failed to upsert view %s", view.view_id, exc_info=True)

    async def upsert_session_summary(
        self,
        session_id: str,
        summary: str,
        title: str = "",
    ) -> None:
        """Store or update a session's summary embedding."""
        if not self._collection or not summary:
            return
        doc_id = f"summary_{session_id}"
        try:
            await asyncio.to_thread(
                self._collection.upsert,
                ids=[doc_id],
                documents=[summary],
                metadatas=[
                    {
                        "type": "session_summary",
                        "session_id": session_id,
                        "title": title,
                    }
                ],
            )
        except Exception:
            logger.warning("Failed to upsert session summary %s", session_id, exc_info=True)

    # ------------------------------------------------------------------
    # Search operations
    # ------------------------------------------------------------------

    async def search_views(
        self,
        query: str,
        n_results: int = 5,
        session_ids: list[str] | None = None,
    ) -> list[ViewSearchResult]:
        """Semantic search over view summaries."""
        if not self._collection:
            return []

        where_filter: dict | None = {"type": "view"}
        if session_ids:
            where_filter = {
                "$and": [
                    {"type": "view"},
                    {"session_id": {"$in": session_ids}},
                ],
            }

        try:
            results = await asyncio.to_thread(
                self._collection.query,
                query_texts=[query],
                n_results=n_results,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            logger.warning("View search failed", exc_info=True)
            return []

        return self._parse_view_results(results)

    async def search_sessions(
        self,
        query: str,
        n_results: int = 10,
    ) -> list[SessionSearchResult]:
        """Semantic search over session summaries."""
        if not self._collection:
            return []

        try:
            results = await asyncio.to_thread(
                self._collection.query,
                query_texts=[query],
                n_results=n_results,
                where={"type": "session_summary"},
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            logger.warning("Session search failed", exc_info=True)
            return []

        return self._parse_session_results(results)

    # ------------------------------------------------------------------
    # Result parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_view_results(results: dict) -> list[ViewSearchResult]:
        out: list[ViewSearchResult] = []
        if not results or not results.get("ids"):
            return out
        ids = results["ids"][0]
        docs = results["documents"][0] if results.get("documents") else [""] * len(ids)
        metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(ids)
        dists = results["distances"][0] if results.get("distances") else [1.0] * len(ids)
        for view_id, doc, meta, dist in zip(ids, docs, metas, dists):
            out.append(
                ViewSearchResult(
                    view_id=view_id,
                    session_id=meta.get("session_id", ""),
                    session_title=meta.get("title", ""),
                    summary=doc or "",
                    score=1.0 - dist,  # cosine distance → similarity
                )
            )
        return out

    @staticmethod
    def _parse_session_results(results: dict) -> list[SessionSearchResult]:
        out: list[SessionSearchResult] = []
        if not results or not results.get("ids"):
            return out
        ids = results["ids"][0]
        docs = results["documents"][0] if results.get("documents") else [""] * len(ids)
        metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(ids)
        dists = results["distances"][0] if results.get("distances") else [1.0] * len(ids)
        for _doc_id, doc, meta, dist in zip(ids, docs, metas, dists):
            out.append(
                SessionSearchResult(
                    session_id=meta.get("session_id", ""),
                    title=meta.get("title", ""),
                    summary=doc or "",
                    score=1.0 - dist,
                )
            )
        return out
