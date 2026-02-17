"""AgentRuntime 单元测试。"""

from decimal import Decimal
from pathlib import Path

import pytest

from simu_emperor.agents.context_builder import (
    ContextBuilder,
    DataScope,
    SkillScope,
)
from simu_emperor.agents.file_manager import FileManager
from simu_emperor.agents.llm.client import LLMClient
from simu_emperor.agents.llm.providers import ExecutionResult, MockProvider
from simu_emperor.agents.memory_manager import MemoryManager
from simu_emperor.agents.runtime import AgentRuntime, validate_effects
from simu_emperor.engine.models.effects import EffectOperation, EffectScope, EventEffect
from simu_emperor.engine.models.events import EventSource, PlayerEvent

from tests.conftest import make_national_data


# ── Fixtures ──


@pytest.fixture
def setup_runtime(tmp_path: Path) -> tuple[AgentRuntime, FileManager, str]:
    """创建完整的 AgentRuntime 测试环境。"""
    agent_base = tmp_path / "agent"
    template_base = tmp_path / "default_agents"
    skills_dir = tmp_path / "skills"
    agent_base.mkdir()
    template_base.mkdir()
    skills_dir.mkdir()

    fm = FileManager(agent_base, template_base, skills_dir)
    agent_id = "test_agent"

    # 创建 agent 文件
    agent_dir = agent_base / agent_id
    agent_dir.mkdir()
    (agent_dir / "soul.md").write_text("你是测试官员。", encoding="utf-8")
    (agent_dir / "data_scope.yaml").write_text(
        """\
display_name: 测试官员
skills:
  query_data:
    national: [imperial_treasury]
    provinces: all
    fields:
      - commerce.*
      - granary_stock
  write_report:
    inherits: query_data
  execute_command:
    national: [national_tax_modifier]
    provinces: all
    fields:
      - taxation.*
""",
        encoding="utf-8",
    )
    fm.ensure_agent_dirs(agent_id)

    # 创建 skill 文件
    (skills_dir / "query_data.md").write_text("# 查询数据", encoding="utf-8")
    (skills_dir / "write_report.md").write_text("# 撰写报告", encoding="utf-8")
    (skills_dir / "execute_command.md").write_text("# 执行命令", encoding="utf-8")

    provider = MockProvider()
    client = LLMClient(provider)
    cb = ContextBuilder(fm)
    mm = MemoryManager(fm)
    runtime = AgentRuntime(client, cb, mm, fm)

    return runtime, fm, agent_id


def _make_command(**overrides) -> PlayerEvent:
    defaults = {
        "turn_created": 1,
        "description": "调整税率",
        "command_type": "adjust_tax",
        "target_province_id": "zhili",
    }
    defaults.update(overrides)
    return PlayerEvent(**defaults)


# ── validate_effects 测试组 ──


