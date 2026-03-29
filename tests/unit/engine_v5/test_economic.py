"""Tests for V5 Engine economic calculations."""

import pytest
from decimal import Decimal

from simu_emperor.engine_v5.models.base_data import ProvinceData, NationData
from simu_emperor.engine_v5.models.incident import Incident, Effect
from simu_emperor.engine_v5 import economic


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
        turn=0,
        base_tax_rate=Decimal("0.10"),
        tribute_rate=Decimal("0.8"),
        imperial_treasury=Decimal("100000"),
        provinces=provinces,
    )


class TestApplyBaseGrowth:
    """Test apply_base_growth function."""

    def test_base_growth_applied(self, sample_nation):
        """Test base growth rates are applied."""
        initial_production = sample_nation.provinces["zhili"].production_value
        initial_population = sample_nation.provinces["zhili"].population

        economic.apply_base_growth(sample_nation)

        expected_production = initial_production * Decimal("1.01")
        expected_population = initial_population * Decimal("1.005")

        assert sample_nation.provinces["zhili"].production_value == expected_production
        assert sample_nation.provinces["zhili"].population == expected_population

    def test_base_growth_all_provinces(self, sample_nation):
        """Test base growth applied to all provinces."""
        initial_zhili = sample_nation.provinces["zhili"].production_value
        initial_shanxi = sample_nation.provinces["shanxi"].production_value

        economic.apply_base_growth(sample_nation)

        assert sample_nation.provinces["zhili"].production_value == initial_zhili * Decimal("1.01")
        assert sample_nation.provinces["shanxi"].production_value == initial_shanxi * Decimal(
            "1.01"
        )


class TestCalculateTaxAndTreasury:
    """Test calculate_tax_and_treasury function."""

    def test_tax_calculation(self, sample_nation):
        """Test tax calculation and treasury update."""
        economic.apply_base_growth(sample_nation)
        economic.calculate_tax_and_treasury(sample_nation)

        # zhili: production = 100000 * 1.01 = 101000
        # tax = 101000 * 0.10 = 10100
        # surplus = 10100 - 5000 = 5100
        # remittance = 5100 * 0.8 = 4080
        # stockpile = 20000 + 5100 - 4080 = 21020
        assert sample_nation.provinces["zhili"].stockpile == Decimal("21020")

        # total remittance = 4080 + 3264 = 7344
        # treasury = 100000 + 7344 - 0 = 107344
        assert sample_nation.imperial_treasury == Decimal("107344")

    def test_tax_with_tax_modifier(self, sample_nation):
        """Test tax calculation with province tax modifier."""
        sample_nation.provinces["zhili"].tax_modifier = Decimal("0.05")

        economic.apply_base_growth(sample_nation)
        economic.calculate_tax_and_treasury(sample_nation)

        # zhili: production = 100000 * 1.01 = 101000
        # tax = 101000 * (0.10 + 0.05) = 15150
        # surplus = 15150 - 5000 = 10150
        # remittance = 10150 * 0.8 = 8120
        # stockpile = 20000 + 10150 - 8120 = 22030
        assert sample_nation.provinces["zhili"].stockpile == Decimal("22030")


