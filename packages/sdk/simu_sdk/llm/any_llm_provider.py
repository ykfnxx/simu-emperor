"""Unified LLM provider via any-llm-sdk.

Supports all providers (anthropic, openai, deepseek, groq, etc.)
through a single implementation. Responses are normalized to OpenAI
ChatCompletion format by any-llm-sdk.
"""

from __future__ import annotations

import json
from typing import Any

from any_llm import acompletion

from simu_shared.models import LLMConfig
from simu_sdk.llm.base import LLMProvider, LLMResponse, ToolCall


class AnyLLMProvider(LLMProvider):
    """LLM provider backed by any-llm-sdk.

    All providers use OpenAI message format — any-llm-sdk handles
    conversion to/from provider-native formats (e.g. Anthropic tool_use).
    """

    message_format = "openai"

    def __init__(self, config: LLMConfig) -> None:
        self._model = config.model
        self._provider = config.provider
        self._api_key = config.api_key
        self._api_base = config.base_url
        self._temperature = config.temperature
        self._max_tokens = config.max_tokens

    async def call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
    ) -> LLMResponse:
        full_messages = list(messages)
        if system:
            full_messages.insert(0, {"role": "system", "content": system})

        response = await acompletion(
            model=self._model,
            provider=self._provider,
            messages=full_messages,
            tools=tools or None,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            api_key=self._api_key,
            api_base=self._api_base,
        )

        choice = response.choices[0]
        msg = choice.message

        tool_calls: list[ToolCall] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments)
                        if tc.function.arguments
                        else {},
                    )
                )

        return LLMResponse(
            content=msg.content or "",
            tool_calls=tool_calls,
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            },
        )

    async def close(self) -> None:
        pass  # acompletion manages clients internally
