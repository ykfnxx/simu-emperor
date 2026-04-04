"""AgentRegistry — persistent registration and status tracking for Agents."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from simu_shared.models import AgentRegistration, AgentStatus
from simu_server.stores.database import Database

logger = logging.getLogger(__name__)


class AgentRegistry:
    """SQLite-backed Agent registration table."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def register(self, reg: AgentRegistration) -> None:
        await self._db.conn.execute(
            """
            INSERT OR REPLACE INTO agents
            (agent_id, display_name, status, process_pid, config_path, callback_url,
             registered_at, last_heartbeat, capabilities)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reg.agent_id,
                reg.display_name,
                reg.status.value,
                reg.process_pid,
                reg.config_path,
                reg.callback_url,
                reg.registered_at.isoformat(),
                reg.last_heartbeat.isoformat() if reg.last_heartbeat else None,
                json.dumps(reg.capabilities),
            ),
        )
        await self._db.conn.commit()

    async def get(self, agent_id: str) -> AgentRegistration | None:
        cursor = await self._db.conn.execute(
            "SELECT * FROM agents WHERE agent_id = ?", (agent_id,),
        )
        row = await cursor.fetchone()
        return self._row_to_reg(row) if row else None

    async def list_all(self) -> list[AgentRegistration]:
        cursor = await self._db.conn.execute("SELECT * FROM agents ORDER BY agent_id")
        return [self._row_to_reg(r) for r in await cursor.fetchall()]

    async def list_running(self) -> list[AgentRegistration]:
        cursor = await self._db.conn.execute(
            "SELECT * FROM agents WHERE status = ?", (AgentStatus.RUNNING.value,),
        )
        return [self._row_to_reg(r) for r in await cursor.fetchall()]

    async def update_status(self, agent_id: str, status: AgentStatus, pid: int | None = None) -> None:
        if pid is not None:
            await self._db.conn.execute(
                "UPDATE agents SET status = ?, process_pid = ? WHERE agent_id = ?",
                (status.value, pid, agent_id),
            )
        else:
            await self._db.conn.execute(
                "UPDATE agents SET status = ? WHERE agent_id = ?",
                (status.value, agent_id),
            )
        await self._db.conn.commit()

    async def update_heartbeat(self, agent_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        await self._db.conn.execute(
            "UPDATE agents SET last_heartbeat = ? WHERE agent_id = ?",
            (now, agent_id),
        )
        await self._db.conn.commit()

    async def update_capabilities(self, agent_id: str, capabilities: list[str]) -> None:
        await self._db.conn.execute(
            "UPDATE agents SET capabilities = ? WHERE agent_id = ?",
            (json.dumps(capabilities), agent_id),
        )
        await self._db.conn.commit()

    @staticmethod
    def _row_to_reg(row: tuple) -> AgentRegistration:
        return AgentRegistration(
            agent_id=row[0],
            display_name=row[1],
            status=AgentStatus(row[2]),
            process_pid=row[3],
            config_path=row[4],
            callback_url=row[5],
            registered_at=row[6],
            last_heartbeat=row[7],
            capabilities=json.loads(row[8]),
        )
