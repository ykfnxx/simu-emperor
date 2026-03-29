"""Economic calculation logic for V5 Engine.

Migrated from V4 engine.engine - contains pure economic calculation functions.
"""

import logging
from decimal import Decimal
from typing import Optional

from simu_emperor.engine_v5.models import NationData, ProvinceData, Incident, Effect


logger = logging.getLogger(__name__)


def apply_base_growth(state: NationData) -> None:
    """应用基础增长率（所有省份）

    production_value *= (1 + base_production_growth)
    population *= (1 + base_population_growth)
    """
    for province in state.provinces.values():
        province.production_value *= Decimal("1") + province.base_production_growth
        province.population *= Decimal("1") + province.base_population_growth


def apply_effects(state: NationData, incidents: list[Incident]) -> None:
    """应用所有活跃 Effect（按 target_path 叠加）

    对每个 target_path：
    - 累加所有未生效 Incident 的 add（applied == False）
    - 累加所有 factor
    - target = max(0, (target + sum_add) * (1 + sum_factor))
    """
    effect_groups: dict[str, list[tuple[Incident, Effect]]] = {}

    for incident in incidents:
        for effect in incident.effects:
            if effect.target_path not in effect_groups:
                effect_groups[effect.target_path] = []
            effect_groups[effect.target_path].append((incident, effect))

    incident_ids_with_add_effects: set[str] = set()

    for target_path, incident_effects in effect_groups.items():
        try:
            target = resolve_path(state, target_path)
            if target is None:
                logger.warning(f"Failed to resolve path: {target_path}")
                continue

            sum_add = Decimal("0")
            sum_factor = Decimal("0")

            for incident, effect in incident_effects:
                if effect.add is not None and not incident.applied:
                    sum_add += effect.add
                    incident_ids_with_add_effects.add(incident.incident_id)
                if effect.factor is not None:
                    sum_factor += effect.factor

            new_value = (target + sum_add) * (Decimal("1") + sum_factor)
            new_value = max(Decimal("0"), new_value)

            set_path_value(state, target_path, new_value)

        except Exception as e:
            logger.error(f"Error applying effects to {target_path}: {e}")

    for incident in incidents:
        if incident.incident_id in incident_ids_with_add_effects:
            incident.applied = True


def resolve_path(state: NationData, path: str) -> Optional[Decimal]:
    """解析路径并获取目标值

    Args:
        path: Dot-notation path, e.g. "provinces.zhili.production_value"
    """
    parts = path.split(".")

    if parts[0] == "provinces" and len(parts) == 3:
        province_id = parts[1]
        field = parts[2]

        if province_id not in state.provinces:
            return None

        province = state.provinces[province_id]
        return getattr(province, field, None)
    elif parts[0] == "nation" and len(parts) == 2:
        field = parts[1]
        return getattr(state, field, None)

    return None


def set_path_value(state: NationData, path: str, value: Decimal) -> None:
    """设置路径对应的值"""
    parts = path.split(".")

    if parts[0] == "provinces" and len(parts) == 3:
        province_id = parts[1]
        field = parts[2]

        if province_id in state.provinces:
            province = state.provinces[province_id]
            setattr(province, field, value)
    elif parts[0] == "nation" and len(parts) == 2:
        field = parts[1]
        setattr(state, field, value)


def calculate_tax_and_treasury(state: NationData) -> None:
    """计算税收和国库更新

    各省结算：
      省级税收 = production_value × (base_tax_rate + tax_modifier)
      省级结余 = 省级税收 - 省级固定支出
      省级上缴 = 省级结余 > 0 ? 省级结余 × tribute_rate : 0
      省级库存 += 省级结余 - 省级上缴
      省级库存 = max(0, 省级库存)

    国库结算：
      imperial_treasury += sum(各省上缴) - 国库固定支出
      imperial_treasury = max(0, imperial_treasury)
    """
    total_remittance = Decimal("0")

    for province in state.provinces.values():
        province_tax = province.production_value * (state.base_tax_rate + province.tax_modifier)

        province_surplus = province_tax - province.fixed_expenditure

        if province_surplus > 0:
            province_remittance = province_surplus * state.tribute_rate
        else:
            province_remittance = Decimal("0")

        province.stockpile += province_surplus - province_remittance
        province.stockpile = max(Decimal("0"), province.stockpile)

        total_remittance += province_remittance

    state.imperial_treasury += total_remittance - state.fixed_expenditure
    state.imperial_treasury = max(Decimal("0"), state.imperial_treasury)


def refresh_incidents(incidents: list[Incident]) -> list[Incident]:
    """刷新 Incident 状态

    每个 Incident.remaining_ticks -= 1
    移除 remaining_ticks == 0 的 Incident

    Returns:
        过期的 Incident 列表
    """
    for incident in incidents:
        incident.remaining_ticks -= 1

    expired = [inc for inc in incidents if inc.remaining_ticks <= 0]

    return expired


def process_tick(state: NationData, incidents: list[Incident]) -> list[Incident]:
    """完整处理一个 tick 的经济计算

    计算流程：
    1. 应用基础增长率（所有省份）
    2. 应用所有活跃 Effect（按 target_path 叠加）
    3. 计算税收和国库更新
    4. 刷新 Incident 状态
    5. 增加 tick 计数

    Returns:
        过期的 Incident 列表
    """
    apply_base_growth(state)
    apply_effects(state, incidents)
    calculate_tax_and_treasury(state)
    expired = refresh_incidents(incidents)
    state.turn += 1

    return expired
