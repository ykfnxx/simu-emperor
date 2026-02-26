"""
LLM 提供商接口
"""

from abc import ABC, abstractmethod


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
