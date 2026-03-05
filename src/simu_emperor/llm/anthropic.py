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

    # Claude 模型上下文窗口大小
    _CONTEXT_WINDOWS = {
        # Claude 3.5 系列
        "claude-sonnet-4-20250514": 200000,
        "claude-3-5-sonnet-20241022": 200000,
        # Claude 3 系列
        "claude-3-opus-20240229": 200000,
        "claude-3-sonnet-20240229": 200000,
        "claude-3-haiku-20240307": 200000,
        # Claude 2 系列
        "claude-2.1": 100000,
        "claude-2.0": 100000,
        "claude-instant-1.2": 100000,
    }

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

    def get_context_window_size(self) -> int:
        """
        获取当前 Claude 模型的上下文窗口大小

        如果模型在映射表中，返回准确的值。
        如果不在映射表中，根据模型名称模式智能推测，并记录警告。

        Returns:
            上下文窗口大小（token 数）
        """
        # 优先从映射表查找
        if self.model in self._CONTEXT_WINDOWS:
            return self._CONTEXT_WINDOWS[self.model]

        # 智能推测：根据模型名称模式
        model_lower = self.model.lower()

        # Claude 3 和 Claude 3.5/3.7 系列通常有 200K context
        if "claude-3" in model_lower or "claude-3.5" in model_lower or "claude-3.7" in model_lower:
            logger.info(
                f"Model '{self.model}' not in context window table, assuming 200K (Claude 3 series)"
            )
            return 200000

        # Claude-2 系列通常有 200K context
        if "claude-2" in model_lower:
            logger.info(
                f"Model '{self.model}' not in context window table, assuming 200K (Claude 2 series)"
            )
            return 200000

        # Claude-instant (1.2) 系列通常有 100K context
        if "claude-instant" in model_lower:
            logger.info(
                f"Model '{self.model}' not in context window table, assuming 100K (Claude Instant)"
            )
            return 100000

        # Claude Sonnet 4 (claude-sonnet-4-* 系列）
        if "claude-sonnet-4" in model_lower:
            logger.info(
                f"Model '{self.model}' not in context window table, assuming 200K (Claude Sonnet 4)"
            )
            return 200000

        # 无法推测，使用保守默认值并记录警告
        logger.warning(
            f"Unknown model '{self.model}', cannot determine context window size. "
            f"Using conservative default 100000 tokens. "
            f"Please add this model to _CONTEXT_WINDOWS for accurate sizing."
        )
        return 100000

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

    async def call_with_functions(
        self,
        prompt: str,
        functions: list[dict],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> dict:
        """
        调用 Claude API 并支持 function calling (tool use)

        Args:
            prompt: 用户提示词
            functions: 可用函数列表（需要转换为 Anthropic 格式）
            system_prompt: 系统提示词（可选）
            temperature: 温度参数
            max_tokens: 最大生成 token 数

        Returns:
            包含 response_text 和 tool_calls 的字典
        """
        try:
            # 转换为 Anthropic 的 tools 格式
            tools = []
            for func in functions:
                tool = {
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": {
                        "type": "object",
                        "properties": func.get("parameters", {}).get("properties", {}),
                        "required": func.get("parameters", {}).get("required", []),
                    },
                }
                tools.append(tool)

            kwargs = {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
                "tools": tools,
            }

            if system_prompt:
                kwargs["system"] = system_prompt

            response = await self.client.messages.create(**kwargs)

            # 提取文本内容和 tool_calls
            response_text = ""
            tool_calls = []

            for block in response.content:
                if block.type == "text":
                    response_text += block.text
                elif block.type == "tool_use":
                    tool_calls.append(
                        {"id": block.id, "function": {"name": block.name, "arguments": block.input}}
                    )

            return {"response_text": response_text, "tool_calls": tool_calls}

        except Exception as e:
            logger.error(f"Error calling Anthropic API with functions: {e}", exc_info=True)
            raise
