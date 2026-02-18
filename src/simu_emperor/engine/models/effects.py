"""事件效果模型：EventEffect 定义原子级数值变更操作。"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class EffectOperation(StrEnum):
    """效果操作类型。"""

    ADD = "add"
    MULTIPLY = "multiply"


class EffectScope(BaseModel):
    """效果影响范围。"""

    province_ids: list[str] = Field(default_factory=list, description="影响的省份 ID 列表")
    is_national: bool = Field(default=False, description="是否为全国性效果")


class EventEffect(BaseModel):
    """原子效果：对目标字段施加加法或乘法操作。"""

    target: str = Field(
        description="目标字段路径（如 population.total, commerce.market_prosperity）"
    )
    operation: EffectOperation = Field(description="操作类型：add 或 multiply")
    value: Decimal = Field(description="数值")
    scope: EffectScope = Field(default_factory=EffectScope, description="影响范围")
