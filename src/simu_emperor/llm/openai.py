"""
OpenAI GPT LLM 提供商
"""

import logging

from simu_emperor.llm.base import LLMProvider

logger = logging.getLogger(__name__)

try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("openai package not installed. OpenAIProvider will not work.")


class OpenAIProvider(LLMProvider):
    """
    OpenAI GPT 提供商

    使用 openai SDK 调用 GPT API。
    """

    def __init__(self, api_key: str, model: str = "gpt-4", base_url: str | None = None):
        """
        初始化 OpenAI 提供商

        Args:
            api_key: OpenAI API 密钥
            model: 模型名称（默认 gpt-4）
            base_url: API Base URL（可选，用于兼容 OpenAI 格式的服务）
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package is required. Install with: pip install openai")

        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = openai.AsyncOpenAI(**client_kwargs)
        self.model = model
        logger.info(f"OpenAIProvider initialized with model: {model}, base_url: {base_url or 'default'}")

    async def call(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """
        调用 GPT API

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            temperature: 温度参数（0-1）
            max_tokens: 最大生成 token 数

        Returns:
            GPT 响应文本
        """
        try:
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": prompt})

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # 提取文本内容
            content = response.choices[0].message.content
            return content

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}", exc_info=True)
            raise
