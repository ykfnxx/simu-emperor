"""简化的基础数据模型 (V4).

将原有复杂的嵌套模型简化为 4 个核心字段。
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict


@dataclass
class ProvinceData:
    """省级数据（简化为 4 个核心字段）

    V4 简化设计：
    - production_value: 产值（纯经济产出）
    - population: 人口
    - fixed_expenditure: 固定支出
    - stockpile: 库存
    """

    province_id: str
    name: str

    # 四大核心数据
    production_value: Decimal  # 产值（纯经济产出）
    population: Decimal         # 人口
    fixed_expenditure: Decimal  # 固定支出
    stockpile: Decimal          # 库存

    # 增长率（固定）
    base_production_growth: Decimal = field(default=Decimal("0.01"))   # 基础产值增长率 1%/tick
    base_population_growth: Decimal = field(default=Decimal("0.005"))  # 基础人口增长率 0.5%/tick

    # 税率修正
    tax_modifier: Decimal = field(default=Decimal("0.0"))  # 省级税率修正值


@dataclass
class NationData:
    """国家数据"""

    turn: int                           # 当前 tick 数
    base_tax_rate: Decimal = field(default=Decimal("0.10"))  # 全国统一基础税率 10%
    tribute_rate: Decimal = field(default=Decimal("0.8"))    # 上缴比例 80%
    fixed_expenditure: Decimal = field(default=Decimal("0")) # 国库固定支出
    imperial_treasury: Decimal = field(default=Decimal("0")) # 国库
    provinces: Dict[str, ProvinceData] = field(default_factory=dict)
