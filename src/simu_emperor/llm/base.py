"""
LLM 提供商接口
"""

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """
    大语言模型提供商接口

    定义 LLM 调用的统一接口。
    """

    @abstractmethod
    async def call(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """
        调用 LLM 生成响应

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            temperature: 温度参数（0-1，越低越确定性）
            max_tokens: 最大生成 token 数

        Returns:
            LLM 响应文本
        """
        pass

    async def call_with_functions(
        self,
        prompt: str,
        functions: list[dict[str, Any]],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> dict[str, Any]:
        """
        调用 LLM 并支持 function calling

        Args:
            prompt: 用户提示词
            functions: 可用函数列表（OpenAI 格式）
            system_prompt: 系统提示词（可选）
            temperature: 温度参数
            max_tokens: 最大生成 token 数

        Returns:
            包含 response_text 和 tool_calls 的字典：
            {
                "response_text": str,  # LLM 的文本响应
                "tool_calls": list[dict]  # LLM 请求调用的函数
            }
        """
        # 默认实现：不支持 function calling，抛出错误
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support function calling. "
            "Please use a provider that implements call_with_functions."
        )
