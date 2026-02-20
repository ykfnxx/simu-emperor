"""LLM 调用封装：统一入口，预留重试/日志/限流扩展点。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TypeVar

from pydantic import BaseModel

from simu_emperor.agents.context_builder import AgentContext
from simu_emperor.agents.llm.providers import LLMProvider

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """LLM 调用客户端，委托给具体 Provider。"""

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def generate(self, context: AgentContext) -> str:
        """调用 LLM 生成文本。"""
        return await self.provider.generate(context)

    async def generate_stream(self, context: AgentContext) -> AsyncIterator[str]:
        """流式调用 LLM 生成文本。"""
        async for chunk in self.provider.generate_stream(context):
            yield chunk

    async def generate_structured(self, context: AgentContext, response_model: type[T]) -> T:
        """调用 LLM 生成结构化输出。"""
        return await self.provider.generate_structured(context, response_model)
