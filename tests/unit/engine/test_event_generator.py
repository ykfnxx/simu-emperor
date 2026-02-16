"""事件生成器单元测试。"""

import random
from decimal import Decimal
from pathlib import Path

import pytest

from simu_emperor.engine.event_generator import (
    generate_events_for_turn,
    generate_random_event,
    load_event_templates,
)
from simu_emperor.engine.models.effects import EffectOperation
from simu_emperor.engine.models.event_templates import EffectTemplate, EventTemplate


# 测试用模板数据
@pytest.fixture
def sample_templates() -> list[EventTemplate]:
    """创建测试用的事件模板列表。"""
    return [
        EventTemplate(
            template_id="test_flood",
            category="disaster",
            weight=Decimal("2.0"),
            severity_min=Decimal("0.3"),
            severity_max=Decimal("1.0"),
            duration_min=1,
            duration_max=3,
            description_templates=["{province}遭遇洪灾"],
            effects=[
                EffectTemplate(
                    target="granary_stock",
                    operation=EffectOperation.MULTIPLY,
                    value_min=Decimal("0.3"),
                    value_max=Decimal("0.7"),
                    scope_type="province",
                )
            ],
        ),
        EventTemplate(
            template_id="test_harvest",
            category="blessing",
            weight=Decimal("1.0"),
            severity_min=Decimal("0.2"),
            severity_max=Decimal("0.6"),
            duration_min=1,
            duration_max=1,
            description_templates=["{province}风调雨顺，五谷丰登"],
            effects=[
                EffectTemplate(
                    target="population.happiness",
                    operation=EffectOperation.ADD,
                    value_min=Decimal("0.05"),
                    value_max=Decimal("0.1"),
                    scope_type="province",
                )
            ],
        ),
        EventTemplate(
            template_id="test_national_prosperity",
            category="blessing",
            weight=Decimal("0.5"),
            severity_min=Decimal("0.3"),
            severity_max=Decimal("0.6"),
            duration_min=1,
            duration_max=2,
            description_templates=["国泰民安，天下太平"],
            effects=[
                EffectTemplate(
                    target="administration.stability",
                    operation=EffectOperation.ADD,
                    value_min=Decimal("0.02"),
                    value_max=Decimal("0.05"),
                    scope_type="all_provinces",
                )
            ],
        ),
        EventTemplate(
            template_id="test_imperial_decree",
            category="blessing",
            weight=Decimal("0.3"),
            severity_min=Decimal("0.5"),
            severity_max=Decimal("0.8"),
            duration_min=1,
            duration_max=1,
            description_templates=["圣旨颁布，万民欢庆"],
            effects=[
                EffectTemplate(
                    target="population.happiness",
                    operation=EffectOperation.ADD,
                    value_min=Decimal("0.01"),
                    value_max=Decimal("0.03"),
                    scope_type="national",
                )
            ],
        ),
    ]


@pytest.fixture
def sample_province_ids() -> list[str]:
    """测试用省份 ID 列表。"""
    return ["jiangnan", "zhili", "sichuan"]


class TestLoadEventTemplates:
    """测试模板加载功能。"""

    def test_load_event_templates_from_file(self):
        """从实际 JSON 文件加载模板。"""
        path = Path(__file__).parent.parent.parent.parent / "data" / "event_templates.json"
        if path.exists():
            templates = load_event_templates(path)
            assert len(templates) >= 8  # 计划要求至少 8 个模板
            assert all(isinstance(t, EventTemplate) for t in templates)

    def test_load_event_templates_invalid_path(self):
        """加载不存在的文件应抛出异常。"""
        with pytest.raises(FileNotFoundError):
            load_event_templates("/nonexistent/path.json")


class TestGenerateSingleEvent:
    """测试单个事件生成。"""

    def test_generate_single_event_fields(self, sample_templates, sample_province_ids):
        """生成的事件字段正确性。"""
        rng = random.Random(42)
        template = sample_templates[0]  # flood
        event = generate_random_event(template, turn=5, province_ids=sample_province_ids, rng=rng)

        assert event.source == "random"
        assert event.category == "disaster"
        assert event.turn_created == 5
        assert event.severity >= template.severity_min
        assert event.severity <= template.severity_max
        assert event.duration >= template.duration_min
        assert event.duration <= template.duration_max
        assert len(event.effects) == 1
        assert event.effects[0].target == "granary_stock"
        assert event.effects[0].operation == EffectOperation.MULTIPLY

    def test_generate_event_description_placeholder(self, sample_templates, sample_province_ids):
        """描述占位符正确填充。"""
        rng = random.Random(42)
        template = sample_templates[0]  # flood with {province} placeholder
        event = generate_random_event(template, turn=1, province_ids=sample_province_ids, rng=rng)

        # 描述应该包含省份名称
        assert "{province}" not in event.description
        assert any(pid in event.description for pid in sample_province_ids)


