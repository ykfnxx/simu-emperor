"""
Anthropic Claude LLM 提供商
"""

import logging

from simu_emperor.llm.base import LLMProvider

logger = logging.getLogger(__name__)

try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("anthropic package not installed. AnthropicProvider will not work.")


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude 提供商

    使用 anthropic SDK 调用 Claude API。
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """
        初始化 Anthropic 提供商

        Args:
            api_key: Anthropic API 密钥
            model: 模型名称（默认 claude-sonnet-4-20250514）
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package is required. Install with: pip install anthropic")

        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        logger.info(f"AnthropicProvider initialized with model: {model}")

    async def call(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """
        调用 Claude API

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            temperature: 温度参数（0-1）
            max_tokens: 最大生成 token 数

        Returns:
            Claude 响应文本
        """
        try:
            kwargs = {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }

            if system_prompt:
                kwargs["system"] = system_prompt

            response = await self.client.messages.create(**kwargs)

            # 提取文本内容
            content = response.content[0].text
            return content

        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}", exc_info=True)
            raise
