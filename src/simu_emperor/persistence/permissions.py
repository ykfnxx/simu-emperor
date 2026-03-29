import logging
from typing import Any

from simu_emperor.persistence.client import SeekDBClient


logger = logging.getLogger(__name__)


class PermissionChecker:
    def __init__(self, client: SeekDBClient):
        self._client = client

    async def check_province_access(self, agent_id: str, province_id: str) -> bool:
        config = await self._client.fetch_one(
            "SELECT permissions FROM agent_config WHERE agent_id = ?", agent_id
        )
        if not config:
            return False

        permissions = config.get("permissions", {})
        provinces = permissions.get("provinces", [])

        return province_id in provinces or "*" in provinces

    async def check_tool_permission(self, agent_id: str, tool_name: str) -> bool:
        config = await self._client.fetch_one(
            "SELECT permissions FROM agent_config WHERE agent_id = ?", agent_id
        )
        if not config:
            return False

        permissions = config.get("permissions", {})
        tools = permissions.get("tools", [])

        return tool_name in tools or "*" in tools

    async def get_permissions(self, agent_id: str) -> dict[str, Any] | None:
        config = await self._client.fetch_one(
            "SELECT permissions FROM agent_config WHERE agent_id = ?", agent_id
        )
        if not config:
            return {}
        return config.get("permissions", {})
