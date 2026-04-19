"""MessageStore — persists routed messages for frontend display.

Dual-write: SQLite (primary) + data/memory/ JSONL (debug convenience).
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from simu_shared.models import RoutedMessage
from simu_server.stores.database import Database

logger = logging.getLogger(__name__)


class MessageStore:
    """SQLite-backed message persistence for the Client API."""

    def __init__(self, db: Database, memory_dir: Path | None = None) -> None:
        self._db = db
        self._memory_dir = memory_dir

    async def store(self, msg: RoutedMessage) -> None:
        await self._db.conn.execute(
            """
            INSERT INTO messages (message_id, session_id, src, dst, content, event_type, timestamp, origin_event_id, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg.message_id,
                msg.session_id,
                msg.src,
                json.dumps(msg.dst),
                msg.content,
                msg.event_type,
                msg.timestamp.isoformat(),
                msg.origin_event_id,
                msg.payload_json,
            ),
        )
        await self._db.conn.commit()
        if self._memory_dir is not None:
            # Fire-and-forget: debug mirror write, errors logged internally
            asyncio.get_running_loop().run_in_executor(
                None, self._write_to_memory, msg,
            )

    def _write_to_memory(self, msg: RoutedMessage) -> None:
        """Append message as JSONL to data/memory/ for debugging."""
        if self._memory_dir is None:
            return
        try:
            self._memory_dir.mkdir(parents=True, exist_ok=True)

            # Per-session message log
            session_dir = self._memory_dir / "sessions" / msg.session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            line = msg.model_dump_json() + "\n"
            with open(session_dir / "messages.jsonl", "a", encoding="utf-8") as f:
                f.write(line)

            # tape_meta.jsonl — session-level index for quick overview
            meta_entry = json.dumps({
                "session_id": msg.session_id,
                "src": msg.src,
                "dst": msg.dst,
                "event_type": msg.event_type,
                "timestamp": msg.timestamp.isoformat(),
                "message_id": msg.message_id,
            }) + "\n"
            with open(self._memory_dir / "tape_meta.jsonl", "a", encoding="utf-8") as f:
                f.write(meta_entry)
        except Exception:
            logger.warning("Failed to write message to memory dir", exc_info=True)

    async def query(
        self,
        session_id: str,
        limit: int = 100,
        before: str | None = None,
    ) -> list[RoutedMessage]:
        if before:
            cursor = await self._db.conn.execute(
                """
                SELECT * FROM messages
                WHERE session_id = ? AND timestamp < ?
                ORDER BY timestamp DESC LIMIT ?
                """,
                (session_id, before, limit),
            )
        else:
            cursor = await self._db.conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit),
            )
        rows = await cursor.fetchall()
        return [self._row_to_message(r) for r in reversed(rows)]

    @staticmethod
    def _row_to_message(row: tuple) -> RoutedMessage:
        return RoutedMessage(
            message_id=row[0],
            session_id=row[1],
            src=row[2],
            dst=json.loads(row[3]),
            content=row[4],
            event_type=row[5],
            timestamp=row[6],
            origin_event_id=row[7],
            payload_json=row[8] if len(row) > 8 else None,
        )
