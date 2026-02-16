"""Repository 模块单元测试。"""

from decimal import Decimal

import aiosqlite
import pytest

from simu_emperor.engine.models.effects import EffectOperation, EffectScope, EventEffect
from simu_emperor.engine.models.events import AgentEvent, PlayerEvent, RandomEvent
from simu_emperor.engine.models.state import GamePhase, GameState
from simu_emperor.persistence.database import _create_schema
from simu_emperor.persistence.repositories import (
    AgentReportRepository,
    ChatHistoryRepository,
    EventLogRepository,
    GameSaveRepository,
    PlayerCommandRepository,
)
from tests.conftest import make_national_data, make_zhili_province


@pytest.fixture
async def db_conn():
    """每个测试独立的内存 SQLite 连接。"""
    conn = await aiosqlite.connect(":memory:")
    await _create_schema(conn)
    yield conn
    await conn.close()


class TestGameSaveRepository:
    """GameSaveRepository 测试。"""

    async def test_save_and_load(self, db_conn) -> None:
        """保存并加载游戏状态。"""
        repo = GameSaveRepository(db_conn)
        state = GameState(
            game_id="game-001",
            current_turn=3,
            phase=GamePhase.INTERACTION,
            base_data=make_national_data(turn=3),
        )

        await repo.save(state)
        loaded = await repo.load("game-001", turn=3)

        assert loaded is not None
        assert loaded.game_id == "game-001"
        assert loaded.current_turn == 3
        assert loaded.phase == GamePhase.INTERACTION

    async def test_load_latest(self, db_conn) -> None:
        """不指定回合时加载最新存档。"""
        repo = GameSaveRepository(db_conn)

        for turn in [1, 2, 5]:
            state = GameState(
                game_id="game-002",
                current_turn=turn,
                phase=GamePhase.RESOLUTION,
                base_data=make_national_data(turn=turn),
            )
            await repo.save(state)

        loaded = await repo.load("game-002")
        assert loaded is not None
        assert loaded.current_turn == 5

    async def test_load_nonexistent(self, db_conn) -> None:
        """加载不存在的存档返回 None。"""
        repo = GameSaveRepository(db_conn)
        loaded = await repo.load("nonexistent", turn=1)
        assert loaded is None

    async def test_list_saves(self, db_conn) -> None:
        """列出所有存档。"""
        repo = GameSaveRepository(db_conn)

        for turn in [1, 3, 5]:
            state = GameState(
                game_id="game-003",
                current_turn=turn,
                phase=GamePhase.RESOLUTION,
                base_data=make_national_data(turn=turn),
            )
            await repo.save(state)

        saves = await repo.list_saves("game-003")
        assert len(saves) == 3
        assert [s[0] for s in saves] == [1, 3, 5]

    async def test_delete(self, db_conn) -> None:
        """删除指定存档。"""
        repo = GameSaveRepository(db_conn)
        state = GameState(
            game_id="game-004",
            current_turn=2,
            phase=GamePhase.RESOLUTION,
            base_data=make_national_data(turn=2),
        )

        await repo.save(state)
        await repo.delete("game-004", 2)

        loaded = await repo.load("game-004", turn=2)
        assert loaded is None

    async def test_save_overwrites_same_turn(self, db_conn) -> None:
        """同一 game_id + turn 的存档会被覆盖。"""
        repo = GameSaveRepository(db_conn)

        state1 = GameState(
            game_id="game-005",
            current_turn=1,
            phase=GamePhase.RESOLUTION,
            base_data=make_national_data(imperial_treasury=Decimal("100000")),
        )
        await repo.save(state1)

        state2 = GameState(
            game_id="game-005",
            current_turn=1,
            phase=GamePhase.INTERACTION,
            base_data=make_national_data(imperial_treasury=Decimal("200000")),
        )
        await repo.save(state2)

        loaded = await repo.load("game-005", turn=1)
        assert loaded is not None
        assert loaded.phase == GamePhase.INTERACTION
        assert loaded.base_data.imperial_treasury == Decimal("200000")


