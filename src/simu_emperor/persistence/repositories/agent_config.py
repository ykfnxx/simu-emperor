import json
import logging
from typing import Any

from simu_emperor.persistence.client import SeekDBClient


logger = logging.getLogger(__name__)


class AgentConfigRepository:
    def __init__(self, client: SeekDBClient):
        self._client = client

    async def get(self, agent_id: str) -> dict[str, Any] | None:
        return await self._client.fetch_one(
            "SELECT * FROM agent_config WHERE agent_id = ? AND is_active = TRUE", agent_id
        )

    async def get_all(self) -> list[dict[str, Any]]:
        return await self._client.fetch_all("SELECT * FROM agent_config WHERE is_active = TRUE")

    async def save(
        self,
        agent_id: str,
        role_name: str,
        soul_text: str,
        skills: list[str] | None = None,
        permissions: dict[str, Any] | None = None,
    ) -> None:
        skills_json = json.dumps(skills) if skills else None
        permissions_json = json.dumps(permissions) if permissions else None

        await self._client.execute(
            """
            INSERT INTO agent_config (agent_id, role_name, soul_text, skills, permissions)
            VALUES (?, ?, ?, ?, ?)
            ON DUPLICATE KEY UPDATE
 role_name = VALUES(role_name),
                soul_text = VALUES(soul_text),
                skills = VALUES(skills),
                permissions = VALUES(permissions)
            """,
            agent_id,
            role_name,
            soul_text,
            skills_json,
            permissions_json,
        )

    async def update_permissions(self, agent_id: str, permissions: dict[str, Any]) -> None:
        await self._client.execute(
            "UPDATE agent_config SET permissions = ? WHERE agent_id = ?",
            json.dumps(permissions),
            agent_id,
        )
