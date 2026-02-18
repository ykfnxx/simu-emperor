"""LLM Provider 层单元测试。"""

from decimal import Decimal
from typing import Any

import pytest

from simu_emperor.agents.context_builder import AgentContext
from simu_emperor.agents.llm.client import LLMClient
from simu_emperor.agents.llm.providers import (
    ExecutionResult,
    MockProvider,
    build_system_prompt,
    build_user_prompt,
)
from simu_emperor.engine.models.effects import EffectOperation, EffectScope, EventEffect


# ── Fixtures ──


def _make_context(**overrides: Any) -> AgentContext:
    defaults: dict[str, Any] = {
        "agent_id": "hubu_shangshu",
        "soul": "你是户部尚书，掌管天下财赋。",
        "skill": "# 查询数据\n请汇报当前财政状况。",
        "data": {"national": {"imperial_treasury": "500000"}},
        "memory_summary": None,
        "recent_memories": [],
    }
    defaults.update(overrides)
    return AgentContext(**defaults)


# ── MockProvider 测试组 ──


class TestMockProvider:
    @pytest.mark.asyncio
    async def test_default_response_contains_agent_id(self) -> None:
        provider = MockProvider()
        ctx = _make_context()
        result = await provider.generate(ctx)
        assert "hubu_shangshu" in result

    @pytest.mark.asyncio
    async def test_default_response_contains_skill_info(self) -> None:
        provider = MockProvider()
        ctx = _make_context()
        result = await provider.generate(ctx)
        assert "MockProvider" in result

    @pytest.mark.asyncio
    async def test_custom_response_by_agent_id(self) -> None:
        provider = MockProvider(responses={"hubu_shangshu": "国库充盈，陛下放心。"})
        ctx = _make_context()
        result = await provider.generate(ctx)
        assert result == "国库充盈，陛下放心。"

    @pytest.mark.asyncio
    async def test_custom_response_different_agent(self) -> None:
        provider = MockProvider(responses={"other_agent": "其他回复"})
        ctx = _make_context()
        result = await provider.generate(ctx)
        # 未匹配的 agent_id 应返回默认响应
        assert "hubu_shangshu" in result

    @pytest.mark.asyncio
    async def test_structured_default_execution_result(self) -> None:
        provider = MockProvider()
        ctx = _make_context()
        result = await provider.generate_structured(ctx, ExecutionResult)
        assert isinstance(result, ExecutionResult)
        assert result.fidelity == Decimal("1.0")
        assert result.effects == []
        assert "hubu_shangshu" in result.narrative

    @pytest.mark.asyncio
    async def test_structured_custom_response_model_instance(self) -> None:
        preset = ExecutionResult(
            narrative="臣已遵旨办理。",
            effects=[],
            fidelity=Decimal("0.8"),
        )
        provider = MockProvider(structured_responses={"hubu_shangshu": preset})
        ctx = _make_context()
        result = await provider.generate_structured(ctx, ExecutionResult)
        assert result.narrative == "臣已遵旨办理。"
        assert result.fidelity == Decimal("0.8")

    @pytest.mark.asyncio
    async def test_structured_custom_response_dict(self) -> None:
        provider = MockProvider(
            structured_responses={
                "hubu_shangshu": {
                    "narrative": "减税已办。",
                    "effects": [],
                    "fidelity": Decimal("0.9"),
                }
            }
        )
        ctx = _make_context()
        result = await provider.generate_structured(ctx, ExecutionResult)
        assert result.narrative == "减税已办。"
        assert result.fidelity == Decimal("0.9")


# ── Prompt 组装测试组 ──


class TestBuildSystemPrompt:
    def test_contains_soul(self) -> None:
        ctx = _make_context(soul="你是兵部尚书，掌管天下军务。")
        prompt = build_system_prompt(ctx)
        assert prompt == "你是兵部尚书，掌管天下军务。"


