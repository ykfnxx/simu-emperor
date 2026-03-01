"""SkillParser 单元测试"""

import pytest
from pathlib import Path
from simu_emperor.agents.skills.parser import SkillParser
from simu_emperor.agents.skills.exceptions import SkillParseError


class TestSkillParser:
    """SkillParser 测试类"""

    def test_parse_valid_skill(self, fixtures_dir: Path):
        """测试解析完整的 Skill 文件"""
        parser = SkillParser()
        skill_file = fixtures_dir / "skills" / "query_data.md"

        skill = parser.parse_file(skill_file)

        # 验证 metadata
        assert skill.metadata.name == "query_data"
        assert skill.metadata.version == "1.0.0"
        assert skill.metadata.description == "查询游戏数据"
        assert skill.metadata.author == "system"
        assert skill.metadata.tags == ("query", "data")  # tags 是 tuple
        assert skill.metadata.parameters is not None
        assert "province_id" in skill.metadata.parameters
        assert skill.metadata.parameters["province_id"]["type"] == "str"
        assert skill.metadata.parameters["province_id"]["required"] is True

        # 验证 content
        assert "这是一个用于查询游戏数据的 Skill" in skill.content
        assert "## 使用方法" in skill.content

        # 验证 file_path 和 mtime
        assert skill.file_path == skill_file
        assert isinstance(skill.mtime, float)
        assert skill.mtime > 0

    def test_parse_minimal_skill(self, fixtures_dir: Path):
        """测试解析最小字段的 Skill 文件"""
        parser = SkillParser()
        skill_file = fixtures_dir / "skills" / "write_report.md"

        skill = parser.parse_file(skill_file)

        # 验证必需字段
        assert skill.metadata.name == "write_report"
        assert skill.metadata.description == "撰写报告"
        assert skill.metadata.version == "1.0.0"

        # 验证可选字段为默认值
        assert skill.metadata.author == "System"  # 默认值
        assert skill.metadata.tags == ()  # 空 tuple
        assert skill.metadata.parameters == {}  # 空 dict

        # 验证 content
        assert "这是一个最简单的 Skill 文件" in skill.content

    def test_parse_no_frontmatter(self, fixtures_dir: Path):
        """测试解析没有 frontmatter 的文件（应该抛出异常）"""
        parser = SkillParser()
        skill_file = fixtures_dir / "skills" / "invalid_no_frontmatter.md"

        with pytest.raises(SkillParseError) as exc_info:
            parser.parse_file(skill_file)

        assert "frontmatter" in str(exc_info.value).lower()

    def test_parse_missing_name(self, fixtures_dir: Path):
        """测试解析缺少必需字段的文件（应该抛出异常）"""
        parser = SkillParser()
        skill_file = fixtures_dir / "skills" / "invalid_missing_name.md"

        with pytest.raises(SkillParseError) as exc_info:
            parser.parse_file(skill_file)

        error_msg = str(exc_info.value).lower()
        assert "name" in error_msg or "required" in error_msg

    def test_split_frontmatter_valid(self):
        """测试分离有效的 frontmatter"""
        parser = SkillParser()
        content = """---
name: test
version: 1.0.0
---

Some content here"""

        frontmatter, body = parser._split_frontmatter(content)

        assert frontmatter == "name: test\nversion: 1.0.0"
        # body 会有前导换行符，这是正常的
        assert body.strip() == "Some content here"

    def test_split_frontmatter_no_open_delimiter(self):
        """测试缺少开始分隔符的情况"""
        parser = SkillParser()
        content = "name: test\n---\nSome content"

        # _split_frontmatter 抛出 ValueError，不是 SkillParseError
        with pytest.raises(ValueError) as exc_info:
            parser._split_frontmatter(content)

        assert "frontmatter" in str(exc_info.value).lower()

    def test_split_frontmatter_no_close_delimiter(self):
        """测试缺少结束分隔符的情况"""
        parser = SkillParser()
        content = """---
name: test
version: 1.0.0
Some content"""

        # _split_frontmatter 抛出 ValueError，不是 SkillParseError
        with pytest.raises(ValueError) as exc_info:
            parser._split_frontmatter(content)

        assert "frontmatter" in str(exc_info.value).lower() or "---" in str(exc_info.value)

    def test_split_frontmatter_empty_body(self):
        """测试 body 为空的情况"""
        parser = SkillParser()
        content = """---
name: test
version: 1.0.0
---
"""

        frontmatter, body = parser._split_frontmatter(content)

        assert frontmatter == "name: test\nversion: 1.0.0"
        assert body == ""

    def test_parse_file_not_found(self, fixtures_dir: Path):
        """测试解析不存在的文件"""
        parser = SkillParser()
        skill_file = fixtures_dir / "skills" / "nonexistent.md"

        with pytest.raises(SkillParseError) as exc_info:
            parser.parse_file(skill_file)

        # 检查错误消息包含 "文件不存在"
        assert "文件不存在" in str(exc_info.value)

    def test_parse_name_mismatch_filename(self, fixtures_dir: Path):
        """测试 name 与文件名不一致（应该抛出异常）"""
        parser = SkillParser()
        skill_file = fixtures_dir / "skills" / "invalid_name_mismatch.md"

        with pytest.raises(Exception) as exc_info:
            parser.parse_file(skill_file)

        # 应该抛出 SkillValidationError 或 SkillParseError
        error_msg = str(exc_info.value).lower()
        assert "name" in error_msg or "不一致" in error_msg or "invalid_name_mismatch" in error_msg
