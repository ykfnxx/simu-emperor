"""events + effects 模型单元测试：事件创建、discriminated union 序列化。"""

from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from simu_emperor.engine.models.effects import (
    EffectOperation,
    EffectScope,
    EventEffect,
)
from simu_emperor.engine.models.events import (
    AgentEvent,
    EventSource,
    GameEvent,
    PlayerEvent,
    RandomEvent,
)
from simu_emperor.engine.models.state import (
    GamePhase,
    GameState,
    TurnRecord,
)

from tests.conftest import make_national_data


# --- Effects ---


class TestEffectOperation:
    def test_values(self):
        assert EffectOperation.ADD == "add"
        assert EffectOperation.MULTIPLY == "multiply"


class TestEffectScope:
    def test_defaults(self):
        scope = EffectScope()
        assert scope.province_ids == []
        assert scope.is_national is False

    def test_national_scope(self):
        scope = EffectScope(is_national=True)
        assert scope.is_national is True

    def test_province_scope(self):
        scope = EffectScope(province_ids=["jiangnan", "xibei"])
        assert len(scope.province_ids) == 2


class TestEventEffect:
    def test_add_effect(self):
        effect = EventEffect(
            target="population.total",
            operation=EffectOperation.ADD,
            value=Decimal("1000"),
            scope=EffectScope(province_ids=["jiangnan"]),
        )
        assert effect.target == "population.total"
        assert effect.operation == EffectOperation.ADD
        assert effect.value == Decimal("1000")

    def test_multiply_effect(self):
        effect = EventEffect(
            target="commerce.market_prosperity",
            operation=EffectOperation.MULTIPLY,
            value=Decimal("1.2"),
        )
        assert effect.operation == EffectOperation.MULTIPLY

    def test_serialization_roundtrip(self):
        effect = EventEffect(
            target="agriculture.irrigation_level",
            operation=EffectOperation.ADD,
            value=Decimal("0.1"),
            scope=EffectScope(province_ids=["jiangnan"]),
        )
        json_str = effect.model_dump_json()
        restored = EventEffect.model_validate_json(json_str)
        assert restored == effect


# --- Events ---


class TestPlayerEvent:
    def test_creation(self):
        event = PlayerEvent(
            turn_created=1,
            description="建设江南水利",
            command_type="build_irrigation",
            target_province_id="jiangnan",
            parameters={"investment": "10000"},
            effects=[
                EventEffect(
                    target="agriculture.irrigation_level",
                    operation=EffectOperation.ADD,
                    value=Decimal("0.1"),
                    scope=EffectScope(province_ids=["jiangnan"]),
                )
            ],
        )
        assert event.source == EventSource.PLAYER
        assert event.command_type == "build_irrigation"
        assert len(event.effects) == 1

    def test_auto_event_id(self):
        e1 = PlayerEvent(turn_created=0, description="a", command_type="x")
        e2 = PlayerEvent(turn_created=0, description="b", command_type="y")
        assert e1.event_id != e2.event_id

    def test_default_duration(self):
        event = PlayerEvent(turn_created=0, description="a", command_type="x")
        assert event.duration == 1

    def test_direct_default_false(self):
        event = PlayerEvent(turn_created=0, description="a", command_type="x")
        assert event.direct is False

    def test_direct_true(self):
        event = PlayerEvent(
            turn_created=0, description="皇帝亲自下令", command_type="direct_order", direct=True,
        )
        assert event.direct is True
        assert event.source == EventSource.PLAYER

    def test_direct_serialization_roundtrip(self):
        event = PlayerEvent(
            turn_created=1,
            description="亲政减税",
            command_type="tax_reduction",
            direct=True,
            parameters={"rate": "0.05"},
        )
        adapter = TypeAdapter(GameEvent)
        json_str = adapter.dump_json(event)
        restored = adapter.validate_json(json_str)
        assert isinstance(restored, PlayerEvent)
        assert restored.direct is True


class TestAgentEvent:
    def test_creation(self):
        event = AgentEvent(
            turn_created=3,
            description="户部执行减税命令",
            agent_event_type="execute_tax_reduction",
            agent_id="hubu_shangshu",
            fidelity=Decimal("0.7"),
        )
        assert event.source == EventSource.AGENT
        assert event.fidelity == Decimal("0.7")

    def test_fidelity_out_of_range(self):
        with pytest.raises(ValidationError):
            AgentEvent(
                turn_created=3,
                description="test",
                agent_event_type="test",
                agent_id="test",
                fidelity=Decimal("1.5"),
            )


class TestRandomEvent:
    def test_creation(self):
        event = RandomEvent(
            turn_created=2,
            description="江南水灾",
            category="disaster",
            severity=Decimal("0.8"),
            duration=3,
            effects=[
                EventEffect(
                    target="granary_stock",
                    operation=EffectOperation.MULTIPLY,
                    value=Decimal("0.5"),
                    scope=EffectScope(province_ids=["jiangnan"]),
                )
            ],
        )
        assert event.source == EventSource.RANDOM
        assert event.severity == Decimal("0.8")
        assert event.duration == 3


