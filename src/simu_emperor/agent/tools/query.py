"""
Query tool handlers for V5 Agent

Query tools return data to the LLM for function calling.
"""

import json
import logging
from pathlib import Path
from typing import Any

from simu_emperor.mq.event import Event
from simu_emperor.persistence.repositories.game_state import GameStateRepository
from simu_emperor.persistence.repositories.agent_config import AgentConfigRepository


logger = logging.getLogger(__name__)


class QueryTools:
    """Query tool handlers - return data to LLM"""

    def __init__(
        self,
        agent_id: str,
        game_state_repo: GameStateRepository,
        agent_config_repo: AgentConfigRepository,
        data_dir: Path | None = None,
    ):
        self.agent_id = agent_id
        self.game_state_repo = game_state_repo
        self.agent_config_repo = agent_config_repo
        self.data_dir = data_dir or Path("data")

    async def query_province_data(self, args: dict, event: Event) -> str:
        province_id = args.get("province_id")
        field_name = args.get("field_path")

        if not province_id:
            return "❌ 请提供 province_id 参数"

        try:
            province = await self.game_state_repo.get_province(province_id)

            if not province:
                return f"❌ 未找到省份 {province_id}"

            if field_name:
                valid_fields = {
                    "population",
                    "treasury",
                    "tax_rate",
                    "stability",
                    "production_value",
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

                value = province.get(field_name, "N/A")
                logger.info(f"Agent {self.agent_id} queried {province_id}.{field_name} = {value}")
                return f"查询结果：{province_id} 的 {field_name} = {value}"

            return f"省份 {province_id} 数据：\n" + json.dumps(
                province, ensure_ascii=False, indent=2
            )

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error querying province data: {e}")
            return f"❌ 查询失败：{str(e)}"

    async def query_national_data(self, args: dict, event: Event) -> str:
        field_name = args.get("field_name")

        try:
            treasury = await self.game_state_repo.get_national_treasury()
            tick = await self.game_state_repo.get_tick()

            national_data = {
                "tick": tick,
                "total_silver": treasury.get("total_silver", 0) if treasury else 0,
                "monthly_income": treasury.get("monthly_income", 0) if treasury else 0,
                "monthly_expense": treasury.get("monthly_expense", 0) if treasury else 0,
                "base_tax_rate": treasury.get("base_tax_rate", 0.1) if treasury else 0.1,
            }

            if field_name:
                valid_fields = set(national_data.keys())
                if field_name not in valid_fields:
                    return f"❌ 无效字段: {field_name}。可用字段: {', '.join(sorted(valid_fields))}"

                value = national_data.get(field_name, "N/A")
                logger.info(f"Agent {self.agent_id} queried national.{field_name} = {value}")
                return f"查询结果：国家级 {field_name} = {value}"

            return "国家级数据：\n" + json.dumps(national_data, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error querying national data: {e}")
            return f"❌ 查询失败：{str(e)}"

    async def list_provinces(self, args: dict, event: Event) -> str:
        try:
            provinces_data = await self.game_state_repo.get_national_treasury()
            default_provinces = ["zhili", "jiangsu", "zhejiang", "guangdong", "sichuan"]

            results = []
            for province_id in default_provinces:
                province = await self.game_state_repo.get_province(province_id)
                if province:
                    results.append(
                        f"- {province_id}: {province.get('name', province_id)} (人口: {province.get('population', 0)})"
                    )

            if not results:
                return "❌ 未找到任何省份"

            logger.info(f"Agent {self.agent_id} listed provinces")
            return "可用省份：\n" + "\n".join(results)

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error listing provinces: {e}")
            return f"❌ 查询失败：{str(e)}"

    async def list_agents(self, args: dict, event: Event) -> str:
        try:
            agents = await self.agent_config_repo.get_all()

            if not agents:
                return "❌ 未找到任何 Agent"

            result_lines = ["当前活跃 Agent："]
            for agent in agents:
                agent_id = agent.get("agent_id", "unknown")
                role_name = agent.get("role_name", "未知职位")
                result_lines.append(f"- {role_name} (ID: {agent_id})")

            logger.info(f"Agent {self.agent_id} listed agents")
            return "\n".join(result_lines)

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error listing agents: {e}")
            return f"❌ 查询失败：{str(e)}"

    async def get_agent_info(self, args: dict, event: Event) -> str:
        target_agent_id = args.get("agent_id")

        if not target_agent_id:
            return "❌ 请提供 agent_id 参数"

        try:
            agent = await self.agent_config_repo.get(target_agent_id)

            if not agent:
                return f"❌ 未找到 Agent {target_agent_id}"

            role_name = agent.get("role_name", "未知职位")
            soul_text = agent.get("soul_text", "暂无描述")[:200]
            skills = agent.get("skills", [])

            result = f"## {role_name} (ID: {target_agent_id})\n"
            result += f"**描述**: {soul_text}...\n"
            if skills:
                result += f"**技能**: {', '.join(skills)}\n"

            return result

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error getting agent info: {e}")
            return f"❌ 查询失败：{str(e)}"
