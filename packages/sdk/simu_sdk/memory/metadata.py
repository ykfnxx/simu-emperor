"""TapeMetadataManager — SQLite-backed session metadata and view index.

Responsibilities:
  - Store/query per-session metadata (title, summary, window_offset)
  - Manage view segment index
  - Keyword search across session titles and summaries
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from simu_sdk.memory.models import TapeMetadata, ViewSegment

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tape_metadata (
    session_id        TEXT PRIMARY KEY,
    title             TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL,
    event_count       INTEGER DEFAULT 0,
    window_offset     INTEGER DEFAULT 0,
    summary           TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS view_segments (
    view_id           TEXT PRIMARY KEY,
    session_id        TEXT NOT NULL,
    start_index       INTEGER NOT NULL,
    end_index         INTEGER NOT NULL,
    summary           TEXT NOT NULL,
    event_count       INTEGER NOT NULL,
    created_at        TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES tape_metadata(session_id)
);

CREATE INDEX IF NOT EXISTS idx_views_session ON view_segments (session_id);
"""


class TapeMetadataManager:
    """Manages per-session metadata in a local SQLite database."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    # ------------------------------------------------------------------
    # Session metadata CRUD
    # ------------------------------------------------------------------

    async def has_metadata(self, session_id: str) -> bool:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT 1 FROM tape_metadata WHERE session_id = ?",
            (session_id,),
        )
        return (await cursor.fetchone()) is not None

    async def create_metadata(self, session_id: str, title: str) -> TapeMetadata:
        assert self._db is not None
        now = datetime.now(UTC).isoformat()
        await self._db.execute(
            "INSERT OR IGNORE INTO tape_metadata (session_id, title, created_at) VALUES (?, ?, ?)",
            (session_id, title, now),
        )
        await self._db.commit()
        return TapeMetadata(session_id=session_id, title=title)

    async def get_metadata(self, session_id: str) -> TapeMetadata | None:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT session_id, title, created_at, event_count, window_offset, summary "
            "FROM tape_metadata WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        # Load associated views
        views = await self._get_views(session_id)
        return TapeMetadata(
            session_id=row[0],
            title=row[1],
            created_at=row[2],
            event_count=row[3],
            window_offset=row[4],
            summary=row[5],
            views=views,
        )

    async def update_summary(self, session_id: str, summary: str) -> None:
        assert self._db is not None
        await self._db.execute(
            "UPDATE tape_metadata SET summary = ? WHERE session_id = ?",
            (summary, session_id),
        )
        await self._db.commit()

    async def update_event_count(self, session_id: str, count: int) -> None:
        assert self._db is not None
        await self._db.execute(
            "UPDATE tape_metadata SET event_count = ? WHERE session_id = ?",
            (count, session_id),
        )
        await self._db.commit()

    async def advance_window(self, session_id: str, new_offset: int) -> None:
        assert self._db is not None
        await self._db.execute(
            "UPDATE tape_metadata SET window_offset = ? WHERE session_id = ?",
            (new_offset, session_id),
        )
        await self._db.commit()

    # ------------------------------------------------------------------
    # View segment management
    # ------------------------------------------------------------------

    async def add_view(self, session_id: str, view: ViewSegment) -> None:
        assert self._db is not None
        await self._db.execute(
            """
            INSERT OR REPLACE INTO view_segments
            (view_id, session_id, start_index, end_index, summary, event_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                view.view_id,
                session_id,
                view.start_index,
                view.end_index,
                view.summary,
                view.event_count,
                view.created_at.isoformat(),
            ),
        )
        await self._db.commit()

    async def _get_views(self, session_id: str) -> list[ViewSegment]:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT view_id, session_id, start_index, end_index, summary, event_count, created_at "
            "FROM view_segments WHERE session_id = ? ORDER BY start_index",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [
            ViewSegment(
                view_id=r[0],
                session_id=r[1],
                start_index=r[2],
                end_index=r[3],
                summary=r[4],
                event_count=r[5],
                created_at=r[6],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Keyword search across sessions
    # ------------------------------------------------------------------

    async def keyword_search(
        self,
        query: str,
        exclude_session: str | None = None,
        max_results: int = 10,
    ) -> list[tuple[str, float]]:
        """Search sessions by keyword matching on title, summary, and view summaries.

        Returns list of (session_id, score) tuples sorted by relevance.
        """
        assert self._db is not None
        query_lower = query.lower()
        terms = query_lower.split()
        if not terms:
            return []

        # Fetch all session metadata
        cursor = await self._db.execute("SELECT session_id, title, summary FROM tape_metadata")
        rows = await cursor.fetchall()

        results: list[tuple[str, float]] = []
        for session_id, title, summary in rows:
            if exclude_session and session_id == exclude_session:
                continue

            score = 0.0
            title_lower = (title or "").lower()
            summary_lower = (summary or "").lower()

            for term in terms:
                if term in title_lower:
                    score += 0.4
                if term in summary_lower:
                    score += 0.4

            # Check view summaries
            views = await self._get_views(session_id)
            for view in views:
                view_lower = view.summary.lower()
                for term in terms:
                    if term in view_lower:
                        score += 0.2 / max(len(views), 1)

            if score > 0:
                results.append((session_id, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:max_results]

    async def list_all_sessions(self) -> list[TapeMetadata]:
        """Return all session metadata (for vector store bootstrap)."""
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT session_id, title, created_at, event_count, window_offset, summary "
            "FROM tape_metadata ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [
            TapeMetadata(
                session_id=r[0],
                title=r[1],
                created_at=r[2],
                event_count=r[3],
                window_offset=r[4],
                summary=r[5],
            )
            for r in rows
        ]
