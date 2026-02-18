"""序列化模块单元测试。"""

from decimal import Decimal

from simu_emperor.engine.models.base_data import NationalBaseData
from simu_emperor.engine.models.effects import EffectOperation, EffectScope, EventEffect
from simu_emperor.engine.models.events import (
    AgentEvent,
    EventSource,
    GameEvent,
    PlayerEvent,
    RandomEvent,
)
from simu_emperor.engine.models.state import GamePhase, GameState, TurnRecord
from tests.conftest import make_national_data, make_province, make_zhili_province


class TestGameStateSerialization:
    """GameState 序列化测试。"""

    def test_game_state_roundtrip(self) -> None:
        """GameState 完整序列化往返。"""
        from simu_emperor.persistence.serialization import (
            deserialize_game_state,
            serialize_game_state,
        )

        national_data = make_national_data(turn=5, imperial_treasury=Decimal("600000"))
        state = GameState(
            game_id="test-game-001",
            current_turn=5,
            phase=GamePhase.INTERACTION,
            base_data=national_data,
        )

        json_str = serialize_game_state(state)
        restored = deserialize_game_state(json_str)

        assert restored.game_id == "test-game-001"
        assert restored.current_turn == 5
        assert restored.phase == GamePhase.INTERACTION
        assert restored.base_data.imperial_treasury == Decimal("600000")

    def test_game_state_with_active_events(self) -> None:
        """GameState 序列化含活跃事件。"""
        from simu_emperor.persistence.serialization import (
            deserialize_game_state,
            serialize_game_state,
        )

        effect = EventEffect(
            target="population.total",
            operation=EffectOperation.ADD,
            value=Decimal("1000"),
            scope=EffectScope(province_ids=["zhili"]),
        )
        player_event = PlayerEvent(
            turn_created=3,
            description="人口迁移",
            effects=[effect],
            command_type="migration",
            target_province_id="zhili",
        )

        state = GameState(
            game_id="test-game-002",
            current_turn=3,
            phase=GamePhase.EXECUTION,
            base_data=make_national_data(),
            active_events=[player_event],
        )

        json_str = serialize_game_state(state)
        restored = deserialize_game_state(json_str)

        assert len(restored.active_events) == 1
        event = restored.active_events[0]
        assert isinstance(event, PlayerEvent)
        assert event.command_type == "migration"
        assert event.target_province_id == "zhili"
        assert len(event.effects) == 1

    def test_game_state_with_history(self) -> None:
        """GameState 序列化含历史记录。"""
        from simu_emperor.persistence.serialization import (
            deserialize_game_state,
            serialize_game_state,
        )

        national_data = make_national_data()
        record = TurnRecord(
            turn=2,
            base_data_snapshot=national_data,
            events_applied=[],
        )

        state = GameState(
            game_id="test-game-003",
            current_turn=3,
            phase=GamePhase.RESOLUTION,
            base_data=national_data,
            history=[record],
        )

        json_str = serialize_game_state(state)
        restored = deserialize_game_state(json_str)

        assert len(restored.history) == 1
        assert restored.history[0].turn == 2