class TestEventLogRepository:
    """EventLogRepository 测试。"""

    async def test_log_and_get_events(self, db_conn) -> None:
        """记录并查询事件。"""
        repo = EventLogRepository(db_conn)

        event = PlayerEvent(
            turn_created=1,
            description="兴修水利",
            command_type="build_irrigation",
            target_province_id="zhili",
        )
        await repo.log_event("game-001", 1, event, "created")

        events = await repo.get_events("game-001", 1)
        assert len(events) == 1
        restored_event, action = events[0]
        assert isinstance(restored_event, PlayerEvent)
        assert restored_event.command_type == "build_irrigation"
        assert action == "created"

    async def test_multiple_events_per_turn(self, db_conn) -> None:
        """同一回合多个事件。"""
        repo = EventLogRepository(db_conn)

        player_event = PlayerEvent(
            turn_created=2,
            description="调税",
            command_type="adjust_tax",
        )
        agent_event = AgentEvent(
            turn_created=2,
            description="执行调税",
            agent_event_type="tax_collection",
            agent_id="minister_li",
            fidelity=Decimal("0.9"),
        )
        random_event = RandomEvent(
            turn_created=2,
            description="丰收",
            category="harvest",
            severity=Decimal("0.5"),
        )

        await repo.log_event("game-001", 2, player_event, "created")
        await repo.log_event("game-001", 2, agent_event, "created")
        await repo.log_event("game-001", 2, random_event, "applied")

        events = await repo.get_events("game-001", 2)
        assert len(events) == 3
        assert isinstance(events[0][0], PlayerEvent)
        assert isinstance(events[1][0], AgentEvent)
        assert isinstance(events[2][0], RandomEvent)
        assert events[2][1] == "applied"

    async def test_event_history(self, db_conn) -> None:
        """事件历史追踪。"""
        repo = EventLogRepository(db_conn)

        event = RandomEvent(
            turn_created=1,
            description="旱灾",
            category="disaster",
            severity=Decimal("0.8"),
            duration=3,
        )

        await repo.log_event("game-001", 1, event, "created")
        await repo.log_event("game-001", 2, event, "applied")
        await repo.log_event("game-001", 3, event, "applied")
        await repo.log_event("game-001", 4, event, "expired")

        history = await repo.get_event_history("game-001", event.event_id)
        assert len(history) == 4
        assert [h[0] for h in history] == ["created", "applied", "applied", "expired"]


class TestAgentReportRepository:
    """AgentReportRepository 测试。"""

    async def test_save_and_get_report(self, db_conn) -> None:
        """保存并获取报告。"""
        repo = AgentReportRepository(db_conn)
        real_data = make_national_data()

        await repo.save_report("game-001", 1, "minister_li", "# 税收报告\n收入良好。", real_data)
        result = await repo.get_report("game-001", 1, "minister_li")

        assert result is not None
        markdown, data = result
        assert "税收报告" in markdown
        assert data.imperial_treasury == real_data.imperial_treasury

    async def test_get_nonexistent_report(self, db_conn) -> None:
        """获取不存在的报告返回 None。"""
        repo = AgentReportRepository(db_conn)
        result = await repo.get_report("game-001", 1, "nobody")
        assert result is None

    async def test_list_reports(self, db_conn) -> None:
        """列出指定回合的所有报告。"""
        repo = AgentReportRepository(db_conn)
        real_data = make_national_data()

        await repo.save_report("game-001", 1, "minister_li", "# 户部报告", real_data)
        await repo.save_report("game-001", 1, "general_wang", "# 兵部报告", real_data)
        await repo.save_report("game-001", 2, "minister_li", "# 第二回合报告", real_data)

        reports = await repo.list_reports("game-001", 1)
        assert len(reports) == 2
        agent_ids = [r[0] for r in reports]
        assert "minister_li" in agent_ids
        assert "general_wang" in agent_ids

    async def test_real_data_snapshot_preserved(self, db_conn) -> None:
        """真实数据快照保持完整。"""
        repo = AgentReportRepository(db_conn)
        zhili = make_zhili_province()
        real_data = make_national_data(
            turn=5,
            imperial_treasury=Decimal("999999"),
            provinces=[zhili],
        )

        await repo.save_report("game-001", 5, "minister_li", "报告", real_data)
        result = await repo.get_report("game-001", 5, "minister_li")

        assert result is not None
        _, data = result
        assert data.imperial_treasury == Decimal("999999")
        assert data.provinces[0].province_id == "zhili"
        assert data.provinces[0].population.total == Decimal("2600000")


