"""角色枚举（系统层面标识 agent 类型）。"""

from enum import StrEnum


class AgentRole(StrEnum):
    """Agent 角色枚举，值必须匹配 data/default_agents/ 目录名。"""

    MINISTER_OF_REVENUE = "minister_of_revenue"
    GOVERNOR_ZHILI = "governor_zhili"
