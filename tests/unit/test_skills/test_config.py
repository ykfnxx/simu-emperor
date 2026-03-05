"""测试 SkillConfig 配置类"""

import pytest

from simu_emperor.agents.skills.config import (
    DEFAULT_SKILL_CONFIG,
    SkillConfig,
)


class TestSkillConfig:
    """测试 SkillConfig 类"""

    def test_default_config(self):
        """测试默认配置常量的值"""
        assert DEFAULT_SKILL_CONFIG["enable_dynamic_loading"] is True
        assert DEFAULT_SKILL_CONFIG["allow_fallback_to_hardcoded"] is True
        assert DEFAULT_SKILL_CONFIG["directories"] == ["data/skills"]
        assert DEFAULT_SKILL_CONFIG["hot_reload"]["enabled"] is True
        assert DEFAULT_SKILL_CONFIG["hot_reload"]["method"] == "watchdog"
        assert DEFAULT_SKILL_CONFIG["cache"]["size"] == 50

    def test_skill_config_from_dict(self):
        """测试从字典创建 SkillConfig"""
        data = {
            "enable_dynamic_loading": False,
            "allow_fallback_to_hardcoded": False,
            "directories": ["custom/skills", "backup/skills"],
            "hot_reload": {
                "enabled": False,
                "method": "polling",
            },
            "cache": {
                "size": 100,
            },
        }

        config = SkillConfig.from_dict(data)

        assert config.enable_dynamic_loading is False
        assert config.allow_fallback_to_hardcoded is False
        assert config.directories == ["custom/skills", "backup/skills"]
        assert config.hot_reload_enabled is False
        assert config.hot_reload_method == "polling"
        assert config.cache_size == 100

    def test_skill_config_empty_dict(self):
        """测试空字典使用默认值"""
        config = SkillConfig.from_dict({})

        assert config.enable_dynamic_loading is True
        assert config.allow_fallback_to_hardcoded is True
        assert config.directories == ["data/skills"]
        assert config.hot_reload_enabled is True
        assert config.hot_reload_method == "watchdog"
        assert config.cache_size == 50

    def test_skill_config_partial_dict(self):
        """测试部分字典配置"""
        data = {
            "directories": ["my/skills"],
            "hot_reload": {
                "method": "custom",
            },
        }

        config = SkillConfig.from_dict(data)

        # 修改的字段
        assert config.directories == ["my/skills"]
        assert config.hot_reload_method == "custom"

        # 默认值
        assert config.enable_dynamic_loading is True
        assert config.allow_fallback_to_hardcoded is True
        assert config.hot_reload_enabled is True
        assert config.cache_size == 50

    def test_skill_config_default_constructor(self):
        """测试直接使用构造函数创建"""
        config = SkillConfig()

        assert config.enable_dynamic_loading is True
        assert config.allow_fallback_to_hardcoded is True
        assert config.directories == ["data/skills"]
        assert config.hot_reload_enabled is True
        assert config.hot_reload_method == "watchdog"
        assert config.cache_size == 50

    def test_skill_config_custom_constructor(self):
        """测试自定义参数创建"""
        config = SkillConfig(
            enable_dynamic_loading=False,
            directories=["test/skills"],
            cache_size=200,
        )

        assert config.enable_dynamic_loading is False
        assert config.allow_fallback_to_hardcoded is True  # 默认值
        assert config.directories == ["test/skills"]
        assert config.hot_reload_enabled is True  # 默认值
        assert config.hot_reload_method == "watchdog"  # 默认值
        assert config.cache_size == 200

    def test_skill_config_immutability(self):
        """测试 dataclass 不可变性"""
        config = SkillConfig()

        # 尝试修改应该抛出异常
        with pytest.raises(Exception):  # FrozenInstanceError
            config.enable_dynamic_loading = False

    def test_skill_config_nested_hot_reload_empty(self):
        """测试 hot_reload 字典为空时使用默认值"""
        config = SkillConfig.from_dict({"hot_reload": {}})

        assert config.hot_reload_enabled is True
        assert config.hot_reload_method == "watchdog"

    def test_skill_config_nested_cache_empty(self):
        """测试 cache 字典为空时使用默认值"""
        config = SkillConfig.from_dict({"cache": {}})

        assert config.cache_size == 50

    def test_skill_config_missing_nested_keys(self):
        """测试嵌套字典缺少某些键"""
        config = SkillConfig.from_dict(
            {
                "hot_reload": {"enabled": False},
                "cache": {"size": 75},
            }
        )

        assert config.hot_reload_enabled is False
        assert config.hot_reload_method == "watchdog"  # 默认值
        assert config.cache_size == 75