class TestValidateEffects:
    def _make_data_scope(self) -> DataScope:
        return DataScope(
            display_name="测试",
            skills={
                "execute_command": SkillScope(
                    national=["national_tax_modifier"],
                    provinces="all",
                    fields=[
                        "taxation.land_tax_rate",
                        "taxation.commercial_tax_rate",
                        "taxation.tariff_rate",
                    ],
                ),
            },
        )

    def test_valid_effects_pass(self) -> None:
        effects = [
            EventEffect(
                target="taxation.land_tax_rate",
                operation=EffectOperation.ADD,
                value=Decimal("-0.01"),
                scope=EffectScope(province_ids=["zhili"]),
            ),
        ]
        ds = self._make_data_scope()
        result = validate_effects(effects, ds)
        assert len(result) == 1
        assert result[0].target == "taxation.land_tax_rate"

    def test_invalid_target_filtered(self) -> None:
        effects = [
            EventEffect(
                target="commerce.merchant_households",
                operation=EffectOperation.ADD,
                value=Decimal("100"),
                scope=EffectScope(province_ids=["zhili"]),
            ),
        ]
        ds = self._make_data_scope()
        result = validate_effects(effects, ds)
        assert len(result) == 0

    def test_national_field_allowed(self) -> None:
        effects = [
            EventEffect(
                target="national_tax_modifier",
                operation=EffectOperation.MULTIPLY,
                value=Decimal("1.1"),
                scope=EffectScope(is_national=True),
            ),
        ]
        ds = self._make_data_scope()
        result = validate_effects(effects, ds)
        assert len(result) == 1

    def test_province_mismatch_filtered(self) -> None:
        effects = [
            EventEffect(
                target="taxation.land_tax_rate",
                operation=EffectOperation.ADD,
                value=Decimal("-0.01"),
                scope=EffectScope(province_ids=["jiangnan"]),
            ),
        ]
        ds = self._make_data_scope()
        command = _make_command(target_province_id="zhili")
        result = validate_effects(effects, ds, command)
        assert len(result) == 0

    def test_province_match_passes(self) -> None:
        effects = [
            EventEffect(
                target="taxation.land_tax_rate",
                operation=EffectOperation.ADD,
                value=Decimal("-0.01"),
                scope=EffectScope(province_ids=["zhili"]),
            ),
        ]
        ds = self._make_data_scope()
        command = _make_command(target_province_id="zhili")
        result = validate_effects(effects, ds, command)
        assert len(result) == 1

    def test_no_execute_command_skill_returns_empty(self) -> None:
        effects = [
            EventEffect(
                target="taxation.land_tax_rate",
                operation=EffectOperation.ADD,
                value=Decimal("-0.01"),
            ),
        ]
        ds = DataScope(display_name="测试", skills={})
        result = validate_effects(effects, ds)
        assert len(result) == 0

    def test_mixed_valid_and_invalid(self) -> None:
        effects = [
            EventEffect(
                target="taxation.land_tax_rate",
                operation=EffectOperation.ADD,
                value=Decimal("-0.01"),
            ),
            EventEffect(
                target="commerce.merchant_households",
                operation=EffectOperation.ADD,
                value=Decimal("100"),
            ),
        ]
        ds = self._make_data_scope()
        result = validate_effects(effects, ds)
        assert len(result) == 1
        assert result[0].target == "taxation.land_tax_rate"

    def test_no_command_province_check_skipped(self) -> None:
        """无命令时不校验省份一致性。"""
        effects = [
            EventEffect(
                target="taxation.land_tax_rate",
                operation=EffectOperation.ADD,
                value=Decimal("-0.01"),
                scope=EffectScope(province_ids=["jiangnan"]),
            ),
        ]
        ds = self._make_data_scope()
        result = validate_effects(effects, ds)
        assert len(result) == 1


# ── AgentRuntime.summarize 测试组 ──


class TestSummarize:
    @pytest.mark.asyncio
    async def test_returns_report(
        self, setup_runtime: tuple[AgentRuntime, FileManager, str]
    ) -> None:
        runtime, fm, agent_id = setup_runtime
        data = make_national_data()
        report = await runtime.summarize(agent_id, 1, data)
        assert isinstance(report, str)
        assert len(report) > 0

    @pytest.mark.asyncio
    async def test_writes_workspace_file(
        self, setup_runtime: tuple[AgentRuntime, FileManager, str]
    ) -> None:
        runtime, fm, agent_id = setup_runtime
        data = make_national_data()
        await runtime.summarize(agent_id, 3, data)
        files = fm.list_workspace_files(agent_id)
        assert "003_report.md" in files

    @pytest.mark.asyncio
    async def test_writes_recent_memory(
        self, setup_runtime: tuple[AgentRuntime, FileManager, str]
    ) -> None:
        runtime, fm, agent_id = setup_runtime
        data = make_national_data()
        await runtime.summarize(agent_id, 5, data)
        memories = fm.list_recent_memories(agent_id)
        turns = [t for t, _ in memories]
        assert 5 in turns

    @pytest.mark.asyncio
    async def test_workspace_content_matches_report(
        self, setup_runtime: tuple[AgentRuntime, FileManager, str]
    ) -> None:
        runtime, fm, agent_id = setup_runtime
        data = make_national_data()
        report = await runtime.summarize(agent_id, 1, data)
        content = fm.read_workspace_file(agent_id, "001_report.md")
        assert content == report


