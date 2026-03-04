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

    # GPT 模型上下文窗口大小（根据官方文档）
    _CONTEXT_WINDOWS = {
        # GPT-4o 系列 (2025)
        "gpt-4o": 128000,
        "gpt-4o-2024-05-13": 128000,
        "gpt-4o-mini": 128000,
        # GPT-4 Turbo 系列
        "gpt-4-turbo": 128000,
        "gpt-4-turbo-2024-04-09": 128000,
        "gpt-4-turbo-preview": 128000,
        # GPT-4 系列
        "gpt-4": 8192,
        "gpt-4-32k": 32768,
        # GPT-3.5 Turbo 系列
        "gpt-3.5-turbo": 16385,
        "gpt-3.5-turbo-16k": 16385,
        # O 系列 (推理模型)
        "o1": 200000,
        "o1-mini": 128000,
        # 常见中文模型（兼容 OpenAI API）
        "glm-4": 128000,
        "glm-4-plus": 128000,
        "deepseek-chat": 128000,
        "deepseek-coder": 128000,
        # 阿里云 MiniMax 系列（六）
        "mini-max": 128000,
        "MiniMax-M2.5": 128000,
        "MiniMax-M3": 128000,
    }

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

    def get_context_window_size(self) -> int:
        """
        获取当前 GPT 模型的上下文窗口大小

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

        # GPT-4o 系列通常有 128K context
        if "gpt-4o" in model_lower:
            logger.info(f"Model '{self.model}' not in context window table, assuming 128K (GPT-4o series)")
            return 128000

        # GPT-4 Turbo 系列通常有 128K context
        if "gpt-4-turbo" in model_lower or "gpt-4-turbo" in model_lower:
            logger.info(f"Model '{self.model}' not in context window table, assuming 128K (GPT-4 Turbo series)")
            return 128000

        # GPT-4 系列（非32k版本）通常有 8K context
        if "gpt-4" in model_lower and "32k" not in model_lower:
            logger.info(f"Model '{self.model}' not in context window table, assuming 8K (GPT-4 base)")
            return 8192

        # GPT-4 32K 系列
        if "32k" in model_lower:
            logger.info(f"Model '{self.model}' not in context window table, assuming 32K")
            return 32768

        # O1 系列通常有 200K context
        if "o1" in model_lower and "mini" not in model_lower:
            logger.info(f"Model '{self.model}' not in context window table, assuming 200K (O1 series)")
            return 200000

        # O1-mini 系列通常有 128K context
        if "o1-mini" in model_lower:
            logger.info(f"Model '{self.model}' not in context window table, assuming 128K (O1-mini)")
            return 128000

        # GPT-3.5 Turbo 系列通常有 16K context
        if "gpt-3.5" in model_lower or "gpt-35" in model_lower:
            logger.info(f"Model '{self.model}' not in context window table, assuming 16K (GPT-3.5 Turbo)")
            return 16385

        # 中文模型（智谱、DeepSeek、通义千问等）通常有 128K context
        if any(prefix in model_lower for prefix in ["glm", "deepseek", "qwen", "yi", "baichuan"]):
            logger.info(f"Model '{self.model}' not in context window table, assuming 128K (Chinese model)")
            return 128000

        # 无法推测，使用保守默认值并记录警告
        logger.warning(
            f"Unknown model '{self.model}', cannot determine context window size. "
            f"Using conservative default 8192 tokens. "
            f"Please add this model to _CONTEXT_WINDOWS for accurate sizing."
        )
        return 8192

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

    async def call_with_functions(
        self,
        prompt: str | None = None,
        functions: list[dict] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        messages: list[dict] | None = None,
    ) -> dict:
        """
        调用 GPT API 并支持 function calling

        Args:
            prompt: 用户提示词（如果提供了messages，此参数会被忽略）
            functions: 可用函数列表（OpenAI 格式）
            system_prompt: 系统提示词（可选）
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            messages: 历史消息列表（用于多轮对话）

        Returns:
            包含 response_text 和 tool_calls 的字典
        """
        try:
            # 如果没有提供messages，创建新的
            if messages is None:
                messages = []

                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})

                if prompt:
                    messages.append({"role": "user", "content": prompt})
            else:
                # 如果提供了messages，确保有system prompt
                if system_prompt and not any(msg.get("role") == "system" for msg in messages):
                    messages.insert(0, {"role": "system", "content": system_prompt})

            # 转换为 OpenAI 的 tools 格式
            # 只有当 functions 非空时才传递 tools 参数（某些 API 如阿里云 DashScope 不接受空 tools）
            tools = None
            if functions and len(functions) > 0:
                tools = [
                    {
                        "type": "function",
                        "function": func
                    }
                    for func in functions
                ]

            # 构建 API 调用参数
            api_params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            # 只有当 tools 非空时才添加到参数中
            if tools:
                api_params["tools"] = tools

            response = await self.client.chat.completions.create(**api_params)

            message = response.choices[0].message

            # 提取 tool_calls
            tool_calls = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append({
                        "id": tc.id,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    })

            return {
                "response_text": message.content or "",
                "tool_calls": tool_calls
            }

        except Exception as e:
            logger.error(f"Error calling OpenAI API with functions: {e}", exc_info=True)
            raise
