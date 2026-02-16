"""事件模板模型：定义随机事件的生成规则。"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from simu_emperor.engine.models.effects import EffectOperation


class EffectTemplate(BaseModel):
    """效果模板：定义效果的范围和值范围。"""

    target: str = Field(description="目标字段路径（如 population.total, granary_stock）")
    operation: EffectOperation = Field(description="操作类型：add 或 multiply")
    value_min: Decimal = Field(description="最小值")
    value_max: Decimal = Field(description="最大值")
    scope_type: Literal["province", "national", "all_provinces"] = Field(
        default="province", description="范围类型"
    )


class EventTemplate(BaseModel):
    """事件模板：定义随机事件的生成规则。"""

    template_id: str = Field(description="模板唯一标识")
    category: str = Field(description="事件分类（如 disaster, blessing, unrest）")
    weight: Decimal = Field(default=Decimal("1.0"), ge=0, description="被选中的相对权重")
    severity_min: Decimal = Field(default=Decimal("0.1"), ge=0, le=1, description="最小严重程度")
    severity_max: Decimal = Field(default=Decimal("1.0"), ge=0, le=1, description="最大严重程度")
    duration_min: int = Field(default=1, ge=1, description="最小持续回合数")
    duration_max: int = Field(default=1, ge=1, description="最大持续回合数")
    description_templates: list[str] = Field(
        min_length=1, description="描述模板列表，支持 {province} 占位符"
    )
    effects: list[EffectTemplate] = Field(default_factory=list, description="效果模板列表")
