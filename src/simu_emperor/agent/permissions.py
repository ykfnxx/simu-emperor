from typing import Any

from simu_emperor.persistence.permissions import PermissionChecker as BasePermissionChecker


class PermissionChecker:
    def __init__(self, agent_id: str, base_checker: BasePermissionChecker):
        self._agent_id = agent_id
        self._base = base_checker

    async def check_province_access(self, province_id: str) -> bool:
        return await self._base.check_province_access(self._agent_id, province_id)

    async def check_tool_permission(self, tool_name: str) -> bool:
        return await self._base.check_tool_permission(self._agent_id, tool_name)

    async def get_permissions(self) -> dict[str, Any] | None:
        return await self._base.get_permissions(self._agent_id)

    async def has_tool_permission(self, tool_name: str, resource_id: str | None = None) -> bool:
        has_tool = await self.check_tool_permission(tool_name)
        if not has_tool:
            return False

        if resource_id and tool_name == "query_province_data":
            return await self.check_province_access(resource_id)

        return True
