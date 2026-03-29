import json
import logging
from typing import Any
from datetime import datetime

from simu_emperor.persistence.client import SeekDBClient


logger = logging.getLogger(__name__)


class TaskSessionRepository:
    def __init__(self, client: SeekDBClient):
        self._client = client

    async def create(
        self,
        task_id: str,
        session_id: str,
        creator_id: str,
        task_type: str | None = None,
        timeout_seconds: int = 300,
    ) -> None:
        await self._client.execute(
            """
            INSERT INTO task_sessions (task_id, session_id, creator_id, task_type, timeout_seconds)
            VALUES (?, ?, ?, ?, ?)
            """,
            task_id,
            session_id,
            creator_id,
            task_type,
            timeout_seconds,
        )

    async def get(self, task_id: str) -> dict[str, Any] | None:
        return await self._client.fetch_one(
            "SELECT * FROM task_sessions WHERE task_id = ?", task_id
        )

    async def update_status(
        self,
        task_id: str,
        status: str,
        result: dict[str, Any] | None = None,
    ) -> None:
        result_json = json.dumps(result) if result else None
        completed_at = datetime.now() if status in ("completed", "failed") else None

        await self._client.execute(
            """
            UPDATE task_sessions 
            SET status = ?, result = ?, completed_at = ?
            WHERE task_id = ?
            """,
            status,
            result_json,
            completed_at,
            task_id,
        )

    async def get_by_session(self, session_id: str) -> list[dict[str, Any]]:
        return await self._client.fetch_all(
            "SELECT * FROM task_sessions WHERE session_id = ? ORDER BY created_at DESC", session_id
        )

    async def get_pending_tasks(self) -> list[dict[str, Any]]:
        return await self._client.fetch_all(
            "SELECT * FROM task_sessions WHERE status = 'pending' ORDER BY created_at ASC"
        )
