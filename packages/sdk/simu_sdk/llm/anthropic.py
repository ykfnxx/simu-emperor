"""Anthropic Claude provider."""

from __future__ import annotations

import json
from typing import Any

from anthropic import AsyncAnthropic

from simu_shared.models import LLMConfig
from simu_sdk.llm.base import LLMProvider, LLMResponse, ToolCall


class AnthropicProvider(LLMProvider):
    """Calls Claude via the Anthropic Python SDK."""

    message_format = "anthropic"

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._client = AsyncAnthropic(api_key=config.api_key)

    async def call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self._config.model,
            "max_tokens": self._config.max_tokens,
            "temperature": self._config.temperature,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = _convert_tools_to_anthropic(tools)

        response = await self._client.messages.create(**kwargs)

        content = ""
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input if isinstance(block.input, dict) else {},
                ))

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )

    async def close(self) -> None:
        await self._client.close()


def _convert_tools_to_anthropic(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert OpenAI-style function defs to Anthropic tool format."""
    result = []
    for t in tools:
        func = t.get("function", t)
        result.append({
            "name": func["name"],
            "description": func.get("description", ""),
            "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
        })
    return result
