"""测试 SkillRegistry"""

from simu_emperor.agents.skills.models import Skill, SkillMetadata
from simu_emperor.agents.skills.registry import DEFAULT_EVENT_SKILL_MAP, SkillRegistry
from simu_emperor.event_bus.event_types import EventType


class TestDefaultEventSkillMap:
    """测试默认事件映射"""

    def test_default_event_skill_map(self):
        """验证默认事件映射正确性"""
        # 验证映射包含所有预期的事件类型
        assert EventType.COMMAND in DEFAULT_EVENT_SKILL_MAP
        assert EventType.QUERY in DEFAULT_EVENT_SKILL_MAP
        assert EventType.CHAT in DEFAULT_EVENT_SKILL_MAP
        assert EventType.AGENT_MESSAGE in DEFAULT_EVENT_SKILL_MAP
        assert EventType.END_TURN in DEFAULT_EVENT_SKILL_MAP
        assert EventType.TURN_RESOLVED in DEFAULT_EVENT_SKILL_MAP

        # 验证映射值正确
        assert DEFAULT_EVENT_SKILL_MAP[EventType.COMMAND] == "execute_command"
        assert DEFAULT_EVENT_SKILL_MAP[EventType.QUERY] == "query_data"
        assert DEFAULT_EVENT_SKILL_MAP[EventType.CHAT] == "chat"
        assert DEFAULT_EVENT_SKILL_MAP[EventType.AGENT_MESSAGE] == "receive_message"
        assert DEFAULT_EVENT_SKILL_MAP[EventType.END_TURN] == "prepare_turn"
        assert DEFAULT_EVENT_SKILL_MAP[EventType.TURN_RESOLVED] == "summarize_turn"


class TestSkillRegistry:
    """测试 SkillRegistry 类"""

    def test_get_skill_for_event_known(self):
        """验证已知事件返回正确的 Skill 名称"""
        registry = SkillRegistry()

        assert registry.get_skill_for_event(EventType.COMMAND) == "execute_command"
        assert registry.get_skill_for_event(EventType.QUERY) == "query_data"
        assert registry.get_skill_for_event(EventType.CHAT) == "chat"
        assert registry.get_skill_for_event(EventType.AGENT_MESSAGE) == "receive_message"
        assert registry.get_skill_for_event(EventType.END_TURN) == "prepare_turn"
        assert registry.get_skill_for_event(EventType.TURN_RESOLVED) == "summarize_turn"

    def test_get_skill_for_event_unknown(self):
        """验证未知事件返回 None"""
        registry = SkillRegistry()

        # 测试未知事件类型
        assert registry.get_skill_for_event("unknown_event") is None
        assert registry.get_skill_for_event("random_type") is None
        assert registry.get_skill_for_event("") is None

    def test_register_skill(self):
        """验证动态注册 Skill"""
        registry = SkillRegistry()

        # 创建测试 Skill
        metadata = SkillMetadata(
            name="test_skill",
            version="1.0",
            description="Test skill",
        )
        skill = Skill(metadata=metadata, content="Test content")

        # 注册 Skill
        registry.register_skill(skill)

        # 验证注册成功
        assert registry.has_skill("test_skill")
        assert registry.get_skill("test_skill") == skill
        assert "test_skill" in registry.list_skills()

    def test_register_multiple_skills(self):
        """验证注册多个 Skill"""
        registry = SkillRegistry()

        # 创建多个测试 Skill
        skill1 = Skill(
            metadata=SkillMetadata(name="skill1", description="Skill 1", version="1.0"),
            content="Content 1",
        )
        skill2 = Skill(
            metadata=SkillMetadata(name="skill2", description="Skill 2", version="1.0"),
            content="Content 2",
        )
        skill3 = Skill(
            metadata=SkillMetadata(name="skill3", description="Skill 3", version="1.0"),
            content="Content 3",
        )

        # 注册所有 Skill
        registry.register_skill(skill1)
        registry.register_skill(skill2)
        registry.register_skill(skill3)

        # 验证所有 Skill 都已注册
        assert registry.has_skill("skill1")
        assert registry.has_skill("skill2")
        assert registry.has_skill("skill3")

        # 验证 list_skills 返回所有 Skill
        skills_list = registry.list_skills()
        assert len(skills_list) == 3
        assert "skill1" in skills_list
        assert "skill2" in skills_list
        assert "skill3" in skills_list

    def test_has_skill_not_found(self):
        """验证检查不存在的 Skill 返回 False"""
        registry = SkillRegistry()

        assert not registry.has_skill("nonexistent_skill")
        assert not registry.has_skill("")

    def test_get_skill_not_found(self):
        """验证获取不存在的 Skill 返回 None"""
        registry = SkillRegistry()

        assert registry.get_skill("nonexistent_skill") is None
        assert registry.get_skill("") is None

    def test_register_skill_overwrite(self):
        """验证重复注册 Skill 会覆盖"""
        registry = SkillRegistry()

        # 注册第一个 Skill
        skill1 = Skill(
            metadata=SkillMetadata(name="test_skill", description="Original", version="1.0"),
            content="Original content",
        )
        registry.register_skill(skill1)
        assert registry.get_skill("test_skill").content == "Original content"

        # 注册同名 Skill（覆盖）
        skill2 = Skill(
            metadata=SkillMetadata(name="test_skill", description="Updated", version="2.0"),
            content="Updated content",
        )
        registry.register_skill(skill2)
        assert registry.get_skill("test_skill").content == "Updated content"
        assert registry.get_skill("test_skill").metadata.version == "2.0"

    def test_list_skills_empty(self):
        """验证空注册表返回空列表"""
        registry = SkillRegistry()

        skills_list = registry.list_skills()
        assert skills_list == []
        assert len(skills_list) == 0

    def test_event_map_isolation(self):
        """验证不同实例的映射表相互隔离"""
        registry1 = SkillRegistry()
        registry2 = SkillRegistry()

        # 注册 Skill 到 registry1
        skill = Skill(
            metadata=SkillMetadata(name="test_skill", description="Test", version="1.0"),
            content="Test content",
        )
        registry1.register_skill(skill)

        # 验证 registry1 有 Skill，registry2 没有
        assert registry1.has_skill("test_skill")
        assert not registry2.has_skill("test_skill")

        # 验证事件映射在两个实例中都可用
        assert registry1.get_skill_for_event(EventType.COMMAND) == "execute_command"
        assert registry2.get_skill_for_event(EventType.COMMAND) == "execute_command"
