"""role_map.md 文件解析器"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class RoleMapParser:
    """role_map.md 文件解析器

    负责解析 data/role_map.md 文件，提取官员信息。
    使用缓存机制，避免重复解析。
    """

    def __init__(self, data_dir: Path):
        """初始化解析器"""
        self.data_dir = data_dir
        self._role_map_path: Optional[Path] = None
        self._cache: Optional[list[dict]] = None

    def _find_role_map_path(self) -> Optional[Path]:
        """查找 role_map.md 文件"""
        possible_paths = [
            self.data_dir / "role_map.md",  # Prioritize data_dir from constructor
            self.data_dir / "../../role_map.md",
            Path("data/role_map.md"),
            Path.cwd() / "data" / "role_map.md",
        ]

        for path in possible_paths:
            if path.exists():
                logger.debug(f"Found role_map.md at: {path}")
                return path

        logger.warning("role_map.md not found in any expected location")
        return None

    def parse(self) -> list[dict]:
        """解析 role_map.md，返回官员列表"""
        if self._cache is not None:
            return self._cache

        if self._role_map_path is None:
            self._role_map_path = self._find_role_map_path()

        if self._role_map_path is None:
            return []

        try:
            content = self._role_map_path.read_text(encoding="utf-8")
            agents_info = self._parse_markdown(content)
            self._cache = agents_info
            return agents_info

        except Exception as e:
            logger.error(f"Failed to parse role_map.md: {e}", exc_info=True)
            return []

    def _parse_markdown(self, content: str) -> list[dict]:
        """解析 Markdown 内容"""
        agents_info = []
        current_section = None

        for line in content.split("\n"):
            line = line.strip()

            if line.startswith("## "):
                if current_section:
                    agents_info.append(current_section)

                title_line = line[3:].strip()
                if "(" in title_line and ")" in title_line:
                    title = title_line[: title_line.index("(")].strip()
                    agent_id = title_line[title_line.index("(") + 1 : title_line.index(")")].strip()
                    current_section = {
                        "title": title,
                        "agent_id": agent_id,
                        "name": None,
                        "duty": None,
                        "commands": None,
                    }

            elif line.startswith("- 姓名：") or line.startswith("- 姓名:"):
                if current_section:
                    current_section["name"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()

            elif line.startswith("- 职责：") or line.startswith("- 职责:"):
                if current_section:
                    current_section["duty"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()

            elif line.startswith("- 适用命令：") or line.startswith("- 适用命令:"):
                if current_section:
                    current_section["commands"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()

        if current_section:
            agents_info.append(current_section)

        logger.debug(f"Parsed {len(agents_info)} agents from role_map.md")
        return agents_info

    def get_agent(self, agent_id: str) -> Optional[dict]:
        """获取特定官员信息"""
        agents = self.parse()
        for agent in agents:
            if agent["agent_id"] == agent_id:
                return agent
        return None

    def clear_cache(self) -> None:
        """清除缓存"""
        self._cache = None