# ── AgentRuntime.respond 测试组 ──


class TestRespond:
    @pytest.mark.asyncio
    async def test_returns_response(
        self, setup_runtime: tuple[AgentRuntime, FileManager, str]
    ) -> None:
        runtime, fm, agent_id = setup_runtime
        data = make_national_data()
        response = await runtime.respond(agent_id, 1, "国库还有多少银两？", data)
        assert isinstance(response, str)
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_custom_response(self, tmp_path: Path) -> None:
        """使用自定义 MockProvider 响应。"""
        agent_base = tmp_path / "agent"
        template_base = tmp_path / "default_agents"
        skills_dir = tmp_path / "skills"
        agent_base.mkdir()
        template_base.mkdir()
        skills_dir.mkdir()

        fm = FileManager(agent_base, template_base, skills_dir)
        agent_id = "hubu"

        agent_dir = agent_base / agent_id
        agent_dir.mkdir()
        (agent_dir / "soul.md").write_text("户部尚书", encoding="utf-8")
        (agent_dir / "data_scope.yaml").write_text(
            "display_name: 户部\nskills:\n  query_data:\n    fields: []\n",
            encoding="utf-8",
        )
        fm.ensure_agent_dirs(agent_id)
        (skills_dir / "query_data.md").write_text("# 查询", encoding="utf-8")

        provider = MockProvider(responses={"hubu": "回禀陛下，国库尚有五十万两白银。"})
        client = LLMClient(provider)
        cb = ContextBuilder(fm)
        mm = MemoryManager(fm)
        runtime = AgentRuntime(client, cb, mm, fm)

        response = await runtime.respond(agent_id, 1, "国库多少？", make_national_data())
        assert response == "回禀陛下，国库尚有五十万两白银。"


# ── AgentRuntime.execute 测试组 ──


