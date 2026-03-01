"""Skill 数据模型"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class SkillMetadata:
    """Skill 元数据（YAML Frontmatter）"""

    name: str
    description: str
    version: str = "1.0"
    author: str = "System"
    tags: tuple[str, ...] = ()
    priority: int = 10
    required_tools: tuple[str, ...] = ()
    parameters: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "SkillMetadata":
        return cls(
            name=data["name"],
            description=data["description"],
            version=data.get("version", "1.0"),
            author=data.get("author", "System"),
            tags=tuple(data.get("tags", [])),
            priority=data.get("priority", 10),
            required_tools=tuple(data.get("required_tools", [])),
            parameters=data.get("parameters", {}),
        )


@dataclass(frozen=True)
class Skill:
    """Skill 对象"""

    metadata: SkillMetadata
    content: str
    file_path: Optional[Path] = None
    mtime: Optional[float] = None
