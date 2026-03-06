"""事件生成器：从模板池生成随机事件。

TODO: 当前版本未使用，未来版本启用。
保留此模块为未来功能预留。
"""

import json
import random
from decimal import Decimal
from pathlib import Path

from simu_emperor.engine.models.effects import EffectScope, EventEffect
from simu_emperor.engine.models.event_templates import EffectTemplate, EventTemplate
from simu_emperor.engine.models.events import RandomEvent


def load_event_templates(path: str | Path) -> list[EventTemplate]:
    """从 JSON 文件加载事件模板池。

    Args:
        path: 模板文件路径

    Returns:
        事件模板列表
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return [EventTemplate.model_validate(item) for item in data]


def _random_decimal(rng: random.Random, min_val: Decimal, max_val: Decimal) -> Decimal:
    """在范围内生成随机 Decimal 值。"""
    # 使用整数计算避免浮点精度问题
    scale = Decimal("10000")
    min_scaled = int(min_val * scale)
    max_scaled = int(max_val * scale)
    result = rng.randint(min_scaled, max_scaled)
    return Decimal(result) / scale


def _generate_effect(
    template: EffectTemplate,
    province_ids: list[str],
    target_province: str,
    rng: random.Random,
) -> EventEffect:
    """基于效果模板生成具体效果。

    Args:
        template: 效果模板
        province_ids: 所有省份 ID 列表
        target_province: 统一的目标省份（用于 province scope，确保与描述一致）
        rng: 随机数生成器
    """
    # 计算效果值
    value = _random_decimal(rng, template.value_min, template.value_max)

    # 确定范围
    scope = EffectScope()
    if template.scope_type == "national":
        scope.is_national = True
    elif template.scope_type == "all_provinces":
        scope.province_ids = province_ids
    else:  # province
        # 使用统一的目标省份，确保与描述一致
        scope.province_ids = [target_province]

    return EventEffect(
        target=template.target,
        operation=template.operation,
        value=value,
        scope=scope,
    )


def generate_random_event(
    template: EventTemplate,
    turn: int,
    province_ids: list[str],
    rng: random.Random,
) -> RandomEvent:
    """基于模板生成单个随机事件。

    Args:
        template: 事件模板
        turn: 当前回合数
        province_ids: 可选的省份 ID 列表
        rng: 随机数生成器

    Returns:
        生成的随机事件
    """
    # 随机生成严重程度
    severity = _random_decimal(rng, template.severity_min, template.severity_max)

    # 随机生成持续时间
    duration = rng.randint(template.duration_min, template.duration_max)

    # 随机选择目标省份（用于描述模板）
    target_province = rng.choice(province_ids) if province_ids else "全国"

    # 填充描述模板
    description_template = rng.choice(template.description_templates)
    description = description_template.format(province=target_province)

    # 生成效果（传入 target_province 确保与描述一致）
    effects = [
        _generate_effect(effect_template, province_ids, target_province, rng)
        for effect_template in template.effects
    ]

    return RandomEvent(
        source="random",
        category=template.category,
        severity=severity,
        turn_created=turn,
        description=description,
        effects=effects,
        duration=duration,
    )


def generate_events_for_turn(
    templates: list[EventTemplate],
    turn: int,
    province_ids: list[str],
    rng: random.Random,
    max_events: int = 2,
) -> list[RandomEvent]:
    """为当前回合生成随机事件列表。

    使用加权随机选择，从模板池中选择 0 到 max_events 个模板，
    然后基于每个选中的模板生成具体事件。

    Args:
        templates: 事件模板列表
        turn: 当前回合数
        province_ids: 可选的省份 ID 列表
        rng: 随机数生成器（需保证可复现性）
        max_events: 最大事件数量

    Returns:
        生成的随机事件列表
    """
    if not templates or not province_ids:
        return []

    # 计算权重
    weights = [float(t.weight) for t in templates]

    # 决定生成多少个事件（0 到 max_events）
    # 使用泊松分布的简化版本，平均值约为 max_events / 2
    num_events = rng.randint(0, max_events)

    if num_events == 0:
        return []

    # 加权随机选择模板（不放回）
    selected_templates: list[EventTemplate] = []
    available_indices = list(range(len(templates)))
    available_weights = weights.copy()

    for _ in range(num_events):
        if not available_indices:
            break

        # 计算当前可用模板的总权重
        current_total = sum(available_weights)
        if current_total <= 0:
            break

        # 加权随机选择
        r = rng.random() * current_total
        cumulative = 0.0
        selected_idx = 0

        for i, w in enumerate(available_weights):
            cumulative += w
            if r <= cumulative:
                selected_idx = i
                break

        # 添加选中的模板
        original_idx = available_indices[selected_idx]
        selected_templates.append(templates[original_idx])

        # 移除已选中的模板（不放回）
        available_indices.pop(selected_idx)
        available_weights.pop(selected_idx)

    # 基于选中的模板生成事件
    events = [
        generate_random_event(template, turn, province_ids, rng) for template in selected_templates
    ]

    return events
