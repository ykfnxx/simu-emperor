"""Skill 验证器"""

from pathlib import Path

from simu_emperor.agents.skills.models import Skill
from simu_emperor.agents.skills.exceptions import SkillValidationError


class SkillValidator:
    """Skill 验证器"""

    @staticmethod
    def validate_name_matches_filename(skill: Skill, file_path: Path) -> None:
        """验证 metadata.name 与文件名一致

        Args:
            skill: Skill 对象
            file_path: Skill 文件路径

        Raises:
            SkillValidationError: 当 name 与文件名不一致时
        """
        skill_name = file_path.stem
        if skill.metadata.name != skill_name:
            raise SkillValidationError(
                skill.metadata.name,
                "name",
                f"与文件名 '{skill_name}' 不一致",
            )

    @staticmethod
    def validate_required_fields(skill: Skill) -> None:
        """验证必需字段存在

        Args:
            skill: Skill 对象

        Raises:
            SkillValidationError: 当必需字段缺失或为空时
        """
        if not skill.metadata.name:
            raise SkillValidationError(skill.metadata.name or "unknown", "name", "name 不能为空")

        if not skill.metadata.description:
            raise SkillValidationError(skill.metadata.name, "description", "description 不能为空")
