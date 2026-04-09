"""InvocationManager — tracks Agent invocation lifecycles.

Each time the Server dispatches an event to an Agent, an Invocation record
is created to track the call from queue through completion.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from simu_shared.models import Invocation, InvocationStatus, TapeEvent
from simu_server.stores.database import Database

logger = logging.getLogger(__name__)


class InvocationManager:
    """Manages Agent invocation records backed by SQLite."""

    def __init__(self, db: Database, timeout: int = 600) -> None:
        self._db = db
        self._timeout = timeout

    async def create(self, agent_id: str, session_id: str, event: TapeEvent) -> Invocation:
        inv = Invocation(
            agent_id=agent_id,
            session_id=session_id,
            trigger_event_id=event.event_id,
        )
        await self._db.conn.execute(
            """
            INSERT INTO invocations
            (invocation_id, agent_id, session_id, trigger_event_id, status, callback_token, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                inv.invocation_id,
                inv.agent_id,
                inv.session_id,
                inv.trigger_event_id,
                inv.status.value,
                inv.callback_token,
                inv.created_at.isoformat(),
            ),
        )
        await self._db.conn.commit()
        return inv

    async def complete(
        self,
        invocation_id: str,
        status: InvocationStatus = InvocationStatus.SUCCEEDED,
        error: str | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        await self._db.conn.execute(
            "UPDATE invocations SET status = ?, completed_at = ?, error = ? WHERE invocation_id = ?",
            (status.value, now, error, invocation_id),
        )
        await self._db.conn.commit()

    async def mark_running(self, invocation_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        await self._db.conn.execute(
            "UPDATE invocations SET status = ?, started_at = ? WHERE invocation_id = ?",
            (InvocationStatus.RUNNING.value, now, invocation_id),
        )
        await self._db.conn.commit()

    async def get(self, invocation_id: str) -> Invocation | None:
        cursor = await self._db.conn.execute(
            "SELECT * FROM invocations WHERE invocation_id = ?",
            (invocation_id,),
        )
        row = await cursor.fetchone()
        return self._row_to_invocation(row) if row else None

    async def get_active_for_agent(self, agent_id: str) -> list[Invocation]:
        cursor = await self._db.conn.execute(
            "SELECT * FROM invocations WHERE agent_id = ? AND status IN ('queued', 'running')",
            (agent_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_invocation(r) for r in rows]

    async def validate_callback(self, invocation_id: str, callback_token: str) -> bool:
        inv = await self.get(invocation_id)
        return inv is not None and inv.callback_token == callback_token

    @staticmethod
    def _row_to_invocation(row: tuple) -> Invocation:
        return Invocation(
            invocation_id=row[0],
            agent_id=row[1],
            session_id=row[2],
            trigger_event_id=row[3],
            status=InvocationStatus(row[4]),
            callback_token=row[5],
            created_at=row[6],
            started_at=row[7],
            completed_at=row[8],
            error=row[9],
        )
