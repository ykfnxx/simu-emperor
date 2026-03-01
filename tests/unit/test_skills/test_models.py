"""Test Skill data models"""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from simu_emperor.agents.skills.models import Skill, SkillMetadata


class TestSkillMetadata:
    """Test SkillMetadata dataclass"""

    def test_skill_metadata_from_dict(self):
        """Test creating SkillMetadata from dictionary"""
        data = {
            "name": "test_skill",
            "description": "A test skill",
            "version": "2.0",
            "author": "Test Author",
            "tags": ["test", "example"],
            "priority": 5,
            "required_tools": ["tool1", "tool2"],
        }

        metadata = SkillMetadata.from_dict(data)

        assert metadata.name == "test_skill"
        assert metadata.description == "A test skill"
        assert metadata.version == "2.0"
        assert metadata.author == "Test Author"
        assert metadata.tags == ("test", "example")
        assert metadata.priority == 5
        assert metadata.required_tools == ("tool1", "tool2")

    def test_skill_metadata_defaults(self):
        """Test SkillMetadata default values"""
        data = {
            "name": "minimal_skill",
            "description": "Minimal skill with defaults",
        }

        metadata = SkillMetadata.from_dict(data)

        assert metadata.name == "minimal_skill"
        assert metadata.description == "Minimal skill with defaults"
        assert metadata.version == "1.0"
        assert metadata.author == "System"
        assert metadata.tags == ()
        assert metadata.priority == 10
        assert metadata.required_tools == ()

    def test_skill_metadata_name_required(self):
        """Test that 'name' field is required"""
        data = {
            "description": "Skill without name",
        }

        with pytest.raises(KeyError) as exc_info:
            SkillMetadata.from_dict(data)

        assert "name" in str(exc_info.value)

    def test_skill_metadata_description_required(self):
        """Test that 'description' field is required"""
        data = {
            "name": "no_description_skill",
        }

        with pytest.raises(KeyError) as exc_info:
            SkillMetadata.from_dict(data)

        assert "description" in str(exc_info.value)

    def test_skill_metadata_empty_tags(self):
        """Test SkillMetadata with empty tags list"""
        data = {
            "name": "empty_tags",
            "description": "Skill with empty tags",
            "tags": [],
        }

        metadata = SkillMetadata.from_dict(data)

        assert metadata.tags == ()

    def test_skill_metadata_empty_required_tools(self):
        """Test SkillMetadata with empty required_tools list"""
        data = {
            "name": "no_tools",
            "description": "Skill with no required tools",
            "required_tools": [],
        }

        metadata = SkillMetadata.from_dict(data)

        assert metadata.required_tools == ()


class TestSkill:
    """Test Skill dataclass"""

    def test_skill_creation(self):
        """Test creating a Skill object"""
        metadata = SkillMetadata(
            name="test_skill",
            description="Test skill description",
            version="1.0",
        )

        skill = Skill(
            metadata=metadata,
            content="# Test Skill\n\nThis is test content.",
            file_path=Path("/skills/test.md"),
            mtime=1234567890.0,
        )

        assert skill.metadata.name == "test_skill"
        assert skill.content == "# Test Skill\n\nThis is test content."
        assert skill.file_path == Path("/skills/test.md")
        assert skill.mtime == 1234567890.0

    def test_skill_creation_without_optional_fields(self):
        """Test creating Skill without optional fields"""
        metadata = SkillMetadata(
            name="minimal_skill",
            description="Minimal skill",
        )

        skill = Skill(
            metadata=metadata,
            content="Content",
        )

        assert skill.metadata.name == "minimal_skill"
        assert skill.content == "Content"
        assert skill.file_path is None
        assert skill.mtime is None

    def test_skill_is_immutable(self):
        """Test that Skill dataclass is frozen (immutable)"""
        metadata = SkillMetadata(
            name="immutable_skill",
            description="Immutable skill",
        )

        skill = Skill(
            metadata=metadata,
            content="Original content",
        )

        # Attempting to modify should raise FrozenInstanceError
        with pytest.raises(FrozenInstanceError):
            skill.content = "Modified content"

        with pytest.raises(FrozenInstanceError):
            skill.metadata = metadata

        with pytest.raises(FrozenInstanceError):
            skill.file_path = Path("/new/path.md")

    def test_skill_metadata_is_immutable(self):
        """Test that SkillMetadata dataclass is frozen (immutable)"""
        metadata = SkillMetadata(
            name="immutable_metadata",
            description="Immutable metadata",
            tags=("tag1", "tag2"),
        )

        # Attempting to modify should raise FrozenInstanceError
        with pytest.raises(FrozenInstanceError):
            metadata.name = "new_name"

        with pytest.raises(FrozenInstanceError):
            metadata.tags = ("tag3",)

    def test_skill_with_complex_content(self):
        """Test Skill with complex markdown content"""
        metadata = SkillMetadata(
            name="complex_skill",
            description="Skill with complex content",
        )

        content = """# Complex Skill

## Overview
This is a complex skill with multiple sections.

## Instructions
1. Step one
2. Step two
3. Step three

## Code Example
```python
def example():
    return "hello"
```
"""

        skill = Skill(metadata=metadata, content=content)

        assert "## Overview" in skill.content
        assert "```python" in skill.content
        assert skill.metadata.name == "complex_skill"
