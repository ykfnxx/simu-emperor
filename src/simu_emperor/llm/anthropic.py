"""
Anthropic Claude LLM 提供商
"""

import logging
import time

from simu_emperor.llm.base import LLMProvider
from simu_emperor.llm.metrics import (
    llm_requests_total,
    llm_request_duration_seconds,
    llm_tokens_used_total,
    llm_active_requests,
)

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

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        context_window: int | None = None,
    ):
        """
        初始化 Anthropic 提供商

        Args:
            api_key: Anthropic API 密钥
            model: 模型名称（默认 claude-sonnet-4-20250514）
            context_window: 上下文窗口大小（可选，从配置读取）
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package is required. Install with: pip install anthropic")

        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self._context_window = context_window
        logger.info(f"AnthropicProvider initialized with model: {model}")

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
        task_type: str | None = None,
    ) -> str:
        """
        调用 Claude API

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            temperature: 温度参数（0-1）
            max_tokens: 最大生成 token 数
            task_type: 任务类型（用于监控）

        Returns:
            Claude 响应文本
        """
        task_label = task_type or "unknown"
        llm_active_requests.labels(provider="anthropic", model=self.model).inc()
        start_time = time.time()

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

            # 记录 token 使用
            llm_tokens_used_total.labels(
                provider="anthropic", model=self.model, task_type=task_label, token_type="input"
            ).inc(response.usage.input_tokens)
            llm_tokens_used_total.labels(
                provider="anthropic", model=self.model, task_type=task_label, token_type="output"
            ).inc(response.usage.output_tokens)

            # 记录成功
            llm_requests_total.labels(
                provider="anthropic", model=self.model, task_type=task_label, status="success"
            ).inc()

            content = response.content[0].text
            return content

        except Exception as e:
            llm_requests_total.labels(
                provider="anthropic", model=self.model, task_type=task_label, status="error"
            ).inc()
            logger.error(f"Error calling Anthropic API: {e}", exc_info=True)
            raise
        finally:
            duration = time.time() - start_time
            llm_request_duration_seconds.labels(
                provider="anthropic", model=self.model, task_type=task_label
            ).observe(duration)
            llm_active_requests.labels(provider="anthropic", model=self.model).dec()

    async def call_with_functions(
        self,
        prompt: str,
        functions: list[dict],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        task_type: str | None = None,
    ) -> dict:
        """
        调用 Claude API 并支持 function calling (tool use)

        Args:
            prompt: 用户提示词
            functions: 可用函数列表（需要转换为 Anthropic 格式）
            system_prompt: 系统提示词（可选）
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            task_type: 任务类型（用于监控）

        Returns:
            包含 response_text 和 tool_calls 的字典
        """
        task_label = task_type or "unknown"
        llm_active_requests.labels(provider="anthropic", model=self.model).inc()
        start_time = time.time()

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

            # 记录 token 使用
            llm_tokens_used_total.labels(
                provider="anthropic", model=self.model, task_type=task_label, token_type="input"
            ).inc(response.usage.input_tokens)
            llm_tokens_used_total.labels(
                provider="anthropic", model=self.model, task_type=task_label, token_type="output"
            ).inc(response.usage.output_tokens)

            # 记录成功
            llm_requests_total.labels(
                provider="anthropic", model=self.model, task_type=task_label, status="success"
            ).inc()

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
            llm_requests_total.labels(
                provider="anthropic", model=self.model, task_type=task_label, status="error"
            ).inc()
            logger.error(f"Error calling Anthropic API with functions: {e}", exc_info=True)
            raise
        finally:
            duration = time.time() - start_time
            llm_request_duration_seconds.labels(
                provider="anthropic", model=self.model, task_type=task_label
            ).observe(duration)
            llm_active_requests.labels(provider="anthropic", model=self.model).dec()