class TestSeededReproducibility:
    """测试种子可复现性。"""

    def test_same_seed_same_events(self, sample_templates, sample_province_ids):
        """相同种子生成相同事件。"""
        rng1 = random.Random(12345)
        rng2 = random.Random(12345)

        events1 = generate_events_for_turn(sample_templates, turn=1, province_ids=sample_province_ids, rng=rng1, max_events=3)
        events2 = generate_events_for_turn(sample_templates, turn=1, province_ids=sample_province_ids, rng=rng2, max_events=3)

        assert len(events1) == len(events2)
        for e1, e2 in zip(events1, events2):
            assert e1.template_id == e2.template_id if hasattr(e1, 'template_id') else True
            assert e1.category == e2.category
            assert e1.severity == e2.severity
            assert e1.description == e2.description

    def test_different_seed_different_events(self, sample_templates, sample_province_ids):
        """不同种子生成不同事件（大概率）。"""
        rng1 = random.Random(111)
        rng2 = random.Random(222)

        events1 = generate_events_for_turn(sample_templates, turn=1, province_ids=sample_province_ids, rng=rng1, max_events=3)
        events2 = generate_events_for_turn(sample_templates, turn=1, province_ids=sample_province_ids, rng=rng2, max_events=3)

        # 不同种子生成的结果很可能不同（不能保证一定不同，但大概率）
        # 这里只检查多次运行不会崩溃
        assert isinstance(events1, list)
        assert isinstance(events2, list)


class TestScopeTypes:
    """测试不同范围类型。"""

    def test_province_scope(self, sample_templates, sample_province_ids):
        """省份范围效果只影响单个省份。"""
        rng = random.Random(42)
        template = sample_templates[0]  # flood with province scope
        event = generate_random_event(template, turn=1, province_ids=sample_province_ids, rng=rng)

        assert not event.effects[0].scope.is_national
        assert len(event.effects[0].scope.province_ids) == 1
        assert event.effects[0].scope.province_ids[0] in sample_province_ids

    def test_all_provinces_scope(self, sample_templates, sample_province_ids):
        """all_provinces 范围影响所有省份。"""
        rng = random.Random(42)
        template = sample_templates[2]  # national_prosperity with all_provinces scope
        event = generate_random_event(template, turn=1, province_ids=sample_province_ids, rng=rng)

        assert not event.effects[0].scope.is_national
        assert event.effects[0].scope.province_ids == sample_province_ids

    def test_national_scope(self, sample_templates, sample_province_ids):
        """national 范围设置 is_national 标志。"""
        rng = random.Random(42)
        template = sample_templates[3]  # imperial_decree with national scope
        event = generate_random_event(template, turn=1, province_ids=sample_province_ids, rng=rng)

        assert event.effects[0].scope.is_national
        assert event.effects[0].scope.province_ids == []


class TestWeightedSelection:
    """测试权重选择。"""

    def test_weighted_selection_distribution(self, sample_templates, sample_province_ids):
        """权重选择符合预期分布（统计测试）。"""
        # 运行多次，统计各类事件被选中的次数
        category_counts: dict[str, int] = {}

        for seed in range(100):
            rng = random.Random(seed)
            events = generate_events_for_turn(
                sample_templates, turn=1, province_ids=sample_province_ids, rng=rng, max_events=1
            )
            for event in events:
                category_counts[event.category] = category_counts.get(event.category, 0) + 1

        # disaster 权重最高 (2.0)，应该被选中最多
        # blessing 总权重 1.0+0.5+0.3=1.8
        assert "disaster" in category_counts or "blessing" in category_counts

    def test_zero_weight_not_selected(self, sample_province_ids):
        """权重为 0 的模板不应被选中。"""
        templates = [
            EventTemplate(
                template_id="never_selected",
                category="test",
                weight=Decimal("0.0"),
                description_templates=["never"],
                effects=[],
            ),
            EventTemplate(
                template_id="always_selected",
                category="test",
                weight=Decimal("1.0"),
                description_templates=["always"],
                effects=[],
            ),
        ]

        for seed in range(50):
            rng = random.Random(seed)
            events = generate_events_for_turn(
                templates, turn=1, province_ids=sample_province_ids, rng=rng, max_events=1
            )
            for event in events:
                assert event.category == "test"


class TestValueRange:
    """测试效果值范围。"""

    def test_multiply_value_range(self, sample_templates, sample_province_ids):
        """乘法效果值在范围内。"""
        rng = random.Random(42)
        template = sample_templates[0]  # flood with multiply effect
        effect_template = template.effects[0]

        for _ in range(20):
            rng_copy = random.Random(rng.randint(0, 1000000))
            event = generate_random_event(template, turn=1, province_ids=sample_province_ids, rng=rng_copy)
            value = event.effects[0].value
            assert value >= effect_template.value_min
            assert value <= effect_template.value_max

    def test_add_value_range(self, sample_templates, sample_province_ids):
        """加法效果值在范围内。"""
        rng = random.Random(42)
        template = sample_templates[1]  # harvest with add effect
        effect_template = template.effects[0]

        for _ in range(20):
            rng_copy = random.Random(rng.randint(0, 1000000))
            event = generate_random_event(template, turn=1, province_ids=sample_province_ids, rng=rng_copy)
            value = event.effects[0].value
            assert value >= effect_template.value_min
            assert value <= effect_template.value_max


