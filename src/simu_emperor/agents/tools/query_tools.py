"""Query tool handlers for Agent

These handlers return data to the LLM for function calling.
"""

import logging
from pathlib import Path
from typing import Any

from simu_emperor.event_bus.event import Event
from simu_emperor.agents.tools.role_map_parser import RoleMapParser


logger = logging.getLogger(__name__)


class QueryTools:
    """Query tool handlers - return data to LLM

    This class contains all query-type tool handlers that retrieve
    and return data to the LLM during function calling.

    Query functions:
    - query_province_data: Query province-specific data
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
    ):
        """
        Initialize QueryTools

        Args:
            agent_id: Agent unique identifier
            repository: GameRepository for data queries
            data_dir: Data directory path
        """
        self.agent_id = agent_id
        self.repository = repository
        self.data_dir = data_dir
        self._role_map_parser = RoleMapParser(data_dir)

    async def query_province_data(self, args: dict, event: Event) -> str:
        """Query province-specific data"""
        if not self.repository:
            return "❌ Repository not available"

        province_id = args.get("province_id")
        field_path = args.get("field_path")

        try:
            # 加载状态
            state = await self.repository.load_state()

            # 解析 field_path（如 "population.total"）
            parts = field_path.split(".")

            # 获取省份数据
            provinces_dict = {p["province_id"]: p for p in state.get("provinces", [])}
            if province_id not in provinces_dict:
                return f"❌ 未找到省份 {province_id}"

            province_data = provinces_dict[province_id]

            # 导航到目标字段
            value = province_data
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                elif isinstance(value, list) and part.isdigit():
                    value = value[int(part)]
                else:
                    return f"❌ 无法访问字段 {field_path}"

            logger.info(f"Agent {self.agent_id} queried {province_id}.{field_path} = {value}")

            # 返回查询结果（给LLM）
            return f"查询结果：{province_id} 的 {field_path} = {value}"

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error querying province data: {e}")
            return f"❌ 查询失败：{str(e)}"

    async def query_national_data(self, args: dict, event: Event) -> str:
        """Query national-level data"""
        if not self.repository:
            return "❌ Repository not available"

        field_name = args.get("field_name")

        try:
            # 加载状态
            state = await self.repository.load_state()

            # 获取字段值
            value = state.get(field_name)

            logger.info(f"Agent {self.agent_id} queried national.{field_name} = {value}")

            # 返回查询结果（给LLM）
            return f"查询结果：国家级 {field_name} = {value}"

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error querying national data: {e}")
            return f"❌ 查询失败：{str(e)}"

    async def list_provinces(self, args: dict, event: Event) -> str:
        """List all available provinces"""
        if not self.repository:
            return "❌ Repository not available"

        try:
            # 加载状态
            state = await self.repository.load_state()

            # 获取省份列表
            provinces = state.get("provinces", [])
            province_ids = [p.get("province_id") for p in provinces]

            logger.info(f"Agent {self.agent_id} listed provinces: {province_ids}")

            # 返回结果（给LLM）
            return f"可用省份：{', '.join(province_ids)}"

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error listing provinces: {e}")
            return f"❌ 查询失败：{str(e)}"

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

        logger.info(
            f"Agent {self.agent_id} listed agents: {[a['agent_id'] for a in agents]}"
        )
        return "\n".join(result_lines)

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

        return f"{title} {name}：{duty}"
