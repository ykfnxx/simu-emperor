"""Skill 配置"""

from dataclasses import dataclass, field


DEFAULT_SKILL_CONFIG = {
    "enable_dynamic_loading": True,
    "allow_fallback_to_hardcoded": True,
    "directories": ["data/skills"],
    "hot_reload": {
        "enabled": True,
        "method": "watchdog",
    },
    "cache": {
        "size": 50,
    },
}


@dataclass(frozen=True)
class SkillConfig:
    """Skill 配置

    Attributes:
        enable_dynamic_loading: 是否启用动态加载
        allow_fallback_to_hardcoded: 是否允许回退到硬编码
        directories: skill 目录列表
        hot_reload_enabled: 是否启用热重载
        hot_reload_method: 热重载方法
        cache_size: 缓存大小
    """
    enable_dynamic_loading: bool = True
    allow_fallback_to_hardcoded: bool = True
    directories: list[str] = field(default_factory=lambda: ["data/skills"])
    hot_reload_enabled: bool = True
    hot_reload_method: str = "watchdog"
    cache_size: int = 50

    @classmethod
    def from_dict(cls, data: dict) -> "SkillConfig":
        """从字典创建 SkillConfig

        Args:
            data: 配置字典，可能包含嵌套的 hot_reload 和 cache

        Returns:
            SkillConfig 实例
        """
        hot_reload = data.get("hot_reload", {})
        cache = data.get("cache", {})

        return cls(
            enable_dynamic_loading=data.get("enable_dynamic_loading", True),
            allow_fallback_to_hardcoded=data.get("allow_fallback_to_hardcoded", True),
            directories=data.get("directories", ["data/skills"]),
            hot_reload_enabled=hot_reload.get("enabled", True),
            hot_reload_method=hot_reload.get("method", "watchdog"),
            cache_size=cache.get("size", 50),
        )
