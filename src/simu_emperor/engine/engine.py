"""游戏引擎核心 - 处理 tick 计算和 Incident 管理 (V4)."""

import logging
from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING

from simu_emperor.engine.models.base_data import NationData
from simu_emperor.engine.models.incident import Incident, Effect


if TYPE_CHECKING:
    from simu_emperor.event_bus.core import EventBus
    from simu_emperor.event_bus.event import Event


logger = logging.getLogger(__name__)


class Engine:
    """游戏引擎核心 - 处理 tick 计算和 Incident 管理

    状态所有权说明（V4 设计）：
    - Engine 拥有并独占修改 NationData 及其下属 ProvinceData
    - 状态采用原地突变（in-place mutation）而非不可变更新
    - 这与 V1/V2/V3 的不可变模式不同，是为了简化 V4 的 tick 频繁更新场景
    - 调用方不应持有对 state 对象的引用并在外部修改
    - 如需获取状态快照，请使用 copy.deepcopy(engine.get_state())
    """

    def __init__(self, initial_state: NationData, event_bus: Optional["EventBus"] = None):
        self.state = initial_state
        self.active_incidents: List[Incident] = []
        self.event_bus = event_bus

        if event_bus:
            event_bus.subscribe("system:engine", self._on_incident_created)

    def apply_tick(self) -> NationData:
        """应用一个 tick，返回新状态

        Tick 计算流程：
        1. 应用基础增长率（所有省份）
        2. 应用所有活跃 Effect（按 target_path 叠加）
        3. 计算税收和国库更新
        4. 刷新 Incident 状态

        Returns:
            新的 NationData 状态
        """
        # 1. 应用基础增长率
        self._apply_base_growth()

        # 2. 应用所有活跃 Effect
        self._apply_effects()

        # 3. 计算税收和国库更新
        self._calculate_tax_and_treasury()

        # 4. 刷新 Incident 状态
        self._refresh_incidents()

        # 5. 增加 tick 计数
        self.state.turn += 1

        return self.state

    def _apply_base_growth(self) -> None:
        """应用基础增长率（所有省份）

        production_value *= (1 + base_production_growth)
        population *= (1 + base_population_growth)
        """
        for province in self.state.provinces.values():
            province.production_value *= Decimal("1") + province.base_production_growth
            province.population *= Decimal("1") + province.base_population_growth

    def _apply_effects(self) -> None:
        """应用所有活跃 Effect（按 target_path 叠加）

        对每个 target_path：
        - 累加所有未生效 Incident 的 add（applied == False）
        - 累加所有 factor
        - target = max(0, (target + sum_add) * (1 + sum_factor))

        注意：Incident.applied 标记在所有 target_path 处理完成后统一设置
        """
        # 按 target_path 分组 Effect
        effect_groups: dict[str, list[tuple[Incident, Effect]]] = {}

        for incident in self.active_incidents:
            for effect in incident.effects:
                if effect.target_path not in effect_groups:
                    effect_groups[effect.target_path] = []
                effect_groups[effect.target_path].append((incident, effect))

        # 收集所有有 add 效果的 Incident ID（用于后续统一标记）
        # 使用 incident_id 而不是 Incident 对象，因为 dataclass 默认不可哈希
        incident_ids_with_add_effects: set[str] = set()

        # 对每个 target_path 应用 Effect
        for target_path, incident_effects in effect_groups.items():
            try:
                # 解析路径并获取目标值
                target = self._resolve_path(target_path)
                if target is None:
                    logger.warning(f"Failed to resolve path: {target_path}")
                    continue

                # 累加 add 和 factor
                sum_add = Decimal("0")
                sum_factor = Decimal("0")

                for incident, effect in incident_effects:
                    if effect.add is not None and not incident.applied:
                        sum_add += effect.add
                        incident_ids_with_add_effects.add(incident.incident_id)
                    if effect.factor is not None:
                        sum_factor += effect.factor

                # 应用公式：target = max(0, (target + sum_add) * (1 + sum_factor))
                new_value = (target + sum_add) * (Decimal("1") + sum_factor)
                new_value = max(Decimal("0"), new_value)

                # 写回新值
                self._set_path_value(target_path, new_value)

            except Exception as e:
                logger.error(f"Error applying effects to {target_path}: {e}")

        # 所有 target_path 处理完成后，统一标记 Incident.applied = True
        # 这样确保一个 Incident 的所有 add 效果都被应用后才标记
        for incident in self.active_incidents:
            if incident.incident_id in incident_ids_with_add_effects:
                incident.applied = True

    def _resolve_path(self, path: str) -> Optional[Decimal]:
        """解析路径并获取目标值

        Args:
            path: Dot-notation path, e.g. "provinces.zhili.production_value"

        Returns:
            Current value at path, or None if path is invalid
        """
        parts = path.split(".")

        if parts[0] == "provinces" and len(parts) == 3:
            # provinces.{province_id}.{field}
            province_id = parts[1]
            field = parts[2]

            if province_id not in self.state.provinces:
                return None

            province = self.state.provinces[province_id]
            return getattr(province, field, None)
        elif parts[0] == "nation" and len(parts) == 2:
            # nation.{field}
            field = parts[1]
            return getattr(self.state, field, None)

        return None

    def _set_path_value(self, path: str, value: Decimal) -> None:
        """设置路径对应的值

        Args:
            path: Dot-notation path
            value: New value to set
        """
        parts = path.split(".")

        if parts[0] == "provinces" and len(parts) == 3:
            province_id = parts[1]
            field = parts[2]

            if province_id in self.state.provinces:
                province = self.state.provinces[province_id]
                setattr(province, field, value)
        elif parts[0] == "nation" and len(parts) == 2:
            field = parts[1]
            setattr(self.state, field, value)

    def _calculate_tax_and_treasury(self) -> None:
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

        for province in self.state.provinces.values():
            # 省级税收 = production_value × (base_tax_rate + tax_modifier)
            province_tax = province.production_value * (
                self.state.base_tax_rate + province.tax_modifier
            )

            # 省级结余 = 省级税收 - 省级固定支出
            province_surplus = province_tax - province.fixed_expenditure

            # 省级上缴 = 省级结余 > 0 ? 省级结余 × tribute_rate : 0
            if province_surplus > 0:
                province_remittance = province_surplus * self.state.tribute_rate
            else:
                province_remittance = Decimal("0")

            # 省级库存 += 省级结余 - 省级上缴
            province.stockpile += province_surplus - province_remittance

            # 省级库存 = max(0, 省级库存)
            province.stockpile = max(Decimal("0"), province.stockpile)

            total_remittance += province_remittance

        # 国库结算：imperial_treasury += sum(各省上缴) - 国库固定支出
        self.state.imperial_treasury += total_remittance - self.state.fixed_expenditure

        # imperial_treasury = max(0, imperial_treasury)
        self.state.imperial_treasury = max(Decimal("0"), self.state.imperial_treasury)

    def _refresh_incidents(self) -> None:
        """刷新 Incident 状态

        每个 Incident.remaining_ticks -= 1
        移除 remaining_ticks == 0 的 Incident
        """
        # 减少剩余 tick
        for incident in self.active_incidents:
            incident.remaining_ticks -= 1

        # 移除已到期的 Incident
        self.active_incidents = [inc for inc in self.active_incidents if inc.remaining_ticks > 0]

    def add_incident(self, incident: Incident) -> None:
        """添加新的 Incident

        Args:
            incident: Incident to add
        """
        if incident.remaining_ticks <= 0:
            raise ValueError(
                f"Incident remaining_ticks must be > 0, got {incident.remaining_ticks}"
            )
        self.active_incidents.append(incident)

    def remove_incident(self, incident_id: str) -> None:
        """移除指定 Incident

        Args:
            incident_id: ID of incident to remove
        """
        self.active_incidents = [
            inc for inc in self.active_incidents if inc.incident_id != incident_id
        ]

    def get_active_incidents(self) -> List[Incident]:
        """获取所有活跃的 Incident

        Returns:
            Copy of active incidents list
        """
        return self.active_incidents.copy()

    def get_state(self) -> NationData:
        """获取当前状态

        Returns:
            Current game state
        """
        return self.state

    async def _on_incident_created(self, event: "Event") -> None:
        if event.type != "incident_created":
            return

        effects = []
        for eff_data in event.payload["effects"]:
            effect = Effect(
                target_path=eff_data["target_path"],
                add=Decimal(eff_data["add"]) if eff_data.get("add") else None,
                factor=Decimal(eff_data["factor"]) if eff_data.get("factor") else None,
            )
            effects.append(effect)

        incident = Incident(
            incident_id=event.payload["incident_id"],
            title=event.payload["title"],
            description=event.payload["description"],
            effects=effects,
            source=event.payload["source"],
            remaining_ticks=event.payload["remaining_ticks"],
            applied=False,
        )

        self.add_incident(incident)
        logger.info(f"Engine received incident: {incident.incident_id}")
