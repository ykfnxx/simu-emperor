"""Built-in tools for agent data access."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from simu_emperor.agents.context_builder import SkillScope
from simu_emperor.agents.tools.executor import PermissionDeniedError
from simu_emperor.agents.tools.models import Tool, ToolParameter
from simu_emperor.engine.models.base_data import NationalBaseData, ProvinceBaseData

logger = logging.getLogger(__name__)


# Tool definitions
QUERY_PROVINCE_DATA_TOOL = Tool(
    name="query_province_data",
    description="Query a specific field from a province's data. Use this to get detailed information about a province.",
    parameters=[
        ToolParameter(
            name="province_id",
            type="string",
            description="The ID of the province to query (e.g., 'zhili', 'shandong')",
            required=True,
        ),
        ToolParameter(
            name="field_path",
            type="string",
            description="The field path to query (e.g., 'population.total', 'agriculture.cultivated_land_mu', 'granary_stock')",
            required=True,
        ),
    ],
)

QUERY_NATIONAL_DATA_TOOL = Tool(
    name="query_national_data",
    description="Query national-level data fields like imperial treasury or tax modifiers.",
    parameters=[
        ToolParameter(
            name="field_name",
            type="string",
            description="The national field to query (e.g., 'imperial_treasury', 'national_tax_modifier', 'tribute_rate')",
            required=True,
        ),
    ],
)

LIST_PROVINCES_TOOL = Tool(
    name="list_provinces",
    description="List all province IDs available in the current game state.",
    parameters=[],
)


class BuiltinTools:
    """Built-in tools with permission checking."""

    def __init__(
        self,
        national_data: NationalBaseData,
        skill_scope: SkillScope,
    ) -> None:
        """Initialize builtin tools.

        Args:
            national_data: Current national game data
            skill_scope: Permission scope for the current skill
        """
        self._national_data = national_data
        self._skill_scope = skill_scope
        self._province_map: dict[str, ProvinceBaseData] = {
            p.province_id: p for p in national_data.provinces
        }

    def _check_field_permission(self, field_path: str) -> bool:
        """Check if a field path is within the skill scope."""
        if field_path in self._skill_scope.fields:
            return True
        # Check for wildcard matches
        for allowed in self._skill_scope.fields:
            if allowed.endswith(".*"):
                prefix = allowed[:-1]
                if field_path.startswith(prefix):
                    return True
        return False

    def _check_province_permission(self, province_id: str) -> bool:
        """Check if a province is within the skill scope."""
        if self._skill_scope.provinces == "all":
            return True
        if isinstance(self._skill_scope.provinces, list):
            return province_id in self._skill_scope.provinces
        return False

    def _check_national_permission(self, field_name: str) -> bool:
        """Check if a national field is within the skill scope."""
        return field_name in self._skill_scope.national

    def query_province_data(self, province_id: str, field_path: str) -> dict[str, Any]:
        """Query a specific field from a province's data.

        Args:
            province_id: The ID of the province
            field_path: The field path (e.g., 'population.total')

        Returns:
            Serialized field value

        Raises:
            PermissionDeniedError: If access is not permitted
        """
        # Check province permission
        if not self._check_province_permission(province_id):
            raise PermissionDeniedError(
                f"Access to province '{province_id}' not permitted"
            )

        # Check field permission
        if not self._check_field_permission(field_path):
            raise PermissionDeniedError(
                f"Access to field '{field_path}' not permitted"
            )

        # Get province
        province = self._province_map.get(province_id)
        if province is None:
            return {"error": f"Province '{province_id}' not found"}

        # Extract field value
        value = self._extract_field(province, field_path)
        return self._serialize_result(value)

    def query_national_data(self, field_name: str) -> dict[str, Any]:
        """Query a national-level field.

        Args:
            field_name: The national field name

        Returns:
            Serialized field value

        Raises:
            PermissionDeniedError: If access is not permitted
        """
        # Check permission
        if not self._check_national_permission(field_name):
            raise PermissionDeniedError(
                f"Access to national field '{field_name}' not permitted"
            )

        # Get field value
        value = getattr(self._national_data, field_name, None)
        if value is None:
            return {"error": f"National field '{field_name}' not found"}

        return self._serialize_result(value)

    def list_provinces(self) -> dict[str, Any]:
        """List all province IDs, filtered by permission.

        Returns:
            Dict with list of accessible province IDs
        """
        if self._skill_scope.provinces == "all":
            ids = list(self._province_map.keys())
        elif isinstance(self._skill_scope.provinces, list):
            ids = [pid for pid in self._skill_scope.provinces if pid in self._province_map]
        else:
            ids = []

        return {"province_ids": ids}

    def _extract_field(self, province: ProvinceBaseData, field_path: str) -> Any:
        """Extract a field value from province data.

        Args:
            province: Province data object
            field_path: Dot-notation field path

        Returns:
            Field value or None if not found
        """
        if "." in field_path:
            subsystem, field_name = field_path.split(".", 1)
            sub_obj = getattr(province, subsystem, None)
            if sub_obj is None:
                return None
            return getattr(sub_obj, field_name, None)
        else:
            return getattr(province, field_path, None)

    def _serialize_result(self, value: Any) -> dict[str, Any]:
        """Serialize a result value to JSON-compatible format."""
        if hasattr(value, "model_dump"):
            return {"value": value.model_dump(mode="json")}
        if isinstance(value, (list, tuple)) and value and hasattr(value[0], "model_dump"):
            return {"value": [item.model_dump(mode="json") for item in value]}
        if isinstance(value, Decimal):
            return {"value": str(value)}
        return {"value": value}

    def get_tools_and_handlers(
        self,
    ) -> list[tuple[Tool, Any]]:
        """Get all builtin tools with their handlers.

        Returns:
            List of (Tool, handler) tuples ready for registration
        """
        return [
            (QUERY_PROVINCE_DATA_TOOL, self.query_province_data),
            (QUERY_NATIONAL_DATA_TOOL, self.query_national_data),
            (LIST_PROVINCES_TOOL, self.list_provinces),
        ]