class TestBuildUserPrompt:
    def test_contains_skill(self) -> None:
        ctx = _make_context()
        prompt = build_user_prompt(ctx)
        assert "技能指令" in prompt
        assert "查询数据" in prompt

    def test_contains_data(self) -> None:
        ctx = _make_context(data={"national": {"imperial_treasury": "500000"}})
        prompt = build_user_prompt(ctx)
        assert "数据" in prompt
        assert "imperial_treasury" in prompt
        assert "500000" in prompt

    def test_contains_memory_summary(self) -> None:
        ctx = _make_context(memory_summary="上回合国库收入减少。")
        prompt = build_user_prompt(ctx)
        assert "长期记忆" in prompt
        assert "上回合国库收入减少" in prompt

    def test_contains_recent_memories(self) -> None:
        ctx = _make_context(recent_memories=[(3, "第三回合记忆"), (4, "第四回合记忆")])
        prompt = build_user_prompt(ctx)
        assert "近期记忆" in prompt
        assert "回合 3: 第三回合记忆" in prompt
        assert "回合 4: 第四回合记忆" in prompt

    def test_no_memory_section_when_empty(self) -> None:
        ctx = _make_context(memory_summary=None, recent_memories=[])
        prompt = build_user_prompt(ctx)
        assert "记忆" not in prompt

    def test_no_data_section_when_empty(self) -> None:
        ctx = _make_context(data={})
        prompt = build_user_prompt(ctx)
        assert "## 数据" not in prompt


# ── LLMClient 测试组 ──


class TestLLMClient:
    @pytest.mark.asyncio
    async def test_generate_delegates_to_provider(self) -> None:
        provider = MockProvider(responses={"test_agent": "委托响应"})
        client = LLMClient(provider)
        ctx = _make_context(agent_id="test_agent")
        result = await client.generate(ctx)
        assert result == "委托响应"

    @pytest.mark.asyncio
    async def test_generate_structured_delegates_to_provider(self) -> None:
        provider = MockProvider()
        client = LLMClient(provider)
        ctx = _make_context()
        result = await client.generate_structured(ctx, ExecutionResult)
        assert isinstance(result, ExecutionResult)

    @pytest.mark.asyncio
    async def test_provider_attribute_accessible(self) -> None:
        provider = MockProvider()
        client = LLMClient(provider)
        assert client.provider is provider


# ── ExecutionResult 测试组 ──


class TestExecutionResult:
    def test_basic_creation(self) -> None:
        result = ExecutionResult(
            narrative="臣已遵旨办理减税事宜。",
            effects=[],
            fidelity=Decimal("0.85"),
        )
        assert result.narrative == "臣已遵旨办理减税事宜。"
        assert result.fidelity == Decimal("0.85")
        assert result.effects == []

    def test_fidelity_boundary_zero(self) -> None:
        result = ExecutionResult(
            narrative="臣无能为力。",
            effects=[],
            fidelity=Decimal("0"),
        )
        assert result.fidelity == Decimal("0")

    def test_fidelity_boundary_one(self) -> None:
        result = ExecutionResult(
            narrative="臣已完美执行。",
            effects=[],
            fidelity=Decimal("1"),
        )
        assert result.fidelity == Decimal("1")

    def test_fidelity_out_of_range(self) -> None:
        with pytest.raises(ValueError):
            ExecutionResult(
                narrative="test",
                effects=[],
                fidelity=Decimal("1.5"),
            )

    def test_with_event_effects(self) -> None:
        effects = [
            EventEffect(
                target="taxation.land_tax_rate",
                operation=EffectOperation.ADD,
                value=Decimal("-0.01"),
                scope=EffectScope(province_ids=["zhili"]),
            ),
            EventEffect(
                target="commerce.market_prosperity",
                operation=EffectOperation.MULTIPLY,
                value=Decimal("1.05"),
                scope=EffectScope(province_ids=["zhili"]),
            ),
        ]
        result = ExecutionResult(
            narrative="臣已减税并促进商业。",
            effects=effects,
            fidelity=Decimal("0.9"),
        )
        assert len(result.effects) == 2
        assert result.effects[0].target == "taxation.land_tax_rate"
        assert result.effects[1].operation == EffectOperation.MULTIPLY