class TestApplyEffects:
    """Test apply_effects function."""

    def test_effect_factor(self, sample_nation):
        """Test factor effect increases value by percentage."""
        incident = Incident(
            incident_id="inc_001",
            title="丰收",
            description="今年大丰收",
            effects=[Effect(target_path="provinces.zhili.production_value", factor=Decimal("0.1"))],
            source="system",
            remaining_ticks=2,
        )

        economic.apply_base_growth(sample_nation)
        economic.apply_effects(sample_nation, [incident])

        initial = Decimal("100000")
        expected = initial * Decimal("1.01") * Decimal("1.10")
        assert sample_nation.provinces["zhili"].production_value == expected

    def test_effect_add(self, sample_nation):
        """Test add effect adds value once."""
        incident = Incident(
            incident_id="inc_002",
            title="拨款",
            description="国库拨款",
            effects=[Effect(target_path="provinces.zhili.stockpile", add=Decimal("5000"))],
            source="player",
            remaining_ticks=2,
        )

        economic.apply_effects(sample_nation, [incident])

        # stockpile: 20000 + 5000 (add)
        assert sample_nation.provinces["zhili"].stockpile == Decimal("25000")
        assert incident.applied is True

    def test_effect_add_only_applied_once(self, sample_nation):
        """Test add effect is only applied once."""
        incident = Incident(
            incident_id="inc_003",
            title="拨款",
            description="国库拨款",
            effects=[Effect(target_path="provinces.zhili.stockpile", add=Decimal("5000"))],
            source="player",
            remaining_ticks=3,
        )

        economic.apply_effects(sample_nation, [incident])
        first_stockpile = sample_nation.provinces["zhili"].stockpile

        economic.apply_effects(sample_nation, [incident])
        second_stockpile = sample_nation.provinces["zhili"].stockpile

        assert first_stockpile == second_stockpile

    def test_effect_negative_factor(self, sample_nation):
        """Test negative factor reduces value."""
        incident = Incident(
            incident_id="inc_004",
            title="旱灾",
            description="严重旱灾",
            effects=[
                Effect(target_path="provinces.zhili.production_value", factor=Decimal("-0.2"))
            ],
            source="system",
            remaining_ticks=1,
        )

        economic.apply_base_growth(sample_nation)
        economic.apply_effects(sample_nation, [incident])

        initial = Decimal("100000")
        expected = initial * Decimal("1.01") * Decimal("0.80")
        assert sample_nation.provinces["zhili"].production_value == expected


class TestRefreshIncidents:
    """Test refresh_incidents function."""

    def test_incident_expires_after_remaining_ticks(self):
        """Test incident expires after remaining_ticks reaches 0."""
        incident = Incident(
            incident_id="inc_001",
            title="测试",
            description="测试事件",
            effects=[Effect(target_path="provinces.zhili.production_value", factor=Decimal("0.0"))],
            source="test",
            remaining_ticks=2,
        )
        incidents = [incident]

        economic.refresh_incidents(incidents)
        assert incident.remaining_ticks == 1
        assert incident in incidents

        expired = economic.refresh_incidents(incidents)
        assert incident.remaining_ticks == 0
        assert incident in expired


class TestProcessTick:
    """Test process_tick function."""

    def test_process_tick_increments_turn(self, sample_nation):
        """Test process_tick increments turn counter."""
        initial_turn = sample_nation.turn
        economic.process_tick(sample_nation, [])
        assert sample_nation.turn == initial_turn + 1

    def test_process_tick_full_flow(self, sample_nation):
        """Test full tick processing flow."""
        incident = Incident(
            incident_id="inc_001",
            title="拨款",
            description="国库拨款",
            effects=[Effect(target_path="provinces.zhili.stockpile", add=Decimal("5000"))],
            source="player",
            remaining_ticks=2,
        )

        expired = economic.process_tick(sample_nation, [incident])

        assert sample_nation.turn == 1
        assert incident.applied is True
        assert incident.remaining_ticks == 1
        assert len(expired) == 0


class TestPathResolution:
    """Test path resolution functions."""

    def test_resolve_path_province(self, sample_nation):
        """Test resolving province path."""
        value = economic.resolve_path(sample_nation, "provinces.zhili.production_value")
        assert value == Decimal("100000")

    def test_resolve_path_nation(self, sample_nation):
        """Test resolving nation path."""
        value = economic.resolve_path(sample_nation, "nation.imperial_treasury")
        assert value == Decimal("100000")

    def test_resolve_path_invalid(self, sample_nation):
        """Test resolving invalid path returns None."""
        value = economic.resolve_path(sample_nation, "provinces.invalid.field")
        assert value is None

    def test_set_path_value_province(self, sample_nation):
        """Test setting province path value."""
        economic.set_path_value(sample_nation, "provinces.zhili.production_value", Decimal("99999"))
        assert sample_nation.provinces["zhili"].production_value == Decimal("99999")

    def test_set_path_value_nation(self, sample_nation):
        """Test setting nation path value."""
        economic.set_path_value(sample_nation, "nation.imperial_treasury", Decimal("50000"))
        assert sample_nation.imperial_treasury == Decimal("50000")
