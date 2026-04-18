"""LLM provider interface and factory."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from simu_shared.models import LLMConfig


@dataclass
class ToolCall:
    """A single tool call requested by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Parsed response from an LLM call."""

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMProvider(ABC):
    """Abstract interface for LLM backends."""

    #: Message format style: "anthropic" or "openai"
    message_format: str = "openai"

    @abstractmethod
    async def call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
    ) -> LLMResponse: ...

    @abstractmethod
    async def close(self) -> None: ...


def create_llm_provider(config: LLMConfig) -> LLMProvider:
    """Factory that returns the appropriate provider for *config*.

    Uses any-llm-sdk for all real providers (anthropic, openai, deepseek,
    groq, etc.).  Only ``mock`` is handled separately for testing.
    """
    if config.provider == "mock":
        from simu_sdk.llm.mock import MockProvider

        return MockProvider(config)

    from simu_sdk.llm.any_llm_provider import AnyLLMProvider

    return AnyLLMProvider(config)
