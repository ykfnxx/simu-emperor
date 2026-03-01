"""Skill 注册表"""

from simu_emperor.agents.skills.models import Skill
from simu_emperor.event_bus.event_types import EventType


# 硬编码事件映射（设计文档 v2.0 要求）
DEFAULT_EVENT_SKILL_MAP: dict[str, str] = {
    EventType.COMMAND: "execute_command",
    EventType.QUERY: "query_data",
    EventType.CHAT: "chat",
    EventType.AGENT_MESSAGE: "receive_message",
    EventType.END_TURN: "prepare_turn",
    EventType.TURN_RESOLVED: "summarize_turn",
}


class SkillRegistry:
    """Skill 注册表

    管理所有可用的 Skill 实例，并提供事件到 Skill 的映射。

    Attributes:
        _skills: 已注册的 Skill 实例字典 {skill_name: Skill}
        _event_map: 事件类型到 Skill 名称的映射
    """

    def __init__(self) -> None:
        """初始化注册表"""
        self._skills: dict[str, Skill] = {}
        self._event_map = DEFAULT_EVENT_SKILL_MAP.copy()

    def get_skill_for_event(self, event_type: str) -> str | None:
        """获取事件对应的 Skill 名称

        Args:
            event_type: 事件类型字符串

        Returns:
            对应的 Skill 名称，如果事件类型未映射则返回 None
        """
        return self._event_map.get(event_type)

    def register_skill(self, skill: Skill) -> None:
        """注册 Skill 实例

        Args:
            skill: 要注册的 Skill 对象

        Note:
            如果已存在同名 Skill，将被覆盖
        """
        self._skills[skill.metadata.name] = skill

    def has_skill(self, skill_name: str) -> bool:
        """检查 Skill 是否已注册

        Args:
            skill_name: Skill 名称

        Returns:
            如果 Skill 已注册返回 True，否则返回 False
        """
        return skill_name in self._skills

    def get_skill(self, skill_name: str) -> Skill | None:
        """获取已注册的 Skill

        Args:
            skill_name: Skill 名称

        Returns:
            Skill 对象，如果不存在则返回 None
        """
        return self._skills.get(skill_name)

    def list_skills(self) -> list[str]:
        """列出所有已注册的 Skill 名称

        Returns:
            已注册 Skill 名称列表
        """
        return list(self._skills.keys())
