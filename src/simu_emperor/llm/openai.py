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

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        base_url: str | None = None,
        context_window: int | None = None,
    ):
        """
        初始化 OpenAI 提供商

        Args:
            api_key: OpenAI API 密钥
            model: 模型名称（默认 gpt-4）
            base_url: API Base URL（可选，用于兼容 OpenAI 格式的服务）
            context_window: 上下文窗口大小（可选，从配置读取）
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package is required. Install with: pip install openai")

        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = openai.AsyncOpenAI(**client_kwargs)
        self.model = model
        self._context_window = context_window
        logger.info(
            f"OpenAIProvider initialized with model: {model}, base_url: {base_url or 'default'}"
        )

    def get_context_window_size(self) -> int:
        """
        获取当前模型的上下文窗口大小

        从配置文件读取统一值。

        Returns:
            上下文窗口大小（token 数）
        """
        if self._context_window:
            return self._context_window

        # 后备：使用保守默认值
        return 8000

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
                tools = [{"type": "function", "function": func} for func in functions]

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
                # Debug: 打印 tools 结构
                logger.debug(f"Tools being sent to GLM API:")
                for i, tool in enumerate(tools):
                    logger.debug(f"  Tool {i}: type={tool.get('type')}, name={tool.get('function', {}).get('name')}")

            response = await self.client.chat.completions.create(**api_params)

            message = response.choices[0].message

            # 提取 tool_calls
            tool_calls = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append(
                        {
                            "id": tc.id,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                    )

            return {"response_text": message.content or "", "tool_calls": tool_calls}

        except Exception as e:
            logger.error(f"Error calling OpenAI API with functions: {e}", exc_info=True)
            raise
