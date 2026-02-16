"""基础数据模型：以省（Province）为核心单位的多层经济子模型。"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class CropType(StrEnum):
    """作物类型枚举。"""

    RICE = "rice"
    WHEAT = "wheat"
    MILLET = "millet"
    TEA = "tea"
    SILK_MULBERRY = "silk_mulberry"


class PopulationData(BaseModel):
    """人口统计数据。"""

    total: Decimal = Field(ge=0, description="总人口")
    growth_rate: Decimal = Field(description="人口增长率")
    labor_ratio: Decimal = Field(ge=0, le=1, description="劳动力占比")
    happiness: Decimal = Field(ge=0, le=1, description="民众幸福度")


class CropData(BaseModel):
    """单一作物数据。"""

    crop_type: CropType = Field(description="作物类型")
    area_mu: Decimal = Field(ge=0, description="种植面积（亩）")
    yield_per_mu: Decimal = Field(ge=0, description="亩产量")


class AgricultureData(BaseModel):
    """农业部门数据。"""

    crops: list[CropData] = Field(default_factory=list, description="作物列表")
    irrigation_level: Decimal = Field(ge=0, le=1, description="灌溉水平")


class CommerceData(BaseModel):
    """商业部门数据。"""

    merchant_households: Decimal = Field(ge=0, description="商户数量")
    tax_rate: Decimal = Field(ge=0, le=1, description="商业税率")
    market_prosperity: Decimal = Field(ge=0, le=1, description="市场繁荣度")


class TradeData(BaseModel):
    """贸易部门数据。"""

    trade_volume: Decimal = Field(ge=0, description="贸易量")
    tariff_rate: Decimal = Field(ge=0, le=1, description="关税税率")
    trade_route_quality: Decimal = Field(ge=0, le=1, description="贸易路线质量")


class MilitaryData(BaseModel):
    """军事数据。"""

    garrison_size: Decimal = Field(ge=0, description="驻军规模")
    equipment_level: Decimal = Field(ge=0, le=1, description="装备水平")
    morale: Decimal = Field(ge=0, le=1, description="士气")
    upkeep: Decimal = Field(ge=0, description="维持费用")


class ProvinceBaseData(BaseModel):
    """完整省份数据，包含所有经济子模型。"""

    province_id: str = Field(description="省份唯一标识")
    name: str = Field(description="省份名称")
    population: PopulationData = Field(description="人口数据")
    agriculture: AgricultureData = Field(description="农业数据")
    commerce: CommerceData = Field(description="商业数据")
    trade: TradeData = Field(description="贸易数据")
    military: MilitaryData = Field(description="军事数据")
    granary_stock: Decimal = Field(ge=0, description="粮仓储量")
    local_treasury: Decimal = Field(ge=0, description="地方财政")


class NationalBaseData(BaseModel):
    """全国数据，聚合所有省份。"""

    turn: int = Field(ge=0, description="当前回合数")
    imperial_treasury: Decimal = Field(ge=0, description="国库")
    national_tax_modifier: Decimal = Field(default=Decimal("1.0"), description="全国税率修正")
    provinces: list[ProvinceBaseData] = Field(default_factory=list, description="省份列表")
