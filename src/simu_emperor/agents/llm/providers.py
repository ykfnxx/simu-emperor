"""LLM Provider 抽象 + 实现（Mock/Anthropic/OpenAI）。"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from simu_emperor.agents.context_builder import AgentContext
from simu_emperor.engine.models.effects import EventEffect
from simu_emperor.utils.logger import log_llm_request, log_llm_response

T = TypeVar("T", bound=BaseModel)


# ── ExecutionResult 结构化输出 ──


class ExecutionResult(BaseModel):
    """Agent 执行结果：narrative + effects + fidelity。"""

    narrative: str = Field(description="奏折风格自然语言描述")
    effects: list[EventEffect] = Field(default_factory=list, description="结构化效果列表")
    fidelity: Decimal = Field(ge=0, le=1, description="LLM 自评执行忠诚度 (0-1)")


# ── Prompt 组装辅助函数 ──


def build_system_prompt(context: AgentContext) -> str:
    """从 AgentContext 组装 system prompt（soul + rule 部分）。"""
    parts = []
    if context.rule:
        parts.append(context.rule)
        parts.append("")
    parts.append(context.soul)
    return "\n".join(parts)


def build_user_prompt(context: AgentContext) -> str:
    """从 AgentContext 组装 user prompt（skill + data + memory）。

    格式：
    ## 技能指令
    {skill}

    ## 数据
    {data}

    ## 记忆
    ### 长期记忆
    {memory_summary}

    ### 近期记忆
    回合 {turn}: {content}
    """
    parts: list[str] = []

    # Skill 指令
    parts.append("## 技能指令")
    parts.append(context.skill)

    # 数据
    if context.data:
        parts.append("")
        parts.append("## 数据")
        parts.append(_format_data(context.data))

    # 记忆
    has_memory = context.memory_summary or context.recent_memories
    if has_memory:
        parts.append("")
        parts.append("## 记忆")

        if context.memory_summary:
            parts.append("")
            parts.append("### 长期记忆")
            parts.append(context.memory_summary)

        if context.recent_memories:
            parts.append("")
            parts.append("### 近期记忆")
            for turn, content in context.recent_memories:
                parts.append(f"回合 {turn}: {content}")

    return "\n".join(parts)


def _format_data(data: dict[str, Any], indent: int = 0) -> str:
    """递归格式化数据字典为可读文本。"""
    lines: list[str] = []
    prefix = "  " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}- {key}:")
            lines.append(_format_data(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}- {key}:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(_format_data(item, indent + 1))
                else:
                    lines.append(f"{prefix}  - {item}")
        else:
            lines.append(f"{prefix}- {key}: {value}")
    return "\n".join(lines)


# ── LLMProvider 抽象基类 ──


class LLMProvider(ABC):
    """LLM 调用抽象接口。"""

    @abstractmethod
    async def generate(self, context: AgentContext) -> str:
        """生成自由文本响应（用于 summarize/respond 阶段）。"""

    @abstractmethod
    async def generate_structured(self, context: AgentContext, response_model: type[T]) -> T:
        """生成结构化输出（用于 execute 阶段的 ExecutionResult）。"""

    async def generate_stream(self, context: AgentContext) -> AsyncIterator[str]:
        """流式生成文本响应。默认实现为非流式，子类可覆盖。"""
        yield await self.generate(context)


# ── MockProvider ──


class MockProvider(LLMProvider):
    """测试用确定性 Provider。"""

    def __init__(
        self,
        responses: dict[str, str] | None = None,
        structured_responses: dict[str, Any] | None = None,
    ) -> None:
        self._responses = responses or {}
        self._structured_responses = structured_responses or {}

    async def generate(self, context: AgentContext) -> str:
        """按 agent_id 查找预设响应，无预设时返回默认响应。"""
        start_time = log_llm_request(
            provider="mock",
            model="mock-model",
            messages=[],
            agent_id=context.agent_id,
        )
        if context.agent_id in self._responses:
            result = self._responses[context.agent_id]
        else:
            result = f"[MockProvider] agent={context.agent_id} skill={context.skill[:50]}"
        log_llm_response(
            provider="mock",
            tokens=len(result),
            latency_ms=(time.time() - start_time) * 1000,
            agent_id=context.agent_id,
        )
        return result

    async def generate_stream(self, context: AgentContext) -> AsyncIterator[str]:
        """模拟流式输出，逐字符返回。"""
        text = await self.generate(context)
        # 模拟打字机效果，每次返回一个字符
        for char in text:
            yield char

    async def generate_structured(self, context: AgentContext, response_model: type[T]) -> T:
        """按 agent_id 查找预设结构化响应，无预设时返回默认实例。"""
        start_time = log_llm_request(
            provider="mock",
            model="mock-model",
            messages=[],
            agent_id=context.agent_id,
        )
        if context.agent_id in self._structured_responses:
            preset = self._structured_responses[context.agent_id]
            if isinstance(preset, response_model):
                result = preset
            # 如果是 dict，构造模型实例
            elif isinstance(preset, dict):
                result = response_model(**preset)
            else:
                result = self._default_structured_response(context, response_model)
        else:
            result = self._default_structured_response(context, response_model)

        log_llm_response(
            provider="mock",
            tokens=0,
            latency_ms=(time.time() - start_time) * 1000,
            agent_id=context.agent_id,
        )
        return result  # type: ignore[return-value]

    def _default_structured_response(self, context: AgentContext, response_model: type[T]) -> T:
        """生成默认结构化响应。"""
        # 默认返回 ExecutionResult 或尝试构造 response_model 的默认实例
        if response_model is ExecutionResult:
            return response_model(  # type: ignore[return-value]
                narrative=f"[MockProvider] 默认执行报告 agent={context.agent_id}",
                effects=[],
                fidelity=Decimal("1.0"),
            )
        # 对于其他模型，尝试无参构造
        return response_model()  # type: ignore[call-arg]


# ── AnthropicProvider ──


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API Provider。"""

    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514") -> None:
        import anthropic

        self._model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def generate(self, context: AgentContext) -> str:
        """调用 Anthropic Messages API 生成文本。"""
        system_prompt = build_system_prompt(context)
        user_prompt = build_user_prompt(context)
        messages = [{"role": "user", "content": user_prompt}]

        start_time = log_llm_request(
            provider="anthropic",
            model=self._model,
            messages=messages,
            agent_id=context.agent_id,
        )

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
        )
        # 提取文本内容
        text = response.content[0].text  # type: ignore[union-attr]

        log_llm_response(
            provider="anthropic",
            tokens=response.usage.input_tokens + response.usage.output_tokens,
            latency_ms=(time.time() - start_time) * 1000,
            agent_id=context.agent_id,
        )
        return text

    async def generate_stream(self, context: AgentContext) -> AsyncIterator[str]:
        """调用 Anthropic Messages Stream API 流式生成文本。"""
        system_prompt = build_system_prompt(context)
        user_prompt = build_user_prompt(context)

        async with self._client.messages.stream(
            model=self._model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def generate_structured(self, context: AgentContext, response_model: type[T]) -> T:
        """使用 instructor 包装 Anthropic client 获取结构化输出。"""
        import instructor

        client = instructor.from_anthropic(self._client)
        system_prompt = build_system_prompt(context)
        user_prompt = build_user_prompt(context)

        return await client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            response_model=response_model,
        )


