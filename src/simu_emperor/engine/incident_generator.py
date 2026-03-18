"""随机 Incident 生成器 (V4).

根据模板和概率生成随机游戏事件，由 TickCoordinator 定期调用。
"""

import logging
import random
from dataclasses import dataclass, field
from decimal import Decimal

from simu_emperor.config import IncidentConfig
from simu_emperor.engine.models.base_data import NationData
from simu_emperor.engine.models.incident import Effect, Incident

logger = logging.getLogger(__name__)


@dataclass
class IncidentTemplate:
    """Incident 模板定义."""

    template_id: str
    title_template: str  # 含 {province_name} 占位符
    description_template: str
    effects: list[dict]  # effect 骨架，target_path 含 {province} 占位符
    duration_ticks: int
    probability: float  # 单次检查触发概率


DEFAULT_TEMPLATES = [
    IncidentTemplate(
        template_id="harvest_boom",
        title_template="{province_name}大丰收",
        description_template="{province_name}风调雨顺，粮食产量大增，百姓安居乐业。",
        effects=[
            {"target_path": "provinces.{province}.production_value", "factor": "0.15"},
            {"target_path": "provinces.{province}.stockpile", "add": "2000"},
        ],
        duration_ticks=2,
        probability=0.02,
    ),
    IncidentTemplate(
        template_id="drought",
        title_template="{province_name}旱灾",
        description_template="{province_name}久旱无雨，田地龟裂，庄稼枯萎，民生困苦。",
        effects=[
            {"target_path": "provinces.{province}.production_value", "factor": "-0.20"},
            {"target_path": "provinces.{province}.population", "factor": "-0.02"},
        ],
        duration_ticks=4,
        probability=0.01,
    ),
    IncidentTemplate(
        template_id="flood",
        title_template="{province_name}水灾",
        description_template="{province_name}连日暴雨，河水泛滥，良田被淹，仓储受损。",
        effects=[
            {"target_path": "provinces.{province}.production_value", "factor": "-0.25"},
            {"target_path": "provinces.{province}.stockpile", "add": "-3000"},
        ],
        duration_ticks=3,
        probability=0.008,
    ),
    IncidentTemplate(
        template_id="pest_outbreak",
        title_template="{province_name}虫害",
        description_template="{province_name}蝗虫过境，庄稼被啃食殆尽，产值骤降。",
        effects=[
            {"target_path": "provinces.{province}.production_value", "factor": "-0.15"},
        ],
        duration_ticks=2,
        probability=0.015,
    ),
    IncidentTemplate(
        template_id="population_growth",
        title_template="{province_name}人口增长",
        description_template="{province_name}太平盛世，百姓安居，人口快速增长。",
        effects=[
            {"target_path": "provinces.{province}.population", "factor": "0.03"},
        ],
        duration_ticks=4,
        probability=0.03,
    ),
]


class IncidentGenerator:
    """随机 Incident 生成器.

    根据模板和概率生成随机游戏事件。
    由 TickCoordinator 按 check_interval_ticks 间隔调用。
    """

    def __init__(
        self,
        config: IncidentConfig,
        rng: random.Random,
        province_names: dict[str, str],
    ):
        """初始化生成器.

        Args:
            config: Incident 配置
            rng: 随机数生成器（支持 seed 确定性）
            province_names: {province_id: display_name} 映射
        """
        self._config = config
        self._rng = rng
        self._templates: list[IncidentTemplate] = list(DEFAULT_TEMPLATES)
        self._province_names = province_names
        self._counter = 0

    def generate(self, state: NationData, active_count: int) -> list[Incident]:
        """检查所有模板，返回触发的 incidents（可能为空）.

        Args:
            state: 当前游戏状态
            active_count: 当前活跃的系统 incident 数

        Returns:
            触发的 Incident 列表
        """
        if not self._config.enabled:
            return []

        if active_count >= self._config.max_active_system_incidents:
            return []

        if not state.provinces:
            return []

        province_ids = list(state.provinces.keys())
        results = []

        for template in self._templates:
            if self._rng.random() > template.probability:
                continue

            # 达到上限则停止
            if active_count + len(results) >= self._config.max_active_system_incidents:
                break

            province_id = self._rng.choice(province_ids)
            province_name = self._province_names.get(province_id, province_id)

            effects = self._build_effects(template.effects, province_id)
            self._counter += 1

            incident = Incident(
                incident_id=f"inc_sys_{self._counter:06d}",
                title=template.title_template.format(province_name=province_name),
                description=template.description_template.format(province_name=province_name),
                effects=effects,
                source="system:incident_generator",
                remaining_ticks=template.duration_ticks,
            )
            results.append(incident)

        return results

    @staticmethod
    def _build_effects(effect_skeletons: list[dict], province_id: str) -> list[Effect]:
        """从模板骨架构建 Effect 列表，替换 {province} 占位符.

        Args:
            effect_skeletons: 模板中的 effect 定义
            province_id: 目标省份 ID

        Returns:
            Effect 对象列表
        """
        effects = []
        for skeleton in effect_skeletons:
            target_path = skeleton["target_path"].replace("{province}", province_id)
            add = Decimal(skeleton["add"]) if "add" in skeleton else None
            factor = Decimal(skeleton["factor"]) if "factor" in skeleton else None
            effects.append(Effect(target_path=target_path, add=add, factor=factor))
        return effects
