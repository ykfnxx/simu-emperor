"""TapeManager — local JSONL + SQLite dual-write event storage.

Each Agent process owns its own Tape storage directory.  The TapeManager
handles append, query, and metadata indexing entirely on the Agent side;
the Server never touches Tape data.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import aiofiles
import aiosqlite

from simu_shared.models import TapeEvent

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS tape_events (
    event_id   TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    src        TEXT NOT NULL,
    dst        TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload    TEXT NOT NULL,
    timestamp  TEXT NOT NULL,
    parent_event_id TEXT,
    root_event_id   TEXT,
    invocation_id   TEXT
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_tape_session ON tape_events (session_id, timestamp);
"""


class TapeManager:
    """Append-only event log with JSONL + SQLite dual-write.

    Directory layout::

        {base_dir}/
        ├── sessions/{session_id}/tape.jsonl
        └── tape.db
    """

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = base_dir / "tape.db"
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open the SQLite database and ensure schema exists."""
        self._db = await aiosqlite.connect(str(self._db_path))
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute(_CREATE_TABLE)
        await self._db.execute(_CREATE_INDEX)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    async def append(self, event: TapeEvent) -> None:
        """Append an event to both JSONL and SQLite."""
        await self._append_jsonl(event)
        await self._append_sqlite(event)

    async def query(
        self,
        session_id: str,
        limit: int = 100,
        after_event_id: str | None = None,
    ) -> list[TapeEvent]:
        """Query the most recent events for a session, in chronological order."""
        assert self._db is not None
        if after_event_id:
            cursor = await self._db.execute(
                """
                SELECT * FROM tape_events
                WHERE session_id = ? AND timestamp > (
                    SELECT timestamp FROM tape_events WHERE event_id = ?
                )
                ORDER BY timestamp ASC LIMIT ?
                """,
                (session_id, after_event_id, limit),
            )
            rows = await cursor.fetchall()
        else:
            # Fetch the N most recent events, then reverse to chronological order
            cursor = await self._db.execute(
                "SELECT * FROM tape_events WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit),
            )
            rows = list(reversed(await cursor.fetchall()))
        return [self._row_to_event(row) for row in rows]

    async def count(self, session_id: str) -> int:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM tape_events WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _append_jsonl(self, event: TapeEvent) -> None:
        session_dir = self._base_dir / "sessions" / event.session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        tape_path = session_dir / "tape.jsonl"
        line = event.model_dump_json() + "\n"
        async with aiofiles.open(tape_path, "a") as f:
            await f.write(line)

    async def _append_sqlite(self, event: TapeEvent) -> None:
        assert self._db is not None
        await self._db.execute(
            """
            INSERT OR IGNORE INTO tape_events
            (event_id, session_id, src, dst, event_type, payload,
             timestamp, parent_event_id, root_event_id, invocation_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.session_id,
                event.src,
                json.dumps(event.dst),
                event.event_type,
                json.dumps(event.payload),
                event.timestamp.isoformat(),
                event.parent_event_id,
                event.root_event_id,
                event.invocation_id,
            ),
        )
        await self._db.commit()

    @staticmethod
    def _row_to_event(row: tuple) -> TapeEvent:
        return TapeEvent(
            event_id=row[0],
            session_id=row[1],
            src=row[2],
            dst=json.loads(row[3]),
            event_type=row[4],
            payload=json.loads(row[5]),
            timestamp=row[6],
            parent_event_id=row[7],
            root_event_id=row[8],
            invocation_id=row[9],
        )
