"""Query tool handlers for Agent

These handlers return data to the LLM for function calling.

V4: Updated to work with simplified NationData/ProvinceData models.
"""

import logging
from pathlib import Path
from typing import Any

from simu_emperor.event_bus.event import Event
from simu_emperor.agents.tools.registry import ToolProvider, tool
from simu_emperor.agents.tools.role_map_parser import RoleMapParser


logger = logging.getLogger(__name__)


class QueryTools(ToolProvider):
    """Query tool handlers - return data to LLM

    This class contains all query-type tool handlers that retrieve
    and return data to the LLM during function calling.

    Query functions:
    - query_province_data: Query province-specific data (V4: 4 core fields)
    - query_national_data: Query national-level data
    - list_provinces: List all available provinces
    - list_agents: List all active agents from role_map.md
    - get_agent_info: Get detailed information about a specific agent
    """

    def __init__(
        self,
        agent_id: str,
        repository: Any,
        data_dir: Path,
        engine: Any = None,
    ):
        """
        Initialize QueryTools

        Args:
            agent_id: Agent unique identifier
            repository: GameRepository for data queries
            data_dir: Data directory path
            engine: Engine instance for incident queries (optional)
        """
        self.agent_id = agent_id
        self.repository = repository
        self.data_dir = data_dir
        self.engine = engine
        self._role_map_parser = RoleMapParser(data_dir)

    @tool(
        name="query_province_data",
        description="查询某个省份的特定数据字段",
        parameters={
            "type": "object",
            "properties": {
                "province_id": {
                    "type": "string",
                    "enum": [
                        "zhili",
                        "jiangnan",
                        "zhejiang",
                        "fujian",
                        "huguang",
                        "sichuan",
                        "shaanxi",
                        "shandong",
                        "jiangxi",
                    ],
                },
                "field_path": {
                    "type": "string",
                    "enum": [
                        "production_value",
                        "population",
                        "fixed_expenditure",
                        "stockpile",
                        "tax_modifier",
                        "name",
                        "province_id",
                        "base_production_growth",
                        "base_population_growth",
                    ],
                },
            },
            "required": ["province_id", "field_path"],
        },
        category="query",
    )
    async def query_province_data(self, args: dict, event: Event) -> str:
        """Query province-specific data (V4: 4 core fields)"""
        if not self.repository:
            return "❌ Repository not available"

        province_id = args.get("province_id")
        field_name = args.get("field_path")  # Renamed from field_path for V4

        try:
            # V4: 使用 load_nation_data() 获取 NationData 对象
            nation = await self.repository.load_nation_data()

            if province_id not in nation.provinces:
                return f"❌ 未找到省份 {province_id}"

            province = nation.provinces[province_id]

            # V4: 直接访问4个核心字段
            valid_fields = {
                "production_value",
                "population",
                "fixed_expenditure",
                "stockpile",
                "name",
                "province_id",
                "base_production_growth",
                "base_population_growth",
                "tax_modifier",
            }

            if field_name not in valid_fields:
                return f"❌ 无效字段: {field_name}。可用字段: {', '.join(sorted(valid_fields))}"

            value = getattr(province, field_name)

            logger.info(f"Agent {self.agent_id} queried {province_id}.{field_name} = {value}")

            # 返回查询结果（给LLM）
            return f"查询结果：{province_id} 的 {field_name} = {value}"

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error querying province data: {e}")
            return f"❌ 查询失败：{str(e)}"

    @tool(
        name="query_national_data",
        description="查询国家级数据",
        parameters={
            "type": "object",
            "properties": {
                "field_name": {
                    "type": "string",
                    "enum": [
                        "imperial_treasury",
                        "turn",
                        "base_tax_rate",
                        "tribute_rate",
                        "fixed_expenditure",
                    ],
                }
            },
            "required": ["field_name"],
        },
        category="query",
    )
    async def query_national_data(self, args: dict, event: Event) -> str:
        """Query national-level data"""
        if not self.repository:
            return "❌ Repository not available"

        field_name = args.get("field_name")

        try:
            # V4: 使用 load_nation_data() 获取 NationData 对象
            nation = await self.repository.load_nation_data()

            # V4: 直接访问 NationData 字段
            valid_fields = {
                "turn",
                "base_tax_rate",
                "tribute_rate",
                "fixed_expenditure",
                "imperial_treasury",
            }

            if field_name not in valid_fields:
                return f"❌ 无效字段: {field_name}。可用字段: {', '.join(sorted(valid_fields))}"

            value = getattr(nation, field_name)

            logger.info(f"Agent {self.agent_id} queried national.{field_name} = {value}")

            # 返回查询结果（给LLM）
            return f"查询结果：国家级 {field_name} = {value}"

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error querying national data: {e}")
            return f"❌ 查询失败：{str(e)}"

    @tool(
        name="list_provinces",
        description="列出所有可访问的省份 ID",
        parameters={"type": "object", "properties": {}, "required": []},
        category="query",
    )
    async def list_provinces(self, args: dict, event: Event) -> str:
        """List all available provinces"""
        if not self.repository:
            return "❌ Repository not available"

        try:
            # V4: 使用 load_nation_data() 获取 NationData 对象
            nation = await self.repository.load_nation_data()

            # 获取省份列表
            province_ids = list(nation.provinces.keys())

            logger.info(f"Agent {self.agent_id} listed provinces: {province_ids}")

            # 返回结果（给LLM）
            return f"可用省份：{', '.join(province_ids)}"

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error listing provinces: {e}")
            return f"❌ 查询失败：{str(e)}"

    @tool(
        name="list_agents",
        description="列出所有活跃的官员",
        parameters={"type": "object", "properties": {}, "required": []},
        category="query",
    )
    async def list_agents(self, args: dict, event: Event) -> str:
        """List all active agents from role_map.md"""
        agents = self._role_map_parser.parse()

        if not agents:
            return "❌ 无法查询官员信息：role_map.md 文件不存在或解析失败"

        result_lines = ["朝廷现任官员："]
        for agent in agents:
            name = agent.get("name", "未知")
            title = agent.get("title", "未知职位")
            agent_id = agent.get("agent_id", "unknown")
            duty = agent.get("duty", "暂无职责描述")

            result_lines.append(f"- {title} {name}（ID: {agent_id}）: {duty}")

        logger.info(f"Agent {self.agent_id} listed agents: {[a['agent_id'] for a in agents]}")
        return "\n".join(result_lines)

    @tool(
        name="get_agent_info",
        description="获取某个官员的详细信息",
        parameters={
            "type": "object",
            "properties": {"agent_id": {"type": "string"}},
            "required": ["agent_id"],
        },
        category="query",
    )
    async def get_agent_info(self, args: dict, event: Event) -> str:
        """Get detailed information about a specific agent"""
        agent_id = args.get("agent_id")

        if not agent_id:
            return "❌ 请提供 agent_id 参数"

        agent = self._role_map_parser.get_agent(agent_id)

        if not agent:
            return f"❌ 未找到官员 {agent_id}"

        name = agent.get("name", "未知")
        title = agent.get("title", "未知职位")
        duty = agent.get("duty", "暂无职责描述")
        commands = agent.get("commands", "暂无适用命令")

        return f"## {title} {name}\n**职责**: {duty}\n**适用命令**: {commands}"

    @tool(
        name="query_incidents",
        description="查询当前活跃的游戏事件（旱灾、丰收等），可按省份或来源过滤",
        parameters={
            "type": "object",
            "properties": {
                "filter_province": {
                    "type": "string",
                    "description": "按省份 ID 过滤（可选）",
                },
                "filter_source": {
                    "type": "string",
                    "description": "按来源过滤（可选）",
                },
            },
            "required": [],
        },
        category="query",
    )
    async def query_incidents(self, args: dict, event: Event) -> str:
        """Query active incidents, optionally filtered by province or source."""
        if not self.engine:
            return "❌ Engine not available"

        filter_province = args.get("filter_province")
        filter_source = args.get("filter_source")

        incidents = self.engine.get_active_incidents()

        if filter_province:
            incidents = [
                inc
                for inc in incidents
                if any(f"provinces.{filter_province}." in eff.target_path for eff in inc.effects)
            ]

        if filter_source:
            incidents = [inc for inc in incidents if inc.source == filter_source]

        if not incidents:
            return "当前没有活跃的事件。"

        lines = [f"当前活跃事件（共 {len(incidents)} 个）："]
        for inc in incidents:
            effects_desc = []
            for eff in inc.effects:
                if eff.add is not None:
                    effects_desc.append(f"{eff.target_path} +{eff.add}")
                elif eff.factor is not None:
                    pct = float(eff.factor) * 100
                    effects_desc.append(f"{eff.target_path} {pct:+.1f}%")
            lines.append(
                f"- **{inc.title}**（剩余 {inc.remaining_ticks} tick）: {inc.description}\n"
                f"  效果: {', '.join(effects_desc)}\n"
                f"  来源: {inc.source}"
            )

        logger.info(f"Agent {self.agent_id} queried incidents: {len(incidents)} results")
        return "\n".join(lines)
