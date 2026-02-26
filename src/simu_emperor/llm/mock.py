"""
Mock LLM 提供商（用于测试）
"""

from simu_emperor.llm.base import LLMProvider


class MockProvider(LLMProvider):
    """
    Mock LLM 提供商

    返回预定义的响应，用于测试。
    """

    def __init__(self, response: str = "Mock response"):
        """
        初始化 Mock 提供商

        Args:
            response: 预定义的响应文本
        """
        self.response = response
        self.call_count = 0

    async def call(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """
        模拟 LLM 调用

        Args:
            prompt: 用户提示词（忽略）
            system_prompt: 系统提示词（忽略）
            temperature: 温度参数（忽略）
            max_tokens: 最大 token 数（忽略）

        Returns:
            预定义的响应文本
        """
        self.call_count += 1
        return self.response

    def set_response(self, response: str) -> None:
        """
        设置响应文本

        Args:
            response: 新的响应文本
        """
        self.response = response

    def reset(self) -> None:
        """重置调用计数"""
        self.call_count = 0