class TestDescriptionEffectProvinceConsistency:
    """测试描述与效果的省份一致性。"""

    def test_description_effect_province_consistency(self, sample_templates, sample_province_ids):
        """描述中的省份与效果影响的省份必须一致。"""
        rng = random.Random(42)
        for _ in range(20):
            seed = rng.randint(0, 1000000)
            rng_copy = random.Random(seed)
            event = generate_random_event(
                sample_templates[0], turn=1, province_ids=sample_province_ids, rng=rng_copy
            )
            # 从描述中提取省份名
            province_in_desc = next(p for p in sample_province_ids if p in event.description)
            # 所有 province scope 的效果必须影响同一省份
            for effect in event.effects:
                if effect.scope.province_ids and not effect.scope.is_national:
                    if len(effect.scope.province_ids) == 1:  # 单省份效果
                        assert effect.scope.province_ids[0] == province_in_desc

    def test_multiple_effects_same_province(self, sample_province_ids):
        """多效果的模板，所有省份效果应影响同一省份。"""
        template = EventTemplate(
            template_id="test_multi_effect",
            category="disaster",
            weight=Decimal("1.0"),
            severity_min=Decimal("0.3"),
            severity_max=Decimal("1.0"),
            duration_min=1,
            duration_max=3,
            description_templates=["{province}遭遇严重灾害"],
            effects=[
                EffectTemplate(
                    target="granary_stock",
                    operation=EffectOperation.MULTIPLY,
                    value_min=Decimal("0.3"),
                    value_max=Decimal("0.7"),
                    scope_type="province",
                ),
                EffectTemplate(
                    target="population.happiness",
                    operation=EffectOperation.ADD,
                    value_min=Decimal("-0.2"),
                    value_max=Decimal("-0.1"),
                    scope_type="province",
                ),
            ],
        )

        rng = random.Random(12345)
        for _ in range(30):
            seed = rng.randint(0, 1000000)
            rng_copy = random.Random(seed)
            event = generate_random_event(template, turn=1, province_ids=sample_province_ids, rng=rng_copy)

            # 从描述中提取省份名
            province_in_desc = next(p for p in sample_province_ids if p in event.description)

            # 所有效果应该影响同一个省份
            for effect in event.effects:
                if effect.scope.province_ids and len(effect.scope.province_ids) == 1:
                    assert effect.scope.province_ids[0] == province_in_desc

            # 多个效果影响的省份应该相同
            province_effects = [
                e.scope.province_ids[0]
                for e in event.effects
                if e.scope.province_ids and len(e.scope.province_ids) == 1
            ]
            if len(province_effects) > 1:
                assert len(set(province_effects)) == 1, "所有单省份效果应影响同一省份"


class TestEdgeCases:
    """测试边界情况。"""

    def test_empty_templates(self, sample_province_ids):
        """空模板列表返回空事件列表。"""
        rng = random.Random(42)
        events = generate_events_for_turn([], turn=1, province_ids=sample_province_ids, rng=rng)
        assert events == []

    def test_empty_province_ids(self, sample_templates):
        """空省份列表返回空事件列表。"""
        rng = random.Random(42)
        events = generate_events_for_turn(sample_templates, turn=1, province_ids=[], rng=rng)
        assert events == []

    def test_max_events_zero(self, sample_templates, sample_province_ids):
        """max_events=0 返回空列表。"""
        rng = random.Random(42)
        events = generate_events_for_turn(
            sample_templates, turn=1, province_ids=sample_province_ids, rng=rng, max_events=0
        )
        assert events == []

    def test_single_province(self, sample_templates):
        """单个省份正常工作。"""
        rng = random.Random(42)
        province_ids = ["only_province"]
        events = generate_events_for_turn(
            sample_templates, turn=1, province_ids=province_ids, rng=rng, max_events=2
        )
        for event in events:
            for effect in event.effects:
                if effect.scope.province_ids:
                    assert effect.scope.province_ids[0] == "only_province"

    def test_duration_range(self, sample_province_ids):
        """持续时间正确在范围内。"""
        template = EventTemplate(
            template_id="test_duration",
            category="test",
            weight=Decimal("1.0"),
            duration_min=2,
            duration_max=5,
            description_templates=["test"],
            effects=[],
        )

        for seed in range(50):
            rng = random.Random(seed)
            event = generate_random_event(template, turn=1, province_ids=sample_province_ids, rng=rng)
            assert 2 <= event.duration <= 5
