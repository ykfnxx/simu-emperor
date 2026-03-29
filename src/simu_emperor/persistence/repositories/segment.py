import logging
from typing import Any

from simu_emperor.persistence.client import SeekDBClient


logger = logging.getLogger(__name__)


class SegmentRepository:
    def __init__(self, client: SeekDBClient):
        self._client = client

    async def create_segment(
        self,
        session_id: str,
        agent_id: str,
        start_pos: int,
        end_pos: int,
        summary: str,
        embedding: bytes | None = None,
        tick: int | None = None,
    ) -> int:
        result = await self._client.execute(
            """
            INSERT INTO tape_segments (session_id, agent_id, start_pos, end_pos, summary, embedding, tick)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            session_id,
            agent_id,
            start_pos,
            end_pos,
            summary,
            embedding,
            tick,
        )
        row = await self._client.fetch_one("SELECT LAST_INSERT_ID() as id")
        return row["id"] if row else 0

    async def get_segments(self, session_id: str, agent_id: str) -> list[dict[str, Any]]:
        return await self._client.fetch_all(
            "SELECT id, session_id, agent_id, start_pos, end_pos, summary, tick, created_at FROM tape_segments WHERE session_id = ? AND agent_id = ? ORDER BY start_pos",
            session_id,
            agent_id,
        )

    async def search_by_embedding(
        self, agent_id: str, embedding: bytes, limit: int = 5
    ) -> list[dict[str, Any]]:
        return await self._client.fetch_all(
            """
            SELECT id, session_id, agent_id, start_pos, end_pos, summary, tick
 created_at 
            FROM tape_segments 
            WHERE agent_id = ?
            ORDER BY created_at DESC
 LIMIT ?
            """,
            agent_id,
            limit,
        )
