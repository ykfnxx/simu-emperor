"""数据序列化工具 (V4).

V4 数据模型序列化：
- NationData, ProvinceData dataclass 与 JSON 互转
- 处理 Decimal 类型序列化/反序列化
"""

import json
import logging
from dataclasses import asdict
from decimal import Decimal
from typing import Any

from simu_emperor.engine.models.base_data import NationData, ProvinceData


logger = logging.getLogger(__name__)


def _decimal_to_str(obj: Any) -> Any:
    """递归将 Decimal 转换为字符串.

    Args:
        obj: 任意对象

    Returns:
        转换后的对象，Decimal 变为字符串
    """
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_str(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_str(item) for item in obj]
    return obj


# 已知 Decimal 字段白名单
# 只有这些字段名的字符串值才会被转换为 Decimal
DECIMAL_FIELDS = frozenset(
    {
        # ProvinceData Decimal 字段
        "production_value",
        "population",
        "fixed_expenditure",
        "stockpile",
        "base_production_growth",
        "base_population_growth",
        "tax_modifier",
        # NationData Decimal 字段
        "base_tax_rate",
        "tribute_rate",
        "imperial_treasury",
    }
)


def _str_to_decimal(obj: Any, path: str = "") -> Any:
    """递归将已知 Decimal 字段的字符串值转换回 Decimal.

    Args:
        obj: 任意对象
        path: 当前路径（用于识别字段名）

    Returns:
        转换后的对象，只有白名单字段的字符串变为 Decimal

    Note:
        使用字段名白名单确保 string 类型的 ID 字段（如 province_id）
        不会被错误转换为 Decimal。
    """
    if isinstance(obj, str):
        # 只转换已知 Decimal 字段的值
        field_name = path.split(".")[-1] if path else ""
        if field_name in DECIMAL_FIELDS:
            try:
                return Decimal(obj)
            except Exception:
                # 转换失败保持原样
                return obj
        return obj
    if isinstance(obj, dict):
        return {k: _str_to_decimal(v, f"{path}.{k}" if path else k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_str_to_decimal(item, f"{path}[{i}]") for i, item in enumerate(obj)]
    return obj


def serialize_nation_data(nation: NationData) -> str:
    """序列化 NationData 为 JSON 字符串.

    Args:
        nation: NationData 对象

    Returns:
        JSON 字符串
    """
    if nation is None:
        return "{}"

    # dataclass → dict
    nation_dict = asdict(nation)

    # Decimal → str
    nation_dict = _decimal_to_str(nation_dict)

    return json.dumps(nation_dict, ensure_ascii=False)


def deserialize_nation_data(json_str: str) -> NationData:
    """从 JSON 字符串反序列化 NationData.

    Args:
        json_str: JSON 字符串

    Returns:
        NationData 对象

    Raises:
        ValueError: 如果 JSON 格式无效
    """
    if not json_str or json_str == "{}":
        # 返回默认空状态
        return NationData(turn=0)

    try:
        # JSON → dict
        data = json.loads(json_str)

        # str → Decimal
        data = _str_to_decimal(data)

        # 重建 ProvinceData 对象（因为 asdict 会递归转换为 dict）
        provinces_dict = data.get("provinces", {})
        provinces = {}
        for province_id, province_dict in provinces_dict.items():
            provinces[province_id] = ProvinceData(**province_dict)
        data["provinces"] = provinces

        return NationData(**data)

    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.error(f"Failed to deserialize NationData: {e}")
        raise ValueError(f"Invalid NationData JSON: {e}") from e


def serialize_province_data(province: ProvinceData) -> str:
    """序列化 ProvinceData 为 JSON 字符串.

    Args:
        province: ProvinceData 对象

    Returns:
        JSON 字符串
    """
    if province is None:
        return "{}"

    province_dict = asdict(province)
    province_dict = _decimal_to_str(province_dict)

    return json.dumps(province_dict, ensure_ascii=False)


def deserialize_province_data(json_str: str) -> ProvinceData:
    """从 JSON 字符串反序列化 ProvinceData.

    Args:
        json_str: JSON 字符串

    Returns:
        ProvinceData 对象
    """
    if not json_str or json_str == "{}":
        raise ValueError("Invalid ProvinceData JSON: empty or None")

    try:
        data = json.loads(json_str)
        data = _str_to_decimal(data)
        return ProvinceData(**data)

    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.error(f"Failed to deserialize ProvinceData: {e}")
        raise ValueError(f"Invalid ProvinceData JSON: {e}") from e
