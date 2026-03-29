"""Tests for IncidentGenerator."""

import pytest
import random
from decimal import Decimal

from simu_emperor.config import IncidentConfig
from simu_emperor.engine.models.base_data import NationData, ProvinceData
from simu_emperor.engine.models.incident import Incident
from simu_emperor.engine.incident_generator import (
    IncidentGenerator,
    IncidentTemplate,
    DEFAULT_TEMPLATES,
)


@pytest.fixture
def sample_nation():
    """Create a sample NationData for testing."""
    provinces = {
        "zhili": ProvinceData(
            province_id="zhili",
            name="直隶",
            production_value=Decimal("100000"),
            population=Decimal("50000"),
            fixed_expenditure=Decimal("5000"),
            stockpile=Decimal("20000"),
        ),
        "shanxi": ProvinceData(
            province_id="shanxi",
            name="山西",
            production_value=Decimal("80000"),
            population=Decimal("40000"),
            fixed_expenditure=Decimal("4000"),
            stockpile=Decimal("15000"),
        ),
    }
    return NationData(
        turn=10,
        base_tax_rate=Decimal("0.10"),
        tribute_rate=Decimal("0.8"),
        imperial_treasury=Decimal("100000"),
        provinces=provinces,
    )


@pytest.fixture
def province_names():
    return {"zhili": "直隶", "shanxi": "山西"}


@pytest.fixture
def config():
    return IncidentConfig(
        enabled=True,
        check_interval_ticks=4,
        base_trigger_probability=0.1,
        max_active_system_incidents=5,
        llm_beautify_enabled=False,
    )


@pytest.fixture
def generator(config, province_names):
    rng = random.Random(42)
    return IncidentGenerator(config=config, rng=rng, province_names=province_names)


