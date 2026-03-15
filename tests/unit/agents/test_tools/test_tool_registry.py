"""Tests for ToolRegistry - unified tool management"""

import pytest

from simu_emperor.agents.tools.tool_registry import Tool, ToolRegistry
from simu_emperor.event_bus.event import Event


class MockTool:
    """Mock tool for testing"""

    def __init__(self):
        self.called_with = None

    async def handler(self, args: dict, event: Event) -> str:
        self.called_with = (args, event)
        return "mock_result"


@pytest.fixture
def mock_tool():
    return MockTool()


@pytest.fixture
def sample_event():
    return Event(
        event_id="test_event_1",
        src="player",
        dst=["agent:test"],
        type="chat",
        payload={"content": "test"},
        timestamp="2026-03-15T00:00:00Z",
        session_id="test_session",
    )


@pytest.fixture
def sample_tool(mock_tool):
    return Tool(
        name="test_tool",
        description="A test tool",
        parameters={
            "type": "object",
            "properties": {
                "param1": {"type": "string"},
            },
            "required": ["param1"],
        },
        handler=mock_tool.handler,
        category="test",
    )


def test_tool_registry_register_and_get(sample_tool):
    """Test tool registration and retrieval"""
    registry = ToolRegistry()
    registry.register(sample_tool)

    retrieved = registry.get("test_tool")
    assert retrieved is not None
    assert retrieved.name == "test_tool"
    assert retrieved.category == "test"
    assert retrieved.description == "A test tool"


def test_tool_registry_get_nonexistent():
    """Test getting nonexistent tool returns None"""
    registry = ToolRegistry()
    assert registry.get("nonexistent") is None


def test_tool_registry_list_all(sample_tool):
    """Test listing all tools"""
    registry = ToolRegistry()
    registry.register(sample_tool)

    tools = registry.list_all()
    assert len(tools) == 1
    assert tools[0].name == "test_tool"


def test_tool_registry_to_function_definitions(sample_tool):
    """Test exporting to LLM Function Calling format"""
    registry = ToolRegistry()
    registry.register(sample_tool)

    definitions = registry.to_function_definitions()
    assert len(definitions) == 1
    assert definitions[0]["name"] == "test_tool"
    assert definitions[0]["description"] == "A test tool"
    assert "parameters" in definitions[0]
    assert definitions[0]["parameters"]["type"] == "object"


def test_tool_registry_list_by_category(sample_tool):
    """Test listing tools by category"""
    registry = ToolRegistry()
    registry.register(sample_tool)

    test_tools = registry.list_by_category("test")
    assert len(test_tools) == 1
    assert test_tools[0].category == "test"

    query_tools = registry.list_by_category("query")
    assert len(query_tools) == 0


def test_tool_registry_duplicate_registration(sample_tool):
    """Test duplicate registration raises ValueError"""
    registry = ToolRegistry()
    registry.register(sample_tool)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(sample_tool)


def test_tool_dataclass_to_function_definition(sample_tool):
    """Test Tool.to_function_definition() method"""
    definition = sample_tool.to_function_definition()

    assert definition["name"] == "test_tool"
    assert definition["description"] == "A test tool"
    assert definition["parameters"]["type"] == "object"
    assert "properties" in definition["parameters"]
    assert definition["parameters"]["required"] == ["param1"]


@pytest.mark.asyncio
async def test_tool_handler_invocation(sample_tool, sample_event, mock_tool):
    """Test that tool handler can be invoked"""
    result = await sample_tool.handler({"param1": "value"}, sample_event)

    assert result == "mock_result"
    assert mock_tool.called_with == ({"param1": "value"}, sample_event)


def test_tool_registry_multiple_tools_by_category():
    """Test listing multiple tools from same category"""
    registry = ToolRegistry()

    async def handler1(args, event):
        return "result1"

    async def handler2(args, event):
        return "result2"

    tool1 = Tool(
        name="query_tool1",
        description="First query tool",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=handler1,
        category="query",
    )

    tool2 = Tool(
        name="query_tool2",
        description="Second query tool",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=handler2,
        category="query",
    )

    action_tool = Tool(
        name="action_tool",
        description="An action tool",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=handler1,
        category="action",
    )

    registry.register(tool1)
    registry.register(tool2)
    registry.register(action_tool)

    query_tools = registry.list_by_category("query")
    assert len(query_tools) == 2

    action_tools = registry.list_by_category("action")
    assert len(action_tools) == 1
