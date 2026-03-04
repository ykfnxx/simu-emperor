"""Query tool handlers for Agent

These handlers return data to the LLM for function calling.
"""

import logging
from pathlib import Path
from typing import Any

from simu_emperor.event_bus.event import Event


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
        # role_map.md 在项目根目录的 data/ 下，不是在 agent 目录下
        # 尝试多个可能的路径
        possible_paths = [
            Path("data/role_map.md"),  # 相对于项目根目录
            Path(self.data_dir) / "../../role_map.md",  # 相对于 agent 目录向上 3 级
            Path.cwd() / "data" / "role_map.md",  # 绝对路径（基于当前工作目录）
        ]

        role_map_path = None
        for path in possible_paths:
            if path.exists():
                role_map_path = path
                break

        if not role_map_path:
            return "❌ 无法查询官员信息：role_map.md 文件不存在"

        try:
            # 读取并解析 role_map.md
            with open(role_map_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 解析每个官员的信息
            agents_info = []
            current_section = None

            for line in content.split("\n"):
                line = line.strip()

                # 匹配 ## 职位名称 (agent_id)
                if line.startswith("## "):
                    if current_section:
                        agents_info.append(current_section)
                    # 提取职位和 agent_id
                    title_line = line[3:].strip()
                    if "(" in title_line and ")" in title_line:
                        title = title_line[: title_line.index("(")].strip()
                        agent_id = title_line[
                            title_line.index("(") + 1 : title_line.index(")")
                        ].strip()
                        current_section = {
                            "title": title,
                            "agent_id": agent_id,
                            "name": None,
                            "duty": None,
                        }

                # 匹配 - 姓名：xxx
                elif line.startswith("- 姓名：") or line.startswith("- 姓名:"):
                    if current_section:
                        current_section["name"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()

                # 匹配 - 职责：xxx
                elif line.startswith("- 职责：") or line.startswith("- 职责:"):
                    if current_section:
                        current_section["duty"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()

            # 添加最后一个 section
            if current_section:
                agents_info.append(current_section)

            # 构建返回结果
            if agents_info:
                result_lines = ["朝廷现任官员："]
                for agent in agents_info:
                    name = agent.get("name", "未知")
                    title = agent.get("title", "未知职位")
                    agent_id = agent.get("agent_id", "unknown")
                    duty = agent.get("duty", "暂无职责描述")

                    result_lines.append(f"- {title} {name}（ID: {agent_id}）: {duty}")

                logger.info(
                    f"Agent {self.agent_id} listed agents from role_map.md: {[a['agent_id'] for a in agents_info]}"
                )
                return "\n".join(result_lines)
            else:
                return "❌ role_map.md 解析失败：未找到任何官员信息"

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error listing agents: {e}", exc_info=True)
            return f"❌ 查询官员列表失败：{str(e)}"

    async def get_agent_info(self, args: dict, event: Event) -> str:
        """Get detailed information about a specific agent"""
        agent_id = args.get("agent_id")

        if not agent_id:
            return "❌ 请提供 agent_id 参数"

        # role_map.md 在项目根目录的 data/ 下，不是在 agent 目录下
        # 尝试多个可能的路径
        possible_paths = [
            Path("data/role_map.md"),  # 相对于项目根目录
            Path(self.data_dir) / "../../role_map.md",  # 相对于 agent 目录向上 3 级
            Path.cwd() / "data" / "role_map.md",  # 绝对路径（基于当前工作目录）
        ]

        role_map_path = None
        for path in possible_paths:
            if path.exists():
                role_map_path = path
                break

        if not role_map_path:
            return "❌ 无法查询官员信息：role_map.md 文件不存在"

        try:
            # 读取并解析 role_map.md
            with open(role_map_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 查找对应的 agent section
            current_section = None
            result_info = []

            for line in content.split("\n"):
                line = line.strip()

                # 匹配 ## 职位名称 (agent_id)
                if line.startswith("## "):
                    # 如果已经找到了目标 section，返回结果
                    if current_section and current_section.get("agent_id") == agent_id:
                        break

                    # 开始新的 section
                    title_line = line[3:].strip()
                    if "(" in title_line and ")" in title_line:
                        title = title_line[: title_line.index("(")].strip()
                        section_agent_id = title_line[
                            title_line.index("(") + 1 : title_line.index(")")
                        ].strip()
                        current_section = {"title": title, "agent_id": section_agent_id, "info": []}

                # 如果在目标 section 中，收集信息
                elif current_section and current_section.get("agent_id") == agent_id:
                    if line.startswith("-"):
                        result_info.append(line)
                    elif result_info:  # 遇到空行或新 section
                        break

            # 构建返回结果
            if result_info and current_section:
                title = current_section.get("title", "")
                name = next(
                    (
                        line.split("：", 1)[-1].split(":", 1)[-1].strip()
                        for line in result_info
                        if line.startswith("- 姓名") or line.startswith("- 姓名:")
                    ),
                    "",
                )

                result = f"【{title} - {name}】\n\n" + "\n".join(result_info)
                logger.info(f"Agent {self.agent_id} retrieved info for {agent_id} from role_map.md")
                return result
            else:
                return f"❌ 未找到官员 {agent_id} 的信息，请检查 role_map.md 中是否包含该职位"

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error getting agent info: {e}", exc_info=True)
            return f"❌ 查询官员信息失败：{str(e)}"
