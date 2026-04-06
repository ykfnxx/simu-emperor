"""OpenAI provider."""

from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from simu_shared.models import LLMConfig
from simu_sdk.llm.base import LLMProvider, LLMResponse, ToolCall


class OpenAIProvider(LLMProvider):
    """Calls OpenAI-compatible APIs (GPT, etc.)."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        kwargs: dict[str, Any] = {"api_key": config.api_key}
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self._client = AsyncOpenAI(**kwargs)

    async def call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
    ) -> LLMResponse:
        full_messages = list(messages)
        if system:
            full_messages.insert(0, {"role": "system", "content": system})

        kwargs: dict[str, Any] = {
            "model": self._config.model,
            "max_tokens": self._config.max_tokens,
            "temperature": self._config.temperature,
            "messages": full_messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        msg = choice.message

        tool_calls: list[ToolCall] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments) if tc.function.arguments else {},
                ))

        return LLMResponse(
            content=msg.content or "",
            tool_calls=tool_calls,
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            },
        )

    async def close(self) -> None:
        await self._client.close()