class TestChatHistoryRepository:
    """ChatHistoryRepository 测试。"""

    async def test_add_and_get_history(self, db_conn) -> None:
        """添加并查询对话。"""
        repo = ChatHistoryRepository(db_conn)

        await repo.add_message("game-001", "minister_li", "player", "税收情况如何？")
        await repo.add_message("game-001", "minister_li", "agent", "启禀陛下，税收充裕。")

        history = await repo.get_history("game-001", "minister_li")
        assert len(history) == 2
        assert history[0][0] == "player"
        assert history[0][1] == "税收情况如何？"
        assert history[1][0] == "agent"
        assert history[1][1] == "启禀陛下，税收充裕。"

    async def test_limit(self, db_conn) -> None:
        """limit 分页。"""
        repo = ChatHistoryRepository(db_conn)

        for i in range(10):
            await repo.add_message("game-001", "minister_li", "player", f"消息 {i}")

        history = await repo.get_history("game-001", "minister_li", limit=3)
        assert len(history) == 3
        # 应该返回最近的 3 条（按正序排列）
        assert history[0][1] == "消息 7"
        assert history[1][1] == "消息 8"
        assert history[2][1] == "消息 9"

    async def test_separate_agents(self, db_conn) -> None:
        """不同 agent 的对话互不干扰。"""
        repo = ChatHistoryRepository(db_conn)

        await repo.add_message("game-001", "minister_li", "player", "李大人")
        await repo.add_message("game-001", "general_wang", "player", "王将军")

        li_history = await repo.get_history("game-001", "minister_li")
        wang_history = await repo.get_history("game-001", "general_wang")

        assert len(li_history) == 1
        assert len(wang_history) == 1
        assert li_history[0][1] == "李大人"
        assert wang_history[0][1] == "王将军"


class TestPlayerCommandRepository:
    """PlayerCommandRepository 测试。"""

    async def test_save_and_get_command(self, db_conn) -> None:
        """保存并查询命令。"""
        repo = PlayerCommandRepository(db_conn)

        command = PlayerEvent(
            turn_created=1,
            description="征兵三千",
            command_type="recruit",
            target_province_id="zhili",
            parameters={"count": "3000"},
        )
        await repo.save_command("game-001", 1, command)

        commands = await repo.get_commands("game-001", 1)
        assert len(commands) == 1
        restored_cmd, result = commands[0]
        assert restored_cmd.command_type == "recruit"
        assert restored_cmd.target_province_id == "zhili"
        assert restored_cmd.parameters == {"count": "3000"}
        assert result is None

    async def test_save_command_with_result(self, db_conn) -> None:
        """保存带执行结果的命令。"""
        repo = PlayerCommandRepository(db_conn)

        command = PlayerEvent(
            turn_created=2,
            description="调高商税",
            command_type="adjust_tax",
            target_province_id="jiangnan",
            parameters={"tax_type": "commercial", "rate": "0.15"},
        )
        effect = EventEffect(
            target="taxation.commercial_tax_rate",
            operation=EffectOperation.MULTIPLY,
            value=Decimal("1.1"),
            scope=EffectScope(province_ids=["jiangnan"]),
        )
        result = AgentEvent(
            turn_created=2,
            description="税率调整（打了折扣）",
            agent_event_type="tax_adjustment",
            agent_id="minister_li",
            fidelity=Decimal("0.7"),
            effects=[effect],
        )

        await repo.save_command("game-001", 2, command, result)

        commands = await repo.get_commands("game-001", 2)
        assert len(commands) == 1
        restored_cmd, restored_result = commands[0]
        assert restored_cmd.command_type == "adjust_tax"
        assert restored_result is not None
        assert isinstance(restored_result, AgentEvent)
        assert restored_result.fidelity == Decimal("0.7")
        assert restored_result.agent_id == "minister_li"

    async def test_multiple_commands_per_turn(self, db_conn) -> None:
        """同一回合多个命令。"""
        repo = PlayerCommandRepository(db_conn)

        cmd1 = PlayerEvent(
            turn_created=3,
            description="征兵",
            command_type="recruit",
            target_province_id="zhili",
        )
        cmd2 = PlayerEvent(
            turn_created=3,
            description="修路",
            command_type="build_road",
            target_province_id="jiangnan",
        )

        await repo.save_command("game-001", 3, cmd1)
        await repo.save_command("game-001", 3, cmd2)

        commands = await repo.get_commands("game-001", 3)
        assert len(commands) == 2
        assert commands[0][0].command_type == "recruit"
        assert commands[1][0].command_type == "build_road"
