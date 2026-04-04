"""Mock LLM provider for testing."""

from __future__ import annotations

from typing import Any

from simu_shared.models import LLMConfig
from simu_sdk.llm.base import LLMProvider, LLMResponse


class MockProvider(LLMProvider):
    """Returns canned responses. Useful for tests and local dev."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self.call_history: list[dict[str, Any]] = []
        self.next_responses: list[LLMResponse] = []

    def enqueue_response(self, response: LLMResponse) -> None:
        """Pre-load a response to be returned on the next call."""
        self.next_responses.append(response)

    async def call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
    ) -> LLMResponse:
        self.call_history.append({
            "messages": messages,
            "tools": tools,
            "system": system,
        })
        if self.next_responses:
            return self.next_responses.pop(0)
        return LLMResponse(content="[Mock response]")

    async def close(self) -> None:
        pass