class TestGameEventDiscriminatedUnion:
    """测试 discriminated union 的序列化与反序列化。"""

    def test_serialize_player_event(self):
        event = PlayerEvent(
            turn_created=1,
            description="建设",
            command_type="build",
        )
        adapter = TypeAdapter(GameEvent)
        json_str = adapter.dump_json(event)
        restored = adapter.validate_json(json_str)
        assert isinstance(restored, PlayerEvent)
        assert restored.source == EventSource.PLAYER

    def test_serialize_agent_event(self):
        event = AgentEvent(
            turn_created=2,
            description="执行",
            agent_event_type="execute",
            agent_id="hubu",
            fidelity=Decimal("0.9"),
        )
        adapter = TypeAdapter(GameEvent)
        json_str = adapter.dump_json(event)
        restored = adapter.validate_json(json_str)
        assert isinstance(restored, AgentEvent)
        assert restored.source == EventSource.AGENT

    def test_serialize_random_event(self):
        event = RandomEvent(
            turn_created=3,
            description="水灾",
            category="disaster",
            severity=Decimal("0.5"),
        )
        adapter = TypeAdapter(GameEvent)
        json_str = adapter.dump_json(event)
        restored = adapter.validate_json(json_str)
        assert isinstance(restored, RandomEvent)

    def test_list_of_mixed_events(self):
        events = [
            PlayerEvent(turn_created=1, description="a", command_type="x"),
            AgentEvent(
                turn_created=1, description="b",
                agent_event_type="y", agent_id="z", fidelity=Decimal("1"),
            ),
            RandomEvent(turn_created=1, description="c", category="d", severity=Decimal("0")),
        ]
        adapter = TypeAdapter(list[GameEvent])
        json_str = adapter.dump_json(events)
        restored = adapter.validate_json(json_str)
        assert len(restored) == 3
        assert isinstance(restored[0], PlayerEvent)
        assert isinstance(restored[1], AgentEvent)
        assert isinstance(restored[2], RandomEvent)


# --- State ---


class TestGamePhase:
    def test_values(self):
        assert GamePhase.RESOLUTION == "resolution"
        assert GamePhase.SUMMARY == "summary"
        assert GamePhase.INTERACTION == "interaction"
        assert GamePhase.EXECUTION == "execution"


class TestTurnRecord:
    def test_creation(self):
        national = make_national_data()
        record = TurnRecord(
            turn=1,
            base_data_snapshot=national,
            events_applied=[
                PlayerEvent(turn_created=1, description="建设", command_type="build"),
            ],
        )
        assert record.turn == 1
        assert len(record.events_applied) == 1

    def test_serialization_roundtrip(self):
        national = make_national_data()
        record = TurnRecord(
            turn=1,
            base_data_snapshot=national,
            events_applied=[
                RandomEvent(turn_created=1, description="丰收", category="harvest", severity=Decimal("0.3")),
            ],
        )
        json_str = record.model_dump_json()
        restored = TurnRecord.model_validate_json(json_str)
        assert restored.turn == record.turn
        assert len(restored.events_applied) == 1
        assert isinstance(restored.events_applied[0], RandomEvent)


class TestGameState:
    def test_creation(self):
        state = GameState(base_data=make_national_data())
        assert state.current_turn == 0
        assert state.phase == GamePhase.RESOLUTION
        assert len(state.active_events) == 0
        assert len(state.history) == 0

    def test_auto_game_id(self):
        s1 = GameState(base_data=make_national_data())
        s2 = GameState(base_data=make_national_data())
        assert s1.game_id != s2.game_id

    def test_with_active_events(self):
        state = GameState(
            base_data=make_national_data(),
            active_events=[
                PlayerEvent(turn_created=0, description="建设", command_type="build"),
                RandomEvent(turn_created=0, description="水灾", category="disaster", severity=Decimal("0.9")),
            ],
        )
        assert len(state.active_events) == 2

    def test_full_serialization_roundtrip(self):
        national = make_national_data()
        state = GameState(
            current_turn=5,
            phase=GamePhase.INTERACTION,
            base_data=national,
            active_events=[
                AgentEvent(
                    turn_created=5, description="执行",
                    agent_event_type="exec", agent_id="hubu", fidelity=Decimal("0.8"),
                ),
            ],
            history=[
                TurnRecord(
                    turn=4,
                    base_data_snapshot=national,
                    events_applied=[],
                ),
            ],
        )
        json_str = state.model_dump_json()
        restored = GameState.model_validate_json(json_str)
        assert restored.current_turn == 5
        assert restored.phase == GamePhase.INTERACTION
        assert len(restored.active_events) == 1
        assert isinstance(restored.active_events[0], AgentEvent)
        assert len(restored.history) == 1
