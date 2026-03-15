"""ToolRegistry - 统一工具注册管理"""

from dataclasses import dataclass
from typing import Callable


@dataclass
class Tool:
    """工具定义

    Attributes:
        name: 工具名称（唯一标识符）
        description: 工具描述（用于 LLM Function Calling）
        parameters: JSON Schema 参数定义
        handler: 工具处理函数
        category: 工具分类（"query" | "action" | "memory" | "session"）
    """

    name: str
    description: str
    parameters: dict
    handler: Callable
    category: str

    def to_function_definition(self) -> dict:
        """导出为 LLM Function Calling 格式"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ToolRegistry:
    """工具注册表 - 统一管理所有工具"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """注册工具

        Args:
            tool: Tool 实例

        Raises:
            ValueError: 如果工具名称已存在
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name} already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """获取工具

        Args:
            name: 工具名称

        Returns:
            Tool 实例，如果不存在则返回 None
        """
        return self._tools.get(name)

    def list_all(self) -> list[Tool]:
        """列出所有工具

        Returns:
            所有已注册工具的列表
        """
        return list(self._tools.values())

    def to_function_definitions(self) -> list[dict]:
        """导出所有工具为 LLM Function Calling 格式

        Returns:
            函数定义列表
        """
        return [tool.to_function_definition() for tool in self._tools.values()]

    def list_by_category(self, category: str) -> list[Tool]:
        """按分类列出工具

        Args:
            category: 工具分类（如 "query", "action", "memory", "session"）

        Returns:
            该分类下的所有工具
        """
        return [t for t in self._tools.values() if t.category == category]
