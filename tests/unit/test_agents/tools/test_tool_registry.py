"""Tests for ToolRegistry"""

import pytest
from simu_emperor.agents.tools.tool_registry import ToolRegistry, ToolMetadata


async def sample_tool(args: dict, event) -> str:
    """Sample tool handler"""
    return f"Tool called with args: {args}"


async def action_tool(args: dict, event) -> str:
    """Sample action tool"""
    return "Action completed"


def test_register_tool():
    """测试注册工具"""
    registry = ToolRegistry()
    metadata = ToolMetadata(
        name="test_tool",
        description="A test tool",
        parameters={"type": "object", "properties": {}},
        category="query",
    )

    registry.register("test_tool", sample_tool, metadata)

    assert registry.get_handler("test_tool") == sample_tool
    assert registry.get_metadata("test_tool") == metadata


def test_register_tool_with_success_message():
    """测试注册带成功消息的工具"""
    registry = ToolRegistry()
    metadata = ToolMetadata(
        name="action_tool",
        description="An action tool",
        parameters={"type": "object", "properties": {}},
        category="action",
    )

    registry.register("action_tool", action_tool, metadata, success_message="✅ Action done")

    assert registry.get_success_message("action_tool") == "✅ Action done"


def test_list_all_tools():
    """测试列出所有工具"""
    registry = ToolRegistry()
    metadata1 = ToolMetadata(
        name="tool1",
        description="Tool 1",
        parameters={},
        category="query",
    )
    metadata2 = ToolMetadata(
        name="tool2",
        description="Tool 2",
        parameters={},
        category="action",
    )

    registry.register("tool1", sample_tool, metadata1)
    registry.register("tool2", action_tool, metadata2)

    all_tools = registry.list_all()
    assert len(all_tools) == 2
    assert "tool1" in all_tools
    assert "tool2" in all_tools


def test_to_openai_schemas():
    """测试转换为OpenAI格式"""
    registry = ToolRegistry()
    metadata = ToolMetadata(
        name="test_tool",
        description="A test tool",
        parameters={
            "type": "object",
            "properties": {"arg1": {"type": "string", "description": "First argument"}},
            "required": ["arg1"],
        },
        category="query",
    )

    registry.register("test_tool", sample_tool, metadata)

    schemas = registry.to_openai_schemas()
    assert len(schemas) == 1
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "test_tool"
    assert "parameters" in schemas[0]["function"]


def test_get_nonexistent_tool():
    """测试获取不存在的工具"""
    registry = ToolRegistry()
    assert registry.get_handler("nonexistent") is None
    assert registry.get_metadata("nonexistent") is None
    assert registry.get_success_message("nonexistent") is None
