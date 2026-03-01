"""Skill 文件解析器"""

import yaml
from pathlib import Path
from simu_emperor.agents.skills.models import Skill, SkillMetadata
from simu_emperor.agents.skills.exceptions import SkillParseError


class SkillParser:
    """Skill 文件解析器

    支持解析 YAML Frontmatter + Markdown Body 格式的 Skill 文件。

    文件格式：
        ---
        name: skill_name
        version: 1.0.0
        description: Optional description
        ---
        Markdown content here...
    """

    def parse_file(self, file_path: Path) -> Skill:
        """解析 Skill 文件

        Args:
            file_path: Skill 文件路径

        Returns:
            Skill: 解析后的 Skill 对象

        Raises:
            SkillParseError: 文件格式错误或解析失败
        """
        skill_name = file_path.stem  # 从文件名提取 skill_name

        try:
            # 读取文件内容
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except FileNotFoundError as e:
                raise SkillParseError(skill_name, str(file_path), "文件不存在") from e
            except Exception as e:
                raise SkillParseError(skill_name, str(file_path), f"读取文件失败: {e}") from e

            # 获取文件修改时间
            try:
                mtime = file_path.stat().st_mtime
            except Exception as e:
                raise SkillParseError(skill_name, str(file_path), f"获取文件信息失败: {e}") from e

            # 分离 frontmatter 和 body
            try:
                frontmatter, body = self._split_frontmatter(content)
            except SkillParseError:
                raise
            except Exception as e:
                raise SkillParseError(
                    skill_name, str(file_path), f"分离 frontmatter 失败: {e}"
                ) from e

            # 解析 YAML frontmatter
            metadata_dict = yaml.safe_load(frontmatter)
            if not isinstance(metadata_dict, dict):
                raise SkillParseError(
                    skill_name,
                    str(file_path),
                    f"YAML frontmatter 格式错误: 必须是字典类型, "
                    f"实际类型: {type(metadata_dict).__name__}",
                )

            # 构建 SkillMetadata
            try:
                metadata = SkillMetadata.from_dict(metadata_dict)
            except KeyError as e:
                raise SkillParseError(skill_name, str(file_path), f"缺少必需字段: {e}") from e
            except Exception as e:
                raise SkillParseError(skill_name, str(file_path), f"解析 metadata 失败: {e}") from e

            # 构建 Skill 对象
            return Skill(metadata=metadata, content=body.strip(), file_path=file_path, mtime=mtime)

        except SkillParseError:
            # 直接重新抛出 SkillParseError
            raise
        except Exception as e:
            # 捕获其他未预期的异常
            raise SkillParseError(
                skill_name, str(file_path), f"解析文件时发生未预期错误: {e}"
            ) from e

    def _split_frontmatter(self, content: str) -> tuple[str, str]:
        """分离 YAML Frontmatter 和 Markdown Body

        Args:
            content: 文件完整内容

        Returns:
            tuple[str, str]: (frontmatter, body)

        Raises:
            ValueError: frontmatter 格式错误（会被上层转换为 SkillParseError）
        """
        lines = content.split("\n")

        # 检查是否有 frontmatter 开始标记
        if not lines or lines[0].strip() != "---":
            raise ValueError("文件缺少 YAML frontmatter: 文件必须以 '---' 开头")

        # 查找 frontmatter 结束标记
        try:
            end_index = lines.index("---", 1)
        except ValueError:
            raise ValueError("YAML frontmatter 未正确关闭: 缺少结束的 '---' 标记")

        # 提取 frontmatter 和 body
        frontmatter_lines = lines[1:end_index]
        body_lines = lines[end_index + 1 :]

        frontmatter = "\n".join(frontmatter_lines)
        body = "\n".join(body_lines)

        return frontmatter, body