class TestEventSerialization:
    """事件序列化测试。"""

    def test_player_event_roundtrip(self) -> None:
        """PlayerEvent 序列化往返。"""
        from simu_emperor.persistence.serialization import (
            deserialize_event,
            serialize_event,
        )

        effect = EventEffect(
            target="agriculture.irrigation_level",
            operation=EffectOperation.MULTIPLY,
            value=Decimal("1.2"),
            scope=EffectScope(is_national=True),
        )
        event = PlayerEvent(
            turn_created=1,
            description="兴修水利",
            effects=[effect],
            duration=3,
            command_type="build_irrigation",
            target_province_id="zhili",
            parameters={"budget": "50000"},
        )

        json_str = serialize_event(event)
        restored = deserialize_event(json_str)

        assert isinstance(restored, PlayerEvent)
        assert restored.source == EventSource.PLAYER
        assert restored.command_type == "build_irrigation"
        assert restored.target_province_id == "zhili"
        assert restored.parameters == {"budget": "50000"}
        assert restored.duration == 3
        assert len(restored.effects) == 1
        assert restored.effects[0].operation == EffectOperation.MULTIPLY

    def test_agent_event_roundtrip(self) -> None:
        """AgentEvent 序列化往返。"""
        from simu_emperor.persistence.serialization import (
            deserialize_event,
            serialize_event,
        )

        effect = EventEffect(
            target="military.garrison_size",
            operation=EffectOperation.ADD,
            value=Decimal("3000"),
            scope=EffectScope(province_ids=["zhili"]),
        )
        event = AgentEvent(
            turn_created=2,
            description="征兵执行（部分糊弄）",
            effects=[effect],
            agent_event_type="recruit",
            agent_id="general_wang",
            fidelity=Decimal("0.6"),
        )

        json_str = serialize_event(event)
        restored = deserialize_event(json_str)

        assert isinstance(restored, AgentEvent)
        assert restored.source == EventSource.AGENT
        assert restored.agent_id == "general_wang"
        assert restored.fidelity == Decimal("0.6")
        assert restored.agent_event_type == "recruit"

    def test_random_event_roundtrip(self) -> None:
        """RandomEvent 序列化往返。"""
        from simu_emperor.persistence.serialization import (
            deserialize_event,
            serialize_event,
        )

        effect = EventEffect(
            target="agriculture.irrigation_level",
            operation=EffectOperation.MULTIPLY,
            value=Decimal("0.7"),
            scope=EffectScope(province_ids=["zhili"]),
        )
        event = RandomEvent(
            turn_created=3,
            description="旱灾袭击直隶",
            effects=[effect],
            duration=2,
            category="disaster",
            severity=Decimal("0.8"),
        )

        json_str = serialize_event(event)
        restored = deserialize_event(json_str)

        assert isinstance(restored, RandomEvent)
        assert restored.source == EventSource.RANDOM
        assert restored.category == "disaster"
        assert restored.severity == Decimal("0.8")
        assert restored.duration == 2

    def test_discriminated_union_mixed_list(self) -> None:
        """混合事件列表序列化（discriminated union 恢复）。"""
        from simu_emperor.persistence.serialization import (
            deserialize_event,
            serialize_event,
        )

        events: list[GameEvent] = [
            PlayerEvent(
                turn_created=1,
                description="命令1",
                command_type="tax",
            ),
            AgentEvent(
                turn_created=1,
                description="执行1",
                agent_event_type="collect_tax",
                agent_id="minister_li",
                fidelity=Decimal("0.8"),
            ),
            RandomEvent(
                turn_created=1,
                description="随机1",
                category="harvest",
                severity=Decimal("0.3"),
            ),
        ]

        # 分别序列化/反序列化
        restored_events = [deserialize_event(serialize_event(e)) for e in events]

        assert isinstance(restored_events[0], PlayerEvent)
        assert isinstance(restored_events[1], AgentEvent)
        assert isinstance(restored_events[2], RandomEvent)

        assert restored_events[0].source == EventSource.PLAYER
        assert restored_events[1].source == EventSource.AGENT
        assert restored_events[2].source == EventSource.RANDOM


class TestNationalDataSerialization:
    """NationalBaseData 序列化测试。"""

    def test_national_data_roundtrip(self) -> None:
        """NationalBaseData 完整序列化往返。"""
        from simu_emperor.persistence.serialization import (
            deserialize_national_data,
            serialize_national_data,
        )

        data = make_national_data(
            turn=10,
            imperial_treasury=Decimal("800000"),
            national_tax_modifier=Decimal("1.1"),
        )

        json_str = serialize_national_data(data)
        restored = deserialize_national_data(json_str)

        assert restored.turn == 10
        assert restored.imperial_treasury == Decimal("800000")
        assert restored.national_tax_modifier == Decimal("1.1")
        assert len(restored.provinces) == 1

    def test_national_data_multi_province(self) -> None:
        """NationalBaseData 多省份序列化往返。"""
        from simu_emperor.persistence.serialization import (
            deserialize_national_data,
            serialize_national_data,
        )

        zhili = make_zhili_province()
        jiangnan = make_province(
            province_id="jiangnan",
            name="江南",
            granary_stock=Decimal("200000"),
        )

        data = NationalBaseData(
            turn=5,
            imperial_treasury=Decimal("1000000"),
            provinces=[zhili, jiangnan],
        )

        json_str = serialize_national_data(data)
        restored = deserialize_national_data(json_str)

        assert len(restored.provinces) == 2
        assert restored.provinces[0].province_id == "zhili"
        assert restored.provinces[1].province_id == "jiangnan"
        assert restored.provinces[0].population.total == zhili.population.total
        assert restored.provinces[1].granary_stock == Decimal("200000")

    def test_zhili_province_roundtrip(self) -> None:
        """直隶省完整数据序列化往返。"""
        from simu_emperor.persistence.serialization import (
            deserialize_national_data,
            serialize_national_data,
        )

        zhili = make_zhili_province()
        data = NationalBaseData(
            turn=1,
            imperial_treasury=Decimal("500000"),
            provinces=[zhili],
        )

        json_str = serialize_national_data(data)
        restored = deserialize_national_data(json_str)

        province = restored.provinces[0]
        assert province.province_id == "zhili"
        assert province.name == "直隶"
        assert province.population.total == Decimal("2600000")
        assert province.population.happiness == Decimal("0.70")
        assert province.military.garrison_size == Decimal("30000")
        assert province.granary_stock == Decimal("1200000")
