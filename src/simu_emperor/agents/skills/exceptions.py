"""Skill 模块异常类"""


class SkillError(Exception):
    """Skill 模块基础错误"""

    pass


class SkillNotFoundError(SkillError):
    """Skill 文件不存在"""

    def __init__(self, skill_name: str, searched_paths: list[str] | None = None):
        self.skill_name = skill_name
        self.searched_paths = searched_paths or []
        message = f"Skill '{skill_name}' not found"
        if searched_paths:
            message += f" (searched: {', '.join(searched_paths)})"
        super().__init__(message)


class SkillParseError(SkillError):
    """YAML/Markdown 解析错误"""

    def __init__(self, skill_name: str, file_path: str, detail: str):
        self.skill_name = skill_name
        self.file_path = file_path
        super().__init__(f"Failed to parse skill '{skill_name}' from {file_path}: {detail}")


class SkillValidationError(SkillError):
    """Skill 验证失败"""

    def __init__(self, skill_name: str, field: str, reason: str):
        self.skill_name = skill_name
        self.field = field
        super().__init__(f"Skill '{skill_name}' validation failed for field '{field}': {reason}")