class TestExecute:
    @pytest.mark.asyncio
    async def test_returns_agent_event(
        self, setup_runtime: tuple[AgentRuntime, FileManager, str]
    ) -> None:
        runtime, fm, agent_id = setup_runtime
        data = make_national_data()
        command = _make_command()
        event = await runtime.execute(agent_id, 1, command, data)
        assert event.source == EventSource.AGENT
        assert event.agent_id == agent_id
        assert event.agent_event_type == "adjust_tax"
        assert event.turn_created == 1

    @pytest.mark.asyncio
    async def test_writes_exec_workspace_file(
        self, setup_runtime: tuple[AgentRuntime, FileManager, str]
    ) -> None:
        runtime, fm, agent_id = setup_runtime
        data = make_national_data()
        command = _make_command()
        await runtime.execute(agent_id, 2, command, data)
        files = fm.list_workspace_files(agent_id)
        assert "002_exec_adjust_tax.md" in files

    @pytest.mark.asyncio
    async def test_valid_effects_preserved(self, tmp_path: Path) -> None:
        """有效 effects 应保留在 AgentEvent 中。"""
        agent_base = tmp_path / "agent"
        template_base = tmp_path / "default_agents"
        skills_dir = tmp_path / "skills"
        agent_base.mkdir()
        template_base.mkdir()
        skills_dir.mkdir()

        fm = FileManager(agent_base, template_base, skills_dir)
        agent_id = "executor"

        agent_dir = agent_base / agent_id
        agent_dir.mkdir()
        (agent_dir / "soul.md").write_text("执行官", encoding="utf-8")
        (agent_dir / "data_scope.yaml").write_text(
            """\
display_name: 执行官
skills:
  query_data:
    fields: []
  write_report:
    inherits: query_data
  execute_command:
    provinces: all
    fields:
      - taxation.land_tax_rate
      - taxation.commercial_tax_rate
      - taxation.tariff_rate
""",
            encoding="utf-8",
        )
        fm.ensure_agent_dirs(agent_id)
        (skills_dir / "query_data.md").write_text("# Q", encoding="utf-8")
        (skills_dir / "write_report.md").write_text("# W", encoding="utf-8")
        (skills_dir / "execute_command.md").write_text("# E", encoding="utf-8")

        valid_effect = EventEffect(
            target="taxation.land_tax_rate",
            operation=EffectOperation.ADD,
            value=Decimal("-0.01"),
            scope=EffectScope(province_ids=["zhili"]),
        )
        preset = ExecutionResult(
            narrative="臣已减税。",
            effects=[valid_effect],
            fidelity=Decimal("0.9"),
        )
        provider = MockProvider(structured_responses={"executor": preset})
        client = LLMClient(provider)
        cb = ContextBuilder(fm)
        mm = MemoryManager(fm)
        runtime = AgentRuntime(client, cb, mm, fm)

        command = _make_command(target_province_id="zhili")
        event = await runtime.execute(agent_id, 1, command, make_national_data())

        assert len(event.effects) == 1
        assert event.effects[0].target == "taxation.land_tax_rate"
        assert event.fidelity == Decimal("0.9")

    @pytest.mark.asyncio
    async def test_invalid_effects_cause_degradation(self, tmp_path: Path) -> None:
        """无效 effects 导致降级：fidelity=0 + 空效果。"""
        agent_base = tmp_path / "agent"
        template_base = tmp_path / "default_agents"
        skills_dir = tmp_path / "skills"
        agent_base.mkdir()
        template_base.mkdir()
        skills_dir.mkdir()

        fm = FileManager(agent_base, template_base, skills_dir)
        agent_id = "bad_agent"

        agent_dir = agent_base / agent_id
        agent_dir.mkdir()
        (agent_dir / "soul.md").write_text("坏官员", encoding="utf-8")
        (agent_dir / "data_scope.yaml").write_text(
            """\
display_name: 坏官员
skills:
  query_data:
    fields: []
  write_report:
    inherits: query_data
  execute_command:
    provinces: [zhili]
    fields:
      - taxation.land_tax_rate
""",
            encoding="utf-8",
        )
        fm.ensure_agent_dirs(agent_id)
        (skills_dir / "query_data.md").write_text("# Q", encoding="utf-8")
        (skills_dir / "write_report.md").write_text("# W", encoding="utf-8")
        (skills_dir / "execute_command.md").write_text("# E", encoding="utf-8")

        # 越权 effect：修改 commerce 字段（不在 execute_command.fields 中）
        bad_effect = EventEffect(
            target="commerce.merchant_households",
            operation=EffectOperation.ADD,
            value=Decimal("1000"),
            scope=EffectScope(province_ids=["zhili"]),
        )
        good_effect = EventEffect(
            target="taxation.land_tax_rate",
            operation=EffectOperation.ADD,
            value=Decimal("-0.01"),
            scope=EffectScope(province_ids=["zhili"]),
        )
        preset = ExecutionResult(
            narrative="臣已办理。",
            effects=[good_effect, bad_effect],
            fidelity=Decimal("0.8"),
        )
        provider = MockProvider(structured_responses={"bad_agent": preset})
        client = LLMClient(provider)
        cb = ContextBuilder(fm)
        mm = MemoryManager(fm)
        runtime = AgentRuntime(client, cb, mm, fm)

        command = _make_command(target_province_id="zhili")
        event = await runtime.execute(agent_id, 1, command, make_national_data())

        # 降级：fidelity=0，空效果
        assert event.fidelity == Decimal("0")
        assert event.effects == []

    @pytest.mark.asyncio
    async def test_default_mock_produces_valid_event(
        self, setup_runtime: tuple[AgentRuntime, FileManager, str]
    ) -> None:
        """默认 MockProvider 产出的 ExecutionResult（空效果）应通过校验。"""
        runtime, fm, agent_id = setup_runtime
        data = make_national_data()
        command = _make_command()
        event = await runtime.execute(agent_id, 1, command, data)
        # MockProvider 默认返回空 effects，校验通过
        assert event.fidelity == Decimal("1.0")
        assert event.effects == []
