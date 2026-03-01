"""Test skill exception classes"""

import pytest

from simu_emperor.agents.skills.exceptions import (
    SkillError,
    SkillNotFoundError,
    SkillParseError,
    SkillValidationError,
)


class TestSkillError:
    """Test base SkillError class"""

    def test_is_exception_subclass(self):
        """SkillError should be an Exception subclass"""
        assert issubclass(SkillError, Exception)

    def test_can_be_raised(self):
        """SkillError can be raised and caught"""
        with pytest.raises(SkillError):
            raise SkillError("Test error")


class TestSkillNotFoundError:
    """Test SkillNotFoundError class"""

    def test_is_skill_error_subclass(self):
        """SkillNotFoundError should be a SkillError subclass"""
        assert issubclass(SkillNotFoundError, SkillError)

    def test_message_without_paths(self):
        """Error message without searched paths"""
        exc = SkillNotFoundError("query_data")
        assert str(exc) == "Skill 'query_data' not found"
        assert exc.skill_name == "query_data"
        assert exc.searched_paths == []

    def test_message_with_paths(self):
        """Error message with searched paths"""
        paths = [
            "/data/skills/query_data.md",
            "/data/skills/query_data.yaml",
        ]
        exc = SkillNotFoundError("query_data", searched_paths=paths)
        expected = "Skill 'query_data' not found (searched: /data/skills/query_data.md, /data/skills/query_data.yaml)"
        assert str(exc) == expected
        assert exc.skill_name == "query_data"
        assert exc.searched_paths == paths

    def test_can_be_raised_and_caught_as_skill_error(self):
        """Can be caught as SkillError"""
        with pytest.raises(SkillError):
            raise SkillNotFoundError("test_skill")

    def test_can_be_raised_and_caught_as_specific_type(self):
        """Can be caught as SkillNotFoundError"""
        with pytest.raises(SkillNotFoundError):
            raise SkillNotFoundError("test_skill")


class TestSkillParseError:
    """Test SkillParseError class"""

    def test_is_skill_error_subclass(self):
        """SkillParseError should be a SkillError subclass"""
        assert issubclass(SkillParseError, SkillError)

    def test_message_format(self):
        """Error message format"""
        exc = SkillParseError(
            skill_name="query_data",
            file_path="/data/skills/query_data.md",
            detail="Invalid YAML syntax at line 15",
        )
        expected = "Failed to parse skill 'query_data' from /data/skills/query_data.md: Invalid YAML syntax at line 15"
        assert str(exc) == expected
        assert exc.skill_name == "query_data"
        assert exc.file_path == "/data/skills/query_data.md"

    def test_can_be_raised_and_caught_as_skill_error(self):
        """Can be caught as SkillError"""
        with pytest.raises(SkillError):
            raise SkillParseError("test_skill", "/path/to/file.md", "parse error")

    def test_can_be_raised_and_caught_as_specific_type(self):
        """Can be caught as SkillParseError"""
        with pytest.raises(SkillParseError):
            raise SkillParseError("test_skill", "/path/to/file.md", "parse error")


class TestSkillValidationError:
    """Test SkillValidationError class"""

    def test_is_skill_error_subclass(self):
        """SkillValidationError should be a SkillError subclass"""
        assert issubclass(SkillValidationError, SkillError)

    def test_message_format(self):
        """Error message format"""
        exc = SkillValidationError(
            skill_name="query_data",
            field="required_sections",
            reason="Missing 'description' section",
        )
        expected = "Skill 'query_data' validation failed for field 'required_sections': Missing 'description' section"
        assert str(exc) == expected
        assert exc.skill_name == "query_data"
        assert exc.field == "required_sections"

    def test_can_be_raised_and_caught_as_skill_error(self):
        """Can be caught as SkillError"""
        with pytest.raises(SkillError):
            raise SkillValidationError("test_skill", "field", "validation error")

    def test_can_be_raised_and_caught_as_specific_type(self):
        """Can be caught as SkillValidationError"""
        with pytest.raises(SkillValidationError):
            raise SkillValidationError("test_skill", "field", "validation error")


class TestExceptionHierarchy:
    """Test exception class hierarchy"""

    def test_all_exceptions_share_common_base(self):
        """All skill exceptions should inherit from SkillError"""
        assert issubclass(SkillNotFoundError, SkillError)
        assert issubclass(SkillParseError, SkillError)
        assert issubclass(SkillValidationError, SkillError)

    def test_catch_all_with_base_class(self):
        """Can catch all skill exceptions with SkillError"""
        exceptions = [
            SkillNotFoundError("test"),
            SkillParseError("test", "/path", "detail"),
            SkillValidationError("test", "field", "reason"),
        ]

        for exc in exceptions:
            with pytest.raises(SkillError):
                raise exc