# ── OpenAIProvider ──


class OpenAIProvider(LLMProvider):
    """OpenAI API Provider（支持兼容 OpenAI 格式的服务）。"""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o",
        base_url: str | None = None,
    ) -> None:
        import openai

        self._model = model
        self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def generate(self, context: AgentContext) -> str:
        """调用 OpenAI Chat Completions API 生成文本。"""
        system_prompt = build_system_prompt(context)
        user_prompt = build_user_prompt(context)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        start_time = log_llm_request(
            provider="openai",
            model=self._model,
            messages=messages,
            agent_id=context.agent_id,
        )

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        text = response.choices[0].message.content or ""

        tokens = 0
        if response.usage:
            tokens = response.usage.total_tokens

        log_llm_response(
            provider="openai",
            tokens=tokens,
            latency_ms=(time.time() - start_time) * 1000,
            agent_id=context.agent_id,
        )
        return text

    async def generate_stream(self, context: AgentContext) -> AsyncIterator[str]:
        """调用 OpenAI Chat Completions API 流式生成文本。"""
        system_prompt = build_system_prompt(context)
        user_prompt = build_user_prompt(context)

        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def generate_structured(self, context: AgentContext, response_model: type[T]) -> T:
        """生成结构化输出。

        优先使用 instructor（function calling），若失败则降级为 JSON 模式解析。
        某些模型（如 Qwen thinking 模式）不支持 tool_choice 参数。
        """
        import json

        system_prompt = build_system_prompt(context)
        user_prompt = build_user_prompt(context)

        # 获取 Pydantic 模型的 JSON schema
        schema = response_model.model_json_schema()

        # 构建要求 JSON 输出的 prompt
        json_instruction = (
            f"\n\n请严格按照以下 JSON Schema 格式输出，不要输出其他内容：\n"
            f"```json\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n```\n"
            f"只输出 JSON 对象，不要包含 ```json``` 标记。"
        )

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt + json_instruction},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content or ""

        # 提取 JSON（处理可能包含的 markdown 代码块）
        content = content.strip()
        if content.startswith("```"):
            # 移除 markdown 代码块标记
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        # 解析 JSON 并构造模型实例
        data = json.loads(content)
        return response_model(**data)
