"""MessageStore — persists routed messages for frontend display."""

from __future__ import annotations

import json

from simu_shared.models import RoutedMessage
from simu_server.stores.database import Database


class MessageStore:
    """SQLite-backed message persistence for the Client API."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def store(self, msg: RoutedMessage) -> None:
        await self._db.conn.execute(
            """
            INSERT INTO messages (message_id, session_id, src, dst, content, event_type, timestamp, origin_event_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        await self._db.conn.commit()

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
        )
