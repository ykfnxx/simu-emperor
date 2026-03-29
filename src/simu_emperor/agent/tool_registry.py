import logging
from dataclasses import dataclass, field
from typing import Any, Callable, TYPE_CHECKING

from simu_emperor.mq.event import Event

if TYPE_CHECKING:
    from simu_emperor.agent.agent import Agent
    from simu_emperor.agent.context_manager import ContextManager


logger = logging.getLogger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    handler: Callable | None = None

    def to_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self, agent: "Agent"):
        self._agent = agent
        self._tools: dict[str, Tool] = {}
        self._handlers: dict[str, Callable] = {}

        self._query_tools: Any = None
        self._action_tools: Any = None
        self._memory_tools: Any = None
        self._session_tools: Any = None

    def set_query_tools(self, tools: Any) -> None:
        self._query_tools = tools

    def set_action_tools(self, tools: Any) -> None:
        self._action_tools = tools

    def set_memory_tools(self, tools: Any) -> None:
        self._memory_tools = tools

    def set_session_tools(self, tools: Any) -> None:
        self._session_tools = tools

    def register_tool(self, tool: Tool, handler: Callable) -> None:
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler
        logger.debug(f"Tool registered: {tool.name}")

    def get_functions(self) -> list[dict]:
        return [tool.to_openai_schema() for tool in self._tools.values()]

    async def dispatch(
        self,
        name: str,
        args: dict,
        event: Event,
        ctx: "ContextManager",
    ) -> str:
        handler = self._handlers.get(name)
        if not handler:
            logger.warning(f"Unknown tool: {name}")
            return f"Unknown tool: {name}"

        try:
            result = await handler(args, event, ctx)
            return str(result)
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            return f"Tool execution failed: {str(e)}"

    def register_all_tools(self) -> None:
        if self._query_tools:
            self._register_query_tools()
        if self._action_tools:
            self._register_action_tools()
        if self._memory_tools:
            self._register_memory_tools()
        if self._session_tools:
            self._register_session_tools()

    def _register_query_tools(self) -> None:
        tool_definitions = [
            ("query_province_data", "Query data for a specific province"),
            ("query_national_data", "Query national level data"),
            ("list_provinces", "List all provinces"),
            ("list_agents", "List all agents"),
            ("get_agent_info", "Get information about a specific agent"),
            ("query_incidents", "Query incident records"),
        ]

        for name, desc in tool_definitions:
            tool = Tool(
                name=name,
                description=desc,
                parameters={"type": "object", "properties": {}},
            )
            if self._query_tools and hasattr(self._query_tools, name):
                self.register_tool(tool, getattr(self._query_tools, name))

    def _register_action_tools(self) -> None:
        tool_definitions = [
            ("send_message", "Send a message to another agent"),
            ("finish_loop", "Finish the current processing loop"),
            ("create_incident", "Create a new incident"),
            ("update_soul", "Update agent's soul/personality"),
        ]

        for name, desc in tool_definitions:
            tool = Tool(
                name=name,
                description=desc,
                parameters={"type": "object", "properties": {}},
            )
            if self._action_tools and hasattr(self._action_tools, name):
                self.register_tool(tool, getattr(self._action_tools, name))

    def _register_memory_tools(self) -> None:
        tool_definitions = [
            ("retrieve_memory", "Retrieve memories from vector store"),
            ("write_memory", "Write a memory to persistent storage"),
        ]

        for name, desc in tool_definitions:
            tool = Tool(
                name=name,
                description=desc,
                parameters={"type": "object", "properties": {}},
            )
            if self._memory_tools and hasattr(self._memory_tools, name):
                self.register_tool(tool, getattr(self._memory_tools, name))

    def _register_session_tools(self) -> None:
        tool_definitions = [
            ("create_task_session", "Create a new task session"),
            ("finish_task_session", "Mark a task session as completed"),
            ("fail_task_session", "Mark a task session as failed"),
        ]

        for name, desc in tool_definitions:
            tool = Tool(
                name=name,
                description=desc,
                parameters={"type": "object", "properties": {}},
            )
            if self._session_tools and hasattr(self._session_tools, name):
                self.register_tool(tool, getattr(self._session_tools, name))
