"""工具函数注册表"""

import logging
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class ToolMetadata:
    """工具元数据"""

    name: str
    description: str
    parameters: dict  # JSON Schema 格式
    category: str  # "query" | "action" | "memory"

    def to_openai_schema(self) -> dict:
        """转换为 OpenAI function schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """工具函数注册表"""

    def __init__(self):
        self._tools: dict[str, dict[str, Any]] = {}

    def register(
        self,
        name: str,
        handler: Callable,
        metadata: ToolMetadata,
        success_message: str | None = None,
    ) -> None:
        """注册工具函数"""
        self._tools[name] = {
            "handler": handler,
            "metadata": metadata,
            "success_message": success_message,
        }
        logger.debug(f"Registered tool: {name}")

    def get_handler(self, name: str) -> Callable | None:
        """获取工具处理器"""
        return self._tools.get(name, {}).get("handler")

    def get_metadata(self, name: str) -> ToolMetadata | None:
        """获取工具元数据"""
        return self._tools.get(name, {}).get("metadata")

    def get_success_message(self, name: str) -> str | None:
        """获取成功消息"""
        return self._tools.get(name, {}).get("success_message")

    def list_all(self) -> dict[str, ToolMetadata]:
        """列出所有工具"""
        return {name: data["metadata"] for name, data in self._tools.items()}

    def to_openai_schemas(self) -> list[dict]:
        """转换为 OpenAI function calling 格式"""
        return [metadata.to_openai_schema() for metadata in self.list_all().values()]