class TestIncidentGenerator:
    """Test IncidentGenerator."""

    def test_init(self, generator):
        assert generator._counter == 0
        assert len(generator._templates) == len(DEFAULT_TEMPLATES)

    def test_generate_returns_list(self, generator, sample_nation):
        result = generator.generate(sample_nation, active_count=0)
        assert isinstance(result, list)

    def test_generate_disabled(self, province_names, sample_nation):
        config = IncidentConfig(enabled=False)
        gen = IncidentGenerator(config=config, rng=random.Random(42), province_names=province_names)
        result = gen.generate(sample_nation, active_count=0)
        assert result == []

    def test_generate_max_active_reached(self, generator, sample_nation):
        result = generator.generate(sample_nation, active_count=5)
        assert result == []

    def test_generate_no_provinces(self, generator):
        empty_nation = NationData(turn=0)
        result = generator.generate(empty_nation, active_count=0)
        assert result == []

    def test_generate_deterministic_with_seed(self, config, province_names, sample_nation):
        """Same seed produces same results."""
        gen1 = IncidentGenerator(
            config=config, rng=random.Random(42), province_names=province_names
        )
        gen2 = IncidentGenerator(
            config=config, rng=random.Random(42), province_names=province_names
        )
        result1 = gen1.generate(sample_nation, active_count=0)
        result2 = gen2.generate(sample_nation, active_count=0)
        assert len(result1) == len(result2)
        for inc1, inc2 in zip(result1, result2):
            assert inc1.title == inc2.title

    def test_generate_high_probability_triggers(self, province_names, sample_nation):
        """With probability=1.0, all templates trigger."""
        config = IncidentConfig(enabled=True, max_active_system_incidents=10)
        templates = [
            IncidentTemplate(
                template_id="test",
                title_template="{province_name}测试事件",
                description_template="测试描述",
                effects=[{"target_path": "provinces.{province}.production_value", "factor": "0.1"}],
                duration_ticks=2,
                probability=1.0,
            )
        ]
        gen = IncidentGenerator(config=config, rng=random.Random(42), province_names=province_names)
        gen._templates = templates
        result = gen.generate(sample_nation, active_count=0)
        assert len(result) == 1

    def test_generate_zero_probability_never_triggers(self, province_names, sample_nation):
        """With probability=0.0, nothing triggers."""
        config = IncidentConfig(enabled=True)
        templates = [
            IncidentTemplate(
                template_id="test",
                title_template="{province_name}测试事件",
                description_template="测试描述",
                effects=[{"target_path": "provinces.{province}.production_value", "factor": "0.1"}],
                duration_ticks=2,
                probability=0.0,
            )
        ]
        gen = IncidentGenerator(config=config, rng=random.Random(42), province_names=province_names)
        gen._templates = templates
        result = gen.generate(sample_nation, active_count=0)
        assert result == []

    def test_generated_incident_structure(self, province_names, sample_nation):
        """Verify generated incident has correct structure."""
        config = IncidentConfig(enabled=True, max_active_system_incidents=10)
        templates = [
            IncidentTemplate(
                template_id="harvest",
                title_template="{province_name}大丰收",
                description_template="{province_name}风调雨顺",
                effects=[
                    {"target_path": "provinces.{province}.production_value", "factor": "0.15"},
                    {"target_path": "provinces.{province}.stockpile", "add": "2000"},
                ],
                duration_ticks=3,
                probability=1.0,
            )
        ]
        gen = IncidentGenerator(config=config, rng=random.Random(42), province_names=province_names)
        gen._templates = templates
        result = gen.generate(sample_nation, active_count=0)

        assert len(result) == 1
        inc = result[0]
        assert isinstance(inc, Incident)
        assert inc.incident_id.startswith("inc_sys_")
        assert inc.source == "system:incident_generator"
        assert inc.remaining_ticks == 3
        assert len(inc.effects) == 2
        assert inc.applied is False
        # Province name should be substituted in title
        assert "直隶" in inc.title or "山西" in inc.title

    def test_generate_respects_max_active_mid_generation(self, province_names, sample_nation):
        """Stop generating when max_active is reached during generation."""
        config = IncidentConfig(enabled=True, max_active_system_incidents=2)
        templates = [
            IncidentTemplate(
                template_id=f"test_{i}",
                title_template=f"事件{i}",
                description_template="描述",
                effects=[{"target_path": "provinces.{province}.production_value", "factor": "0.1"}],
                duration_ticks=2,
                probability=1.0,
            )
            for i in range(5)
        ]
        gen = IncidentGenerator(config=config, rng=random.Random(42), province_names=province_names)
        gen._templates = templates
        result = gen.generate(sample_nation, active_count=0)
        assert len(result) <= 2

    def test_build_effects_replaces_province(self):
        """Test that {province} placeholder is replaced in target_path."""
        skeletons = [
            {"target_path": "provinces.{province}.production_value", "factor": "0.1"},
            {"target_path": "provinces.{province}.stockpile", "add": "1000"},
        ]
        effects = IncidentGenerator._build_effects(skeletons, "zhili")
        assert effects[0].target_path == "provinces.zhili.production_value"
        assert effects[0].factor == Decimal("0.1")
        assert effects[1].target_path == "provinces.zhili.stockpile"
        assert effects[1].add == Decimal("1000")

    def test_counter_increments(self, province_names, sample_nation):
        """Counter increments with each generated incident."""
        config = IncidentConfig(enabled=True, max_active_system_incidents=10)
        templates = [
            IncidentTemplate(
                template_id="test",
                title_template="事件",
                description_template="描述",
                effects=[{"target_path": "provinces.{province}.production_value", "factor": "0.1"}],
                duration_ticks=2,
                probability=1.0,
            )
        ]
        gen = IncidentGenerator(config=config, rng=random.Random(42), province_names=province_names)
        gen._templates = templates
        gen.generate(sample_nation, active_count=0)
        assert gen._counter == 1
        gen.generate(sample_nation, active_count=0)
        assert gen._counter == 2


class TestDefaultTemplates:
    """Test default templates are valid."""

    def test_default_templates_count(self):
        assert len(DEFAULT_TEMPLATES) == 5

    def test_default_templates_have_valid_ids(self):
        ids = [t.template_id for t in DEFAULT_TEMPLATES]
        assert len(ids) == len(set(ids))  # unique

    def test_default_templates_have_placeholders(self):
        for template in DEFAULT_TEMPLATES:
            assert "{province_name}" in template.title_template
            assert "{province_name}" in template.description_template
            for eff in template.effects:
                assert "{province}" in eff["target_path"]

    def test_default_templates_probabilities_in_range(self):
        for template in DEFAULT_TEMPLATES:
            assert 0.0 < template.probability <= 1.0

    def test_default_templates_duration_positive(self):
        for template in DEFAULT_TEMPLATES:
            assert template.duration_ticks > 0
