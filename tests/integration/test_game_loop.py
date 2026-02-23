"""GameLoop 集成测试。"""

from decimal import Decimal
from pathlib import Path

import pytest

from simu_emperor.agents.llm.providers import MockProvider
from simu_emperor.config import AgentConfig, GameConfig
from simu_emperor.engine.models.effects import EffectOperation, EffectScope, EventEffect
from simu_emperor.engine.models.events import PlayerEvent
from simu_emperor.engine.models.state import GamePhase, GameState
from simu_emperor.game import GameLoop, PhaseError
from simu_emperor.persistence.database import init_database

from tests.conftest import make_national_data


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """创建完整的 data 目录结构。"""
    data = tmp_path / "data"
    data.mkdir()

    # skills
    skills = data / "skills"
    skills.mkdir()
    (skills / "query_data.md").write_text("# 查询数据", encoding="utf-8")
    (skills / "write_report.md").write_text("# 撰写报告", encoding="utf-8")
    (skills / "execute_command.md").write_text("# 执行命令", encoding="utf-8")

    # default_agents
    defaults = data / "default_agents"
    defaults.mkdir()

    # agent 工作区
    agent_base = data / "agent"
    agent_base.mkdir()

    # 创建 agent
    agent_id = "minister_of_revenue"
    agent_dir = agent_base / agent_id
    agent_dir.mkdir()
    (agent_dir / "soul.md").write_text("你是户部尚书。", encoding="utf-8")
    (agent_dir / "data_scope.yaml").write_text(
        """\
display_name: 户部尚书
skills:
  query_data:
    national: [imperial_treasury]
    provinces: all
    fields:
      - commerce.*
      - taxation.*
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
    (agent_dir / "memory").mkdir()
    (agent_dir / "memory" / "recent").mkdir()
    (agent_dir / "workspace").mkdir()

    # saves 目录
    (data / "saves").mkdir()

    return data


@pytest.fixture
async def db_conn(tmp_path: Path):
    """创建临时 SQLite 数据库。"""
    db_path = str(tmp_path / "test.db")
    conn = await init_database(db_path)
    yield conn
    await conn.close()


async def _make_game_loop(
    data_dir: Path,
    db_conn,
    provider: MockProvider | None = None,
    seed: int = 42,
) -> GameLoop:
    """创建并初始化 GameLoop 实例。"""
    state = GameState(
        game_id="test_game",
        current_turn=0,
        phase=GamePhase.RESOLUTION,
        base_data=make_national_data(turn=0),
    )
    config = GameConfig(
        data_dir=data_dir,
        seed=seed,
        max_random_events_per_turn=0,  # 测试中禁用随机事件
        agent=AgentConfig(max_concurrent_llm_calls=5),
    )
    if provider is None:
        provider = MockProvider(
            responses={"minister_of_revenue": "回禀陛下，国库稳定。"},
        )
    loop = GameLoop(state=state, config=config, provider=provider, conn=db_conn)
    # 注意：不调用 initialize_agents()，因为 data_dir fixture 已经创建了 agent 目录
    await loop.initialize()
    return loop


# ── 阶段推进测试 ──


class TestPhaseTransitions:
    @pytest.mark.asyncio
    async def test_initial_resolution(self, data_dir: Path, db_conn) -> None:
        """首回合可从 RESOLUTION 推进。"""
        loop = await _make_game_loop(data_dir, db_conn)
        assert loop.phase == GamePhase.RESOLUTION

        state, metrics = await loop.advance_to_resolution()
        assert state.phase == GamePhase.SUMMARY
        assert state.current_turn == 1
        assert metrics is not None
        assert loop.latest_metrics is metrics

    @pytest.mark.asyncio
    async def test_full_cycle(self, data_dir: Path, db_conn) -> None:
        """完整阶段循环：RESOLUTION → SUMMARY → INTERACTION → EXECUTION。"""
        loop = await _make_game_loop(data_dir, db_conn)

        # RESOLUTION
        state, metrics = await loop.advance_to_resolution()
        assert state.phase == GamePhase.SUMMARY

        # SUMMARY
        reports = await loop.advance_to_summary()
        assert "minister_of_revenue" in reports
        assert state.phase == GamePhase.INTERACTION

        # INTERACTION (no commands, just advance)
        events = await loop.advance_to_execution()
        assert state.phase == GamePhase.EXECUTION
        assert events == []

    @pytest.mark.asyncio
    async def test_second_turn(self, data_dir: Path, db_conn) -> None:
        """第二回合正常推进。"""
        loop = await _make_game_loop(data_dir, db_conn)

        # Turn 1
        await loop.advance_to_resolution()
        await loop.advance_to_summary()
        await loop.advance_to_execution()

        # Turn 2
        state, metrics = await loop.advance_to_resolution()
        assert state.current_turn == 2
        assert state.phase == GamePhase.SUMMARY
        assert len(state.history) == 2  # turn 0 + turn 1


# ── 阶段锁定测试 ──


class TestPhaseLocking:
    @pytest.mark.asyncio
    async def test_cannot_summarize_in_wrong_phase(self, data_dir: Path, db_conn) -> None:
        loop = await _make_game_loop(data_dir, db_conn)
        # 初始为 RESOLUTION，不能汇总
        with pytest.raises(PhaseError):
            await loop.advance_to_summary()

    @pytest.mark.asyncio
    async def test_cannot_chat_in_wrong_phase(self, data_dir: Path, db_conn) -> None:
        loop = await _make_game_loop(data_dir, db_conn)
        with pytest.raises(PhaseError):
            await loop.handle_player_message("minister_of_revenue", "test")

    @pytest.mark.asyncio
    async def test_cannot_execute_in_wrong_phase(self, data_dir: Path, db_conn) -> None:
        loop = await _make_game_loop(data_dir, db_conn)
        with pytest.raises(PhaseError):
            await loop.advance_to_execution()

    @pytest.mark.asyncio
    async def test_cannot_submit_command_in_wrong_phase(self, data_dir: Path, db_conn) -> None:
        loop = await _make_game_loop(data_dir, db_conn)
        cmd = PlayerEvent(
            turn_created=0,
            description="test",
            command_type="test",
        )
        with pytest.raises(PhaseError):
            loop.submit_command(cmd)


# ── 交互阶段测试 ──


class TestInteraction:
    @pytest.mark.asyncio
    async def test_handle_player_message(self, data_dir: Path, db_conn) -> None:
        loop = await _make_game_loop(data_dir, db_conn)
        await loop.advance_to_resolution()
        await loop.advance_to_summary()

        response = await loop.handle_player_message("minister_of_revenue", "国库多少？")
        assert isinstance(response, str)
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_chat_persisted(self, data_dir: Path, db_conn) -> None:
        """对话应持久化到数据库。"""
        from simu_emperor.persistence.repositories import ChatHistoryRepository

        loop = await _make_game_loop(data_dir, db_conn)
        await loop.advance_to_resolution()
        await loop.advance_to_summary()

        await loop.handle_player_message("minister_of_revenue", "国库多少？")

        repo = ChatHistoryRepository(db_conn)
        history = await repo.get_history("test_game", "minister_of_revenue")
        assert len(history) == 2  # player + agent


# ── 命令执行测试 ──


class TestExecution:
    @pytest.mark.asyncio
    async def test_direct_command_added_to_events(self, data_dir: Path, db_conn) -> None:
        """direct=True 的命令直接加入 active_events。"""
        loop = await _make_game_loop(data_dir, db_conn)
        await loop.advance_to_resolution()
        await loop.advance_to_summary()

        events_before = len(loop.state.active_events)
        cmd = PlayerEvent(
            turn_created=1,
            description="皇帝亲令减税",
            command_type="direct_tax",
            direct=True,
            effects=[
                EventEffect(
                    target="taxation.land_tax_rate",
                    operation=EffectOperation.ADD,
                    value=Decimal("-0.01"),
                    scope=EffectScope(province_ids=["jiangnan"]),
                ),
            ],
        )
        loop.submit_command(cmd)
        assert len(loop.state.active_events) == events_before + 1

    @pytest.mark.asyncio
    async def test_non_direct_command_executed_by_agent(self, data_dir: Path, db_conn) -> None:
        """direct=False 的命令由 Agent 执行。"""
        loop = await _make_game_loop(data_dir, db_conn)
        await loop.advance_to_resolution()
        await loop.advance_to_summary()

        cmd = PlayerEvent(
            turn_created=1,
            description="调整税率",
            command_type="adjust_tax",
            target_province_id="jiangnan",
            direct=False,
        )
        loop.submit_command(cmd)

        events = await loop.advance_to_execution()
        assert len(events) == 1
        assert events[0].agent_event_type == "adjust_tax"

    @pytest.mark.asyncio
    async def test_execution_persisted(self, data_dir: Path, db_conn) -> None:
        """执行结果应持久化到数据库。"""
        from simu_emperor.persistence.repositories import PlayerCommandRepository

        loop = await _make_game_loop(data_dir, db_conn)
        await loop.advance_to_resolution()
        await loop.advance_to_summary()

        cmd = PlayerEvent(
            turn_created=1,
            description="减税",
            command_type="adjust_tax",
            direct=False,
        )
        loop.submit_command(cmd)
        await loop.advance_to_execution()

        repo = PlayerCommandRepository(db_conn)
        commands = await repo.get_commands("test_game", 1)
        assert len(commands) == 1

    @pytest.mark.asyncio
    async def test_no_commands_execution(self, data_dir: Path, db_conn) -> None:
        """无命令时执行阶段正常完成。"""
        loop = await _make_game_loop(data_dir, db_conn)
        await loop.advance_to_resolution()
        await loop.advance_to_summary()

        events = await loop.advance_to_execution()
        assert events == []
        assert loop.phase == GamePhase.EXECUTION


# ── 汇总阶段测试 ──


class TestSummary:
    @pytest.mark.asyncio
    async def test_reports_persisted(self, data_dir: Path, db_conn) -> None:
        """报告应持久化到数据库。"""
        from simu_emperor.persistence.repositories import AgentReportRepository

        loop = await _make_game_loop(data_dir, db_conn)
        await loop.advance_to_resolution()
        await loop.advance_to_summary()

        repo = AgentReportRepository(db_conn)
        reports = await repo.list_reports("test_game", 1)
        assert len(reports) >= 1
        agent_ids = [r[0] for r in reports]
        assert "minister_of_revenue" in agent_ids

    @pytest.mark.asyncio
    async def test_summary_returns_all_agents(self, data_dir: Path, db_conn) -> None:
        """汇总应返回所有活跃 Agent 的报告。"""
        loop = await _make_game_loop(data_dir, db_conn)
        await loop.advance_to_resolution()
        reports = await loop.advance_to_summary()
        assert "minister_of_revenue" in reports


# ── 历史记录测试 ──


class TestHistory:
    @pytest.mark.asyncio
    async def test_history_accumulates(self, data_dir: Path, db_conn) -> None:
        """每回合 resolution 产生一条 TurnRecord。"""
        loop = await _make_game_loop(data_dir, db_conn)

        # Turn 1
        await loop.advance_to_resolution()
        assert len(loop.state.history) == 1
        assert loop.state.history[0].turn == 0

        await loop.advance_to_summary()
        await loop.advance_to_execution()

        # Turn 2
        await loop.advance_to_resolution()
        assert len(loop.state.history) == 2
        assert loop.state.history[1].turn == 1
