"""Agent 三阶段流水线集成测试（MockProvider + 文件系统 + SQLite）。"""

from decimal import Decimal
from pathlib import Path

import pytest

from simu_emperor.agents.context_builder import ContextBuilder
from simu_emperor.agents.file_manager import FileManager
from simu_emperor.agents.llm.client import LLMClient
from simu_emperor.agents.llm.providers import ExecutionResult, MockProvider
from simu_emperor.agents.memory_manager import MemoryManager
from simu_emperor.agents.runtime import AgentRuntime
from simu_emperor.engine.models.effects import EffectOperation, EffectScope, EventEffect
from simu_emperor.engine.models.events import EventSource, PlayerEvent
from simu_emperor.persistence.database import init_database

from tests.conftest import make_national_data


@pytest.fixture
async def db_conn(tmp_path: Path):
    """创建临时 SQLite 数据库。"""
    db_path = str(tmp_path / "test.db")
    conn = await init_database(db_path)
    yield conn
    await conn.close()


@pytest.fixture
def agent_env(tmp_path: Path) -> tuple[AgentRuntime, FileManager, str, str]:
    """创建完整的 agent 环境，返回 (runtime, fm, agent_id_1, agent_id_2)。"""
    agent_base = tmp_path / "agent"
    template_base = tmp_path / "default_agents"
    skills_dir = tmp_path / "skills"
    agent_base.mkdir()
    template_base.mkdir()
    skills_dir.mkdir()

    fm = FileManager(agent_base, template_base, skills_dir)

    # 创建 skill 文件
    (skills_dir / "query_data.md").write_text("# 查询数据\n请汇报数据。", encoding="utf-8")
    (skills_dir / "write_report.md").write_text("# 撰写报告\n请撰写本回合报告。", encoding="utf-8")
    (skills_dir / "execute_command.md").write_text(
        "# 执行命令\n请执行皇帝的命令。", encoding="utf-8"
    )

    # Agent 1: 户部尚书
    agent1 = "minister_of_revenue"
    d1 = agent_base / agent1
    d1.mkdir()
    (d1 / "soul.md").write_text(
        "你是户部尚书张廷玉，掌管天下财赋。性格谨慎，偶有贪墨倾向。",
        encoding="utf-8",
    )
    (d1 / "data_scope.yaml").write_text(
        """\
display_name: 户部尚书
skills:
  query_data:
    national: [imperial_treasury, national_tax_modifier]
    provinces: all
    fields:
      - commerce.*
      - taxation.*
      - granary_stock
      - local_treasury
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
    fm.ensure_agent_dirs(agent1)

    # Agent 2: 直隶巡抚
    agent2 = "governor_zhili"
    d2 = agent_base / agent2
    d2.mkdir()
    (d2 / "soul.md").write_text(
        "你是直隶巡抚李卫，忠心耿耿但好夸大困难以争取资源。",
        encoding="utf-8",
    )
    (d2 / "data_scope.yaml").write_text(
        """\
display_name: 直隶巡抚
skills:
  query_data:
    provinces: [zhili]
    fields:
      - population.*
      - agriculture.*
      - commerce.*
      - granary_stock
      - local_treasury
  write_report:
    inherits: query_data
  execute_command:
    provinces: [zhili]
    fields:
      - agriculture.irrigation_level
      - taxation.commercial_tax_rate
      - granary_stock
""",
        encoding="utf-8",
    )
    fm.ensure_agent_dirs(agent2)

    # 带预设响应的 MockProvider
    provider = MockProvider(
        responses={
            "minister_of_revenue": "回禀陛下，本回合国库收入稳定，商税略有增长。",
            "governor_zhili": "启禀陛下，直隶本回合风调雨顺，粮仓充足。",
        },
        structured_responses={
            "minister_of_revenue": ExecutionResult(
                narrative="臣已遵旨调整税率。",
                effects=[
                    EventEffect(
                        target="taxation.land_tax_rate",
                        operation=EffectOperation.ADD,
                        value=Decimal("-0.005"),
                        scope=EffectScope(province_ids=["zhili"]),
                    ),
                ],
                fidelity=Decimal("0.85"),
            ),
            "governor_zhili": ExecutionResult(
                narrative="臣已着手修缮直隶水利。",
                effects=[
                    EventEffect(
                        target="agriculture.irrigation_level",
                        operation=EffectOperation.ADD,
                        value=Decimal("0.05"),
                        scope=EffectScope(province_ids=["zhili"]),
                    ),
                ],
                fidelity=Decimal("0.95"),
            ),
        },
    )
    client = LLMClient(provider)
    cb = ContextBuilder(fm)
    mm = MemoryManager(fm)
    runtime = AgentRuntime(client, cb, mm, fm)

    return runtime, fm, agent1, agent2


class TestThreePhasePipeline:
    """三阶段完整流程集成测试。"""

    @pytest.mark.asyncio
    async def test_summarize_then_respond_then_execute(
        self, agent_env: tuple[AgentRuntime, FileManager, str, str]
    ) -> None:
        """单个 agent 完整三阶段流程。"""
        runtime, fm, agent1, _ = agent_env
        data = make_national_data()
        turn = 1

        # Phase 1: summarize
        report = await runtime.summarize(agent1, turn, data)
        assert "国库收入稳定" in report

        # 验证 workspace 文件
        files = fm.list_workspace_files(agent1)
        assert "001_report.md" in files

        # 验证记忆写入
        memories = fm.list_recent_memories(agent1)
        assert any(t == 1 for t, _ in memories)

        # Phase 2: respond
        response = await runtime.respond(agent1, turn, "商税情况如何？", data)
        assert isinstance(response, str)
        assert len(response) > 0

        # Phase 3: execute
        command = PlayerEvent(
            turn_created=turn,
            description="减税以安民心",
            command_type="adjust_tax",
            target_province_id="zhili",
        )
        event = await runtime.execute(agent1, turn, command, data)

        assert event.source == EventSource.AGENT
        assert event.agent_id == agent1
        assert event.agent_event_type == "adjust_tax"
        assert event.fidelity == Decimal("0.85")
        assert len(event.effects) == 1
        assert event.effects[0].target == "taxation.land_tax_rate"

        # 验证执行 workspace 文件
        files = fm.list_workspace_files(agent1)
        assert "001_exec_adjust_tax.md" in files

    @pytest.mark.asyncio
    async def test_two_agents_independent(
        self, agent_env: tuple[AgentRuntime, FileManager, str, str]
    ) -> None:
        """两个 agent 独立执行三阶段。"""
        runtime, fm, agent1, agent2 = agent_env
        data = make_national_data()
        turn = 1

        # Agent 1: summarize
        report1 = await runtime.summarize(agent1, turn, data)
        assert "国库收入稳定" in report1

        # Agent 2: summarize
        report2 = await runtime.summarize(agent2, turn, data)
        assert "风调雨顺" in report2

        # 各自 workspace 独立
        files1 = fm.list_workspace_files(agent1)
        files2 = fm.list_workspace_files(agent2)
        assert "001_report.md" in files1
        assert "001_report.md" in files2

    @pytest.mark.asyncio
    async def test_multi_turn_memory_accumulation(
        self, agent_env: tuple[AgentRuntime, FileManager, str, str]
    ) -> None:
        """多回合记忆积累。"""
        runtime, fm, agent1, _ = agent_env
        data = make_national_data()

        # 连续 4 个回合
        for turn in range(1, 5):
            await runtime.summarize(agent1, turn, data)

        # 验证 workspace 有 4 个报告
        files = fm.list_workspace_files(agent1)
        assert "001_report.md" in files
        assert "004_report.md" in files

        # 验证记忆窗口（保留最近 3 回合：2,3,4）
        memories = fm.list_recent_memories(agent1)
        turns = [t for t, _ in memories]
        assert 1 not in turns  # turn 1 应被清理
        assert 2 in turns
        assert 3 in turns
        assert 4 in turns


class TestExecuteValidation:
    """执行阶段校验集成测试。"""

    @pytest.mark.asyncio
    async def test_cross_province_effect_rejected(
        self, agent_env: tuple[AgentRuntime, FileManager, str, str]
    ) -> None:
        """governor_zhili 试图修改非 zhili 省份 → 降级。"""
        runtime, fm, _, agent2 = agent_env

        # 替换 provider 使 governor_zhili 产出跨省效果
        bad_result = ExecutionResult(
            narrative="臣已办理。",
            effects=[
                EventEffect(
                    target="agriculture.irrigation_level",
                    operation=EffectOperation.ADD,
                    value=Decimal("0.05"),
                    scope=EffectScope(province_ids=["jiangnan"]),  # 跨省！
                ),
            ],
            fidelity=Decimal("0.9"),
        )
        provider = MockProvider(structured_responses={"governor_zhili": bad_result})
        client = LLMClient(provider)
        cb = ContextBuilder(fm)
        mm = MemoryManager(fm)
        runtime_bad = AgentRuntime(client, cb, mm, fm)

        command = PlayerEvent(
            turn_created=1,
            description="修缮水利",
            command_type="build_irrigation",
            target_province_id="zhili",
        )
        event = await runtime_bad.execute(agent2, 1, command, make_national_data())

        # 跨省效果被拒，降级为 fidelity=0
        assert event.fidelity == Decimal("0")
        assert event.effects == []

    @pytest.mark.asyncio
    async def test_valid_execution_preserves_fidelity(
        self, agent_env: tuple[AgentRuntime, FileManager, str, str]
    ) -> None:
        """合规执行保留原始 fidelity。"""
        runtime, fm, _, agent2 = agent_env
        data = make_national_data()

        command = PlayerEvent(
            turn_created=1,
            description="修缮水利",
            command_type="build_irrigation",
            target_province_id="zhili",
        )
        event = await runtime.execute(agent2, 1, command, data)

        assert event.fidelity == Decimal("0.95")
        assert len(event.effects) == 1
        assert event.effects[0].target == "agriculture.irrigation_level"


class TestWithPersistence:
    """结合持久化层的集成测试。"""

    @pytest.mark.asyncio
    async def test_summarize_and_persist_report(
        self, agent_env: tuple[AgentRuntime, FileManager, str, str], db_conn
    ) -> None:
        """summarize 后手动持久化报告到数据库。"""
        from simu_emperor.persistence.repositories import AgentReportRepository

        runtime, fm, agent1, _ = agent_env
        data = make_national_data()
        turn = 1

        report = await runtime.summarize(agent1, turn, data)

        # 手动持久化（runtime 本身不直接操作 DB，由编排器负责）
        repo = AgentReportRepository(db_conn)
        await repo.save_report(
            game_id="test_game",
            turn=turn,
            agent_id=agent1,
            markdown=report,
            real_data=data,
            report_type="report",
            file_name=f"{turn:03d}_report.md",
        )

        # 验证持久化
        result = await repo.get_report("test_game", turn, agent1)
        assert result is not None
        markdown, _ = result
        assert markdown == report

    @pytest.mark.asyncio
    async def test_execute_and_persist_command(
        self, agent_env: tuple[AgentRuntime, FileManager, str, str], db_conn
    ) -> None:
        """execute 后手动持久化命令和结果到数据库。"""
        from simu_emperor.persistence.repositories import PlayerCommandRepository

        runtime, fm, agent1, _ = agent_env
        data = make_national_data()
        turn = 1

        command = PlayerEvent(
            turn_created=turn,
            description="减税",
            command_type="adjust_tax",
            target_province_id="zhili",
        )
        event = await runtime.execute(agent1, turn, command, data)

        # 手动持久化
        repo = PlayerCommandRepository(db_conn)
        await repo.save_command("test_game", turn, command, event)

        # 验证
        commands = await repo.get_commands("test_game", turn)
        assert len(commands) == 1
        saved_cmd, saved_result = commands[0]
        assert saved_cmd.command_type == "adjust_tax"
        assert saved_result is not None
        assert saved_result.agent_id == agent1

    @pytest.mark.asyncio
    async def test_respond_and_persist_chat(
        self, agent_env: tuple[AgentRuntime, FileManager, str, str], db_conn
    ) -> None:
        """respond 后手动持久化对话到数据库。"""
        from simu_emperor.persistence.repositories import ChatHistoryRepository

        runtime, fm, agent1, _ = agent_env
        data = make_national_data()

        player_msg = "国库还剩多少？"
        response = await runtime.respond(agent1, 1, player_msg, data)

        # 手动持久化
        repo = ChatHistoryRepository(db_conn)
        await repo.add_message("test_game", agent1, "player", player_msg)
        await repo.add_message("test_game", agent1, "agent", response)

        # 验证
        history = await repo.get_history("test_game", agent1)
        assert len(history) == 2
        assert history[0][0] == "player"
        assert history[1][0] == "agent"
