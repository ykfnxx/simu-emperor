"""回合计算指标模型：每回合由公式计算的派生值，不存储在 NationalBaseData 中。"""

from decimal import Decimal

from pydantic import BaseModel, Field


class ProvinceTurnMetrics(BaseModel):
    """省份单回合计算指标。"""

    province_id: str = Field(description="省份唯一标识")

    # 粮食
    food_production: Decimal = Field(description="粮食产量(石)")
    food_demand_civilian: Decimal = Field(description="平民粮食需求(石)")
    food_demand_military: Decimal = Field(description="军事粮食需求(石)")
    food_demand_total: Decimal = Field(description="粮食总需求(石)")
    food_surplus: Decimal = Field(description="粮食盈余(石)")
    granary_change: Decimal = Field(description="粮仓变动(石)")

    # 财政收入
    land_tax_revenue: Decimal = Field(description="田赋收入(两)")
    commercial_tax_revenue: Decimal = Field(description="商税收入(两)")
    trade_tariff_revenue: Decimal = Field(description="关税收入(两)")
    total_revenue: Decimal = Field(description="财政总收入(两)")

    # 财政支出
    military_upkeep: Decimal = Field(description="军事维持费(两)")
    official_salary_cost: Decimal = Field(description="官吏薪俸(两)")
    infrastructure_cost: Decimal = Field(description="基建维护费(两)")
    court_levy_cost: Decimal = Field(description="朝廷征派(两)")
    total_expenditure: Decimal = Field(description="财政总支出(两)")
    fiscal_surplus: Decimal = Field(description="财政盈余(两)")

    # 变动量
    population_change: Decimal = Field(description="人口变动")
    happiness_change: Decimal = Field(description="幸福度变动")
    treasury_change: Decimal = Field(description="地方财政变动(两)")


class NationalTurnMetrics(BaseModel):
    """全国单回合计算指标。"""

    turn: int = Field(ge=0, description="回合数")
    province_metrics: list[ProvinceTurnMetrics] = Field(description="各省份指标")
    imperial_treasury_change: Decimal = Field(description="国库变动(两)")
    tribute_total: Decimal = Field(description="上缴总额(两)")
