"""SessionManager — CRUD operations for game sessions."""

from __future__ import annotations

import json
import logging
from typing import Any

from simu_shared.models import Session, SessionStatus
from simu_server.stores.database import Database

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages Session lifecycle backed by SQLite."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, created_by: str = "player", parent_id: str | None = None) -> Session:
        session = Session(created_by=created_by, parent_id=parent_id)
        await self._db.conn.execute(
            """
            INSERT INTO sessions (session_id, parent_id, status, created_by, agent_ids, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.session_id,
                session.parent_id,
                session.status.value,
                session.created_by,
                json.dumps(session.agent_ids),
                json.dumps(session.metadata),
                session.created_at.isoformat(),
                session.updated_at.isoformat(),
            ),
        )
        await self._db.conn.commit()
        return session

    async def get(self, session_id: str) -> Session | None:
        cursor = await self._db.conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_session(row)

    async def list_all(self) -> list[Session]:
        cursor = await self._db.conn.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC",
        )
        rows = await cursor.fetchall()
        return [self._row_to_session(r) for r in rows]

    async def update_status(self, session_id: str, status: SessionStatus) -> None:
        await self._db.conn.execute(
            "UPDATE sessions SET status = ?, updated_at = datetime('now') WHERE session_id = ?",
            (status.value, session_id),
        )
        await self._db.conn.commit()

    async def add_agent(self, session_id: str, agent_id: str) -> None:
        session = await self.get(session_id)
        if session and agent_id not in session.agent_ids:
            session.agent_ids.append(agent_id)
            await self._db.conn.execute(
                "UPDATE sessions SET agent_ids = ?, updated_at = datetime('now') WHERE session_id = ?",
                (json.dumps(session.agent_ids), session_id),
            )
            await self._db.conn.commit()

    @staticmethod
    def _row_to_session(row: tuple) -> Session:
        return Session(
            session_id=row[0],
            parent_id=row[1],
            status=SessionStatus(row[2]),
            created_by=row[3],
            agent_ids=json.loads(row[4]),
            metadata=json.loads(row[5]),
            created_at=row[6],
            updated_at=row[7],
        )
