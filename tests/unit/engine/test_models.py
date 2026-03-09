"""Tests for ProvinceData and NationData models (V4)."""

from decimal import Decimal

from simu_emperor.engine.models.base_data import ProvinceData, NationData


class TestProvinceData:
    """Test ProvinceData dataclass."""

    def test_province_creation(self):
        """Test ProvinceData creation with all fields."""
        province = ProvinceData(
            province_id="zhili",
            name="直隶",
            production_value=Decimal("100000"),
            population=Decimal("50000"),
            fixed_expenditure=Decimal("5000"),
            stockpile=Decimal("20000"),
        )
        assert province.province_id == "zhili"
        assert province.name == "直隶"
        assert province.production_value == Decimal("100000")
        assert province.population == Decimal("50000")
        assert province.fixed_expenditure == Decimal("5000")
        assert province.stockpile == Decimal("20000")

    def test_province_default_growth_rates(self):
        """Test ProvinceData default growth rates."""
        province = ProvinceData(
            province_id="zhili",
            name="直隶",
            production_value=Decimal("100000"),
            population=Decimal("50000"),
            fixed_expenditure=Decimal("5000"),
            stockpile=Decimal("20000"),
        )
        assert province.base_production_growth == Decimal("0.01")
        assert province.base_population_growth == Decimal("0.005")

    def test_province_custom_growth_rates(self):
        """Test ProvinceData with custom growth rates."""
        province = ProvinceData(
            province_id="zhili",
            name="直隶",
            production_value=Decimal("100000"),
            population=Decimal("50000"),
            fixed_expenditure=Decimal("5000"),
            stockpile=Decimal("20000"),
            base_production_growth=Decimal("0.02"),
            base_population_growth=Decimal("0.01"),
        )
        assert province.base_production_growth == Decimal("0.02")
        assert province.base_population_growth == Decimal("0.01")

    def test_province_default_tax_modifier(self):
        """Test ProvinceData default tax modifier is zero."""
        province = ProvinceData(
            province_id="zhili",
            name="直隶",
            production_value=Decimal("100000"),
            population=Decimal("50000"),
            fixed_expenditure=Decimal("5000"),
            stockpile=Decimal("20000"),
        )
        assert province.tax_modifier == Decimal("0.0")

    def test_province_custom_tax_modifier(self):
        """Test ProvinceData with custom tax modifier."""
        province = ProvinceData(
            province_id="zhili",
            name="直隶",
            production_value=Decimal("100000"),
            population=Decimal("50000"),
            fixed_expenditure=Decimal("5000"),
            stockpile=Decimal("20000"),
            tax_modifier=Decimal("0.05"),
        )
        assert province.tax_modifier == Decimal("0.05")


class TestNationData:
    """Test NationData dataclass."""

    def test_nation_creation(self):
        """Test NationData creation."""
        nation = NationData(turn=0)
        assert nation.turn == 0
        assert nation.base_tax_rate == Decimal("0.10")
        assert nation.tribute_rate == Decimal("0.8")
        assert nation.fixed_expenditure == Decimal("0")
        assert nation.imperial_treasury == Decimal("0")
        assert nation.provinces == {}

    def test_nation_with_provinces(self):
        """Test NationData with provinces."""
        province1 = ProvinceData(
            province_id="zhili",
            name="直隶",
            production_value=Decimal("100000"),
            population=Decimal("50000"),
            fixed_expenditure=Decimal("5000"),
            stockpile=Decimal("20000"),
        )
        province2 = ProvinceData(
            province_id="shanxi",
            name="山西",
            production_value=Decimal("80000"),
            population=Decimal("40000"),
            fixed_expenditure=Decimal("4000"),
            stockpile=Decimal("15000"),
        )
        nation = NationData(turn=0, provinces={"zhili": province1, "shanxi": province2})
        assert len(nation.provinces) == 2
        assert "zhili" in nation.provinces
        assert "shanxi" in nation.provinces
        assert nation.provinces["zhili"].name == "直隶"

    def test_nation_custom_tax_rate(self):
        """Test NationData with custom tax rate."""
        nation = NationData(turn=0, base_tax_rate=Decimal("0.15"))
        assert nation.base_tax_rate == Decimal("0.15")

    def test_nation_custom_tribute_rate(self):
        """Test NationData with custom tribute rate."""
        nation = NationData(turn=0, tribute_rate=Decimal("0.7"))
        assert nation.tribute_rate == Decimal("0.7")

    def test_nation_custom_imperial_treasury(self):
        """Test NationData with custom imperial treasury."""
        nation = NationData(turn=0, imperial_treasury=Decimal("1000000"))
        assert nation.imperial_treasury == Decimal("1000000")
