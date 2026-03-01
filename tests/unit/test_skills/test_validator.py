"""SkillValidator 单元测试"""

from pathlib import Path

import pytest

from simu_emperor.agents.skills.models import Skill, SkillMetadata
from simu_emperor.agents.skills.validator import SkillValidator
from simu_emperor.agents.skills.exceptions import SkillValidationError


class TestSkillValidator:
    """SkillValidator 测试类"""

    def test_validate_name_matches_filename_valid(self):
        """测试验证 name 与文件名一致（成功情况）"""
        metadata = SkillMetadata(name="test_skill", description="Test skill")
        skill = Skill(metadata=metadata, content="Content")
        file_path = Path("/skills/test_skill.md")

        # 不应该抛出异常
        SkillValidator.validate_name_matches_filename(skill, file_path)

    def test_validate_name_matches_filename_invalid(self):
        """测试验证 name 与文件名不一致（失败情况）"""
        metadata = SkillMetadata(name="different_skill", description="Test skill")
        skill = Skill(metadata=metadata, content="Content")
        file_path = Path("/skills/test_skill.md")

        with pytest.raises(SkillValidationError) as exc_info:
            SkillValidator.validate_name_matches_filename(skill, file_path)

        assert exc_info.value.skill_name == "different_skill"
        assert exc_info.value.field == "name"
        assert "test_skill" in str(exc_info.value)

    def test_validate_required_fields_valid(self):
        """测试验证必需字段存在（成功情况）"""
        metadata = SkillMetadata(name="test_skill", description="Test description")
        skill = Skill(metadata=metadata, content="Content")

        # 不应该抛出异常
        SkillValidator.validate_required_fields(skill)

    def test_validate_required_fields_empty_name(self):
        """测试验证 name 为空（失败情况）"""
        metadata = SkillMetadata(name="", description="Test description")
        skill = Skill(metadata=metadata, content="Content")

        with pytest.raises(SkillValidationError) as exc_info:
            SkillValidator.validate_required_fields(skill)

        assert exc_info.value.skill_name == "unknown"
        assert exc_info.value.field == "name"
        assert "name 不能为空" in str(exc_info.value)

    def test_validate_required_fields_empty_description(self):
        """测试验证 description 为空（失败情况）"""
        metadata = SkillMetadata(name="test_skill", description="")
        skill = Skill(metadata=metadata, content="Content")

        with pytest.raises(SkillValidationError) as exc_info:
            SkillValidator.validate_required_fields(skill)

        assert exc_info.value.skill_name == "test_skill"
        assert exc_info.value.field == "description"
        assert "description 不能为空" in str(exc_info.value)
