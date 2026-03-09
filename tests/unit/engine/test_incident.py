"""Tests for Incident and Effect models (V4)."""

import pytest

from decimal import Decimal

from simu_emperor.engine.models.incident import Effect, Incident


class TestEffect:
    """Test Effect dataclass."""

    def test_effect_with_add(self):
        """Test Effect with add value."""
        effect = Effect(target_path="provinces.zhili.stockpile", add=Decimal("1000"))
        assert effect.target_path == "provinces.zhili.stockpile"
        assert effect.add == Decimal("1000")
        assert effect.factor is None

    def test_effect_with_factor(self):
        """Test Effect with factor value."""
        effect = Effect(target_path="provinces.zhili.production_value", factor=Decimal("0.1"))
        assert effect.target_path == "provinces.zhili.production_value"
        assert effect.factor == Decimal("0.1")
        assert effect.add is None

    def test_effect_both_add_and_factor_raises(self):
        """Test Effect with both add and factor raises ValueError."""
        with pytest.raises(ValueError, match="must have exactly one"):
            Effect(
                target_path="provinces.zhili.stockpile",
                add=Decimal("1000"),
                factor=Decimal("0.1")
            )

    def test_effect_neither_add_nor_factor_raises(self):
        """Test Effect with neither add nor factor raises ValueError."""
        with pytest.raises(ValueError, match="must have exactly one"):
            Effect(target_path="provinces.zhili.stockpile")

    def test_effect_negative_add(self):
        """Test Effect with negative add value."""
        effect = Effect(target_path="provinces.zhili.stockpile", add=Decimal("-500"))
        assert effect.add == Decimal("-500")

    def test_effect_negative_factor(self):
        """Test Effect with negative factor value."""
        effect = Effect(target_path="provinces.zhili.production_value", factor=Decimal("-0.1"))
        assert effect.factor == Decimal("-0.1")


class TestIncident:
    """Test Incident dataclass."""

    def test_incident_creation(self):
        """Test Incident creation."""
        effect = Effect(target_path="provinces.zhili.production_value", factor=Decimal("0.1"))
        incident = Incident(
            incident_id="inc_001",
            title="水利建设",
            description="建设大型水利设施",
            effects=[effect],
            source="agent:revenue_minister",
            remaining_ticks=4
        )
        assert incident.incident_id == "inc_001"
        assert incident.title == "水利建设"
        assert incident.description == "建设大型水利设施"
        assert len(incident.effects) == 1
        assert incident.source == "agent:revenue_minister"
        assert incident.remaining_ticks == 4
        assert incident.applied is False

    def test_incident_with_multiple_effects(self):
        """Test Incident with multiple effects."""
        effects = [
            Effect(target_path="provinces.zhili.production_value", factor=Decimal("0.1")),
            Effect(target_path="provinces.zhili.stockpile", add=Decimal("1000")),
        ]
        incident = Incident(
            incident_id="inc_002",
            title="丰收",
            description="今年是大丰收",
            effects=effects,
            source="system",
            remaining_ticks=1
        )
        assert len(incident.effects) == 2

    def test_incident_default_applied_is_false(self):
        """Test Incident default applied is False."""
        effect = Effect(target_path="provinces.zhili.stockpile", add=Decimal("1000"))
        incident = Incident(
            incident_id="inc_003",
            title="拨款",
            description="国库拨款",
            effects=[effect],
            source="player",
            remaining_ticks=1
        )
        assert incident.applied is False

    def test_incident_can_be_created_with_applied_true(self):
        """Test Incident can be created with applied=True."""
        effect = Effect(target_path="provinces.zhili.stockpile", add=Decimal("1000"))
        incident = Incident(
            incident_id="inc_004",
            title="拨款",
            description="国库拨款",
            effects=[effect],
            source="player",
            remaining_ticks=1,
            applied=True
        )
        assert incident.applied is True
