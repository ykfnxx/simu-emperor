import json
import logging
from typing import Any

from simu_emperor.mq.event import Event
from simu_emperor.persistence.client import SeekDBClient


logger = logging.getLogger(__name__)


class TapeRepository:
    def __init__(self, client: SeekDBClient):
        self._client = client

    def _extract_agent_id(self, event: Event) -> str:
        if event.src.startswith("agent:"):
            return event.src[6:]
        return event.src

    async def append_event(self, event: Event, tick: int | None = None) -> int:
        await self._client.execute(
            """
            INSERT INTO tape_events 
            (session_id, agent_id, event_type, event_id, src, dst, payload, tick)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            event.session_id,
            self._extract_agent_id(event),
            event.event_type,
            event.event_id,
            event.src,
            json.dumps(event.dst),
            json.dumps(event.payload),
            tick,
        )
        row = await self._client.fetch_one("SELECT LAST_INSERT_ID() as id")
        return row["id"] if row else 0

    async def load_events(
        self, session_id: str, agent_id: str, offset: int = 0, limit: int | None = None
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT * FROM tape_events
            WHERE session_id = ? AND agent_id = ? AND id > ?
            ORDER BY id ASC
        """
        if limit:
            sql += f" LIMIT {limit}"
        events = await self._client.fetch_all(sql, session_id, agent_id, offset)
        for event in events:
            event["dst"] = json.loads(event["dst"]) if event["dst"] else []
            event["payload"] = json.loads(event["payload"]) if event["payload"] else {}
        return events

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        return await self._client.fetch_one(
            "SELECT * FROM tape_sessions WHERE session_id = ?", session_id
        )

    async def create_session(
        self,
        session_id: str,
        agent_id: str,
        tick_start: int | None = None,
        title: str | None = None,
    ) -> None:
        sql = """
            INSERT INTO tape_sessions (session_id, agent_id, tick_start, title)
            VALUES (?, ?, ?, ?)
            ON DUPLICATE KEY UPDATE
                agent_id = VALUES(agent_id),
                tick_start = VALUES(tick_start),
                title = VALUES(title)
        """
        await self._client.execute(sql, session_id, agent_id, tick_start, title)

    async def update_window_offset(self, session_id: str, offset: int, summary: str) -> None:
        sql = """
            UPDATE tape_sessions 
            SET window_offset = ?, summary = ?
            WHERE session_id = ?
        """
        await self._client.execute(sql, offset, summary, session_id)
