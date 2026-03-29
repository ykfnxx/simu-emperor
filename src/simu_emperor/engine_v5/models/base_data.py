"""Province and Nation data models (V5).

Migrated from V4 engine.models.base_data for V5 architecture.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict


@dataclass
class ProvinceData:
    """省级数据（简化为 4 个核心字段）"""

    province_id: str
    name: str
    production_value: Decimal
    population: Decimal
    fixed_expenditure: Decimal
    stockpile: Decimal
    base_production_growth: Decimal = field(default=Decimal("0.01"))
    base_population_growth: Decimal = field(default=Decimal("0.005"))
    tax_modifier: Decimal = field(default=Decimal("0.0"))

    def __post_init__(self):
        if self.production_value < 0:
            raise ValueError(
                f"ProvinceData.production_value must be >= 0, got {self.production_value}"
            )
        if self.population < 0:
            raise ValueError(f"ProvinceData.population must be >= 0, got {self.population}")
        if self.fixed_expenditure < 0:
            raise ValueError(
                f"ProvinceData.fixed_expenditure must be >= 0, got {self.fixed_expenditure}"
            )
        if self.stockpile < 0:
            raise ValueError(f"ProvinceData.stockpile must be >= 0, got {self.stockpile}")

        if not isinstance(self.production_value, Decimal):
            self.production_value = Decimal(str(self.production_value))
        if not isinstance(self.population, Decimal):
            self.population = Decimal(str(self.population))
        if not isinstance(self.fixed_expenditure, Decimal):
            self.fixed_expenditure = Decimal(str(self.fixed_expenditure))
        if not isinstance(self.stockpile, Decimal):
            self.stockpile = Decimal(str(self.stockpile))


@dataclass
class NationData:
    """国家数据"""

    turn: int
    base_tax_rate: Decimal = field(default=Decimal("0.10"))
    tribute_rate: Decimal = field(default=Decimal("0.8"))
    fixed_expenditure: Decimal = field(default=Decimal("0"))
    imperial_treasury: Decimal = field(default=Decimal("0"))
    provinces: Dict[str, ProvinceData] = field(default_factory=dict)

    def __post_init__(self):
        if self.turn < 0:
            raise ValueError(f"NationData.turn must be >= 0, got {self.turn}")

        if self.imperial_treasury < 0:
            raise ValueError(
                f"NationData.imperial_treasury must be >= 0, got {self.imperial_treasury}"
            )

        if not isinstance(self.base_tax_rate, Decimal):
            self.base_tax_rate = Decimal(str(self.base_tax_rate))
        if not isinstance(self.tribute_rate, Decimal):
            self.tribute_rate = Decimal(str(self.tribute_rate))
        if not isinstance(self.fixed_expenditure, Decimal):
            self.fixed_expenditure = Decimal(str(self.fixed_expenditure))
        if not isinstance(self.imperial_treasury, Decimal):
            self.imperial_treasury = Decimal(str(self.imperial_treasury))
