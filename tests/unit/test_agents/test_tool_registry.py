"""Tests for decorator-based tool registry."""

import pytest

from simu_emperor.agents.tools.registry import (
    ToolMeta,
    ToolProvider,
    ToolRegistry,
    ToolResult,
    tool,
)


class TestToolResult:
    def test_default_values(self):
        result = ToolResult(output="ok")
        assert result.output == "ok"
        assert result.success is True
        assert result.side_effect is None
        assert result.ends_loop is False
        assert result.creates_task is False

    def test_custom_values(self):
        result = ToolResult(output="done", success=False, ends_loop=True)
        assert result.success is False
        assert result.ends_loop is True


class TestToolDecorator:
    def test_decorator_attaches_meta(self):
        @tool(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
            category="test",
        )
        async def my_tool(self, args, event):
            return "ok"

        assert hasattr(my_tool, "_tool_meta")
        assert my_tool._tool_meta.name == "test_tool"
        assert my_tool._tool_meta.category == "test"

    def test_decorator_preserves_function_name(self):
        @tool(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
        )
        async def my_tool(self, args, event):
            return "result"

        assert my_tool.__name__ == "my_tool"


class TestToolRegistry:
    def test_register_provider_discovers_decorated_methods(self):
        class MyTools(ToolProvider):
            @tool(
                name="foo",
                description="test foo",
                parameters={"type": "object", "properties": {}},
                category="test",
            )
            async def foo(self, args, event):
                return "ok"

            @tool(
                name="bar",
                description="test bar",
                parameters={"type": "object", "properties": {}},
                category="test",
            )
            async def bar(self, args, event):
                return "also ok"

        registry = ToolRegistry()
        registry.register_provider(MyTools())
        names = [t["name"] for t in registry.to_function_definitions()]
        assert "foo" in names
        assert "bar" in names

    def test_duplicate_tool_raises(self):
        class Tools1(ToolProvider):
            @tool(
                name="dup",
                description="first",
                parameters={"type": "object", "properties": {}},
            )
            async def dup(self, args, event):
                return "ok"

        class Tools2(ToolProvider):
            @tool(
                name="dup",
                description="second",
                parameters={"type": "object", "properties": {}},
            )
            async def dup(self, args, event):
                return "ok"

        registry = ToolRegistry()
        registry.register_provider(Tools1())
        with pytest.raises(ValueError, match="Duplicate tool: dup"):
            registry.register_provider(Tools2())

    def test_get_handler(self):
        class MyTools(ToolProvider):
            @tool(
                name="test_fn",
                description="test",
                parameters={"type": "object", "properties": {}},
            )
            async def test_fn(self, args, event):
                return "handled"

        registry = ToolRegistry()
        provider = MyTools()
        registry.register_provider(provider)
        handler = registry.get_handler("test_fn")
        assert handler is not None

    def test_get_returns_meta(self):
        class MyTools(ToolProvider):
            @tool(
                name="meta_test",
                description="test desc",
                parameters={"type": "object", "properties": {}},
                category="query",
            )
            async def meta_test(self, args, event):
                return "ok"

        registry = ToolRegistry()
        registry.register_provider(MyTools())
        meta = registry.get("meta_test")
        assert isinstance(meta, ToolMeta)
        assert meta.category == "query"

    def test_list_by_category(self):
        class MyTools(ToolProvider):
            @tool(
                name="q1",
                description="query",
                parameters={"type": "object", "properties": {}},
                category="query",
            )
            async def q1(self, args, event):
                return "ok"

            @tool(
                name="a1",
                description="action",
                parameters={"type": "object", "properties": {}},
                category="action",
            )
            async def a1(self, args, event):
                return "ok"

        registry = ToolRegistry()
        registry.register_provider(MyTools())
        query_tools = registry.list_by_category("query")
        assert len(query_tools) == 1
        assert query_tools[0].name == "q1"

    def test_undecorated_methods_ignored(self):
        class MyTools(ToolProvider):
            async def helper_method(self, args, event):
                return "not a tool"

        registry = ToolRegistry()
        registry.register_provider(MyTools())
        assert len(registry.list_all()) == 0

    def test_get_nonexistent_returns_none(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None
        assert registry.get_handler("nonexistent") is None

    @pytest.mark.asyncio
    async def test_handler_callable(self):
        class MyTools(ToolProvider):
            @tool(
                name="callable_test",
                description="test",
                parameters={"type": "object", "properties": {}},
            )
            async def callable_test(self, args, event):
                return "result"

        registry = ToolRegistry()
        provider = MyTools()
        registry.register_provider(provider)
        handler = registry.get_handler("callable_test")
        result = await handler({}, None)
        assert result == "result"
