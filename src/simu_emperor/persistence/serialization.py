"""
数据序列化工具（V2）

简化设计：只处理核心数据结构的序列化。
"""

import json
from typing import Any

from simu_emperor.engine.models.base_data import NationalBaseData


def serialize_national_data(data: NationalBaseData) -> str:
    """
    序列化国家数据为 JSON

    Args:
        data: NationalBaseData 对象

    Returns:
        JSON 字符串
    """
    if data is None:
        return "{}"
    return data.model_dump_json()


def deserialize_national_data(json_str: str) -> dict[str, Any]:
    """
    反序列化 JSON 为字典

    Args:
        json_str: JSON 字符串

    Returns:
        数据字典
    """
    if not json_str:
        return {}
    return json.loads(json_str)


def serialize_game_state(state: dict[str, Any]) -> str:
    """
    序列化游戏状态

    Args:
        state: 游戏状态字典

    Returns:
        JSON 字符串
    """
    return json.dumps(state, ensure_ascii=False, default=str)


def deserialize_game_state(json_str: str) -> dict[str, Any]:
    """
    反序列化游戏状态

    Args:
        json_str: JSON 字符串

    Returns:
        游戏状态字典
    """
    if not json_str:
        return {}
    return json.loads(json_str)
