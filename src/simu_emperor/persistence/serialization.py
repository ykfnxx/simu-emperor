"""GameState ↔ JSON 序列化/反序列化。"""

from typing import Any

from pydantic import TypeAdapter

from simu_emperor.engine.models.base_data import NationalBaseData
from simu_emperor.engine.models.events import (
    GameEvent,
)
from simu_emperor.engine.models.state import GameState


# TypeAdapter 用于处理 discriminated union
game_event_adapter: TypeAdapter[GameEvent] = TypeAdapter(GameEvent)


def serialize_game_state(state: GameState) -> str:
    """GameState → JSON 字符串（含 discriminated union 处理）。

    Args:
        state: 游戏状态对象

    Returns:
        JSON 字符串
    """
    return state.model_dump_json()


def deserialize_game_state(json_str: str) -> GameState:
    """JSON 字符串 → GameState。

    Args:
        json_str: JSON 字符串

    Returns:
        GameState 对象
    """
    return GameState.model_validate_json(json_str)


def serialize_event(event: GameEvent) -> str:
    """GameEvent → JSON 字符串。

    Args:
        event: 游戏事件对象

    Returns:
        JSON 字符串
    """
    return game_event_adapter.dump_json(event).decode("utf-8")


def deserialize_event(json_str: str | bytes) -> GameEvent:
    """JSON 字符串 → GameEvent（自动恢复具体类型）。

    Args:
        json_str: JSON 字符串或字节

    Returns:
        GameEvent 对象（PlayerEvent/AgentEvent/RandomEvent）
    """
    if isinstance(json_str, bytes):
        return game_event_adapter.validate_json(json_str)
    return game_event_adapter.validate_json(json_str.encode("utf-8"))


def serialize_national_data(data: NationalBaseData) -> str:
    """NationalBaseData → JSON 字符串。

    Args:
        data: 全国数据对象

    Returns:
        JSON 字符串
    """
    return data.model_dump_json()


def deserialize_national_data(json_str: str) -> NationalBaseData:
    """JSON 字符串 → NationalBaseData。

    Args:
        json_str: JSON 字符串

    Returns:
        NationalBaseData 对象
    """
    return NationalBaseData.model_validate_json(json_str)


def serialize_dict(data: dict[str, Any]) -> str:
    """dict → JSON 字符串。

    Args:
        data: 字典对象

    Returns:
        JSON 字符串
    """
    import json

    return json.dumps(data, ensure_ascii=False)


def deserialize_dict(json_str: str) -> dict[str, Any]:
    """JSON 字符串 → dict。

    Args:
        json_str: JSON 字符串

    Returns:
        字典对象
    """
    import json

    return json.loads(json_str)
