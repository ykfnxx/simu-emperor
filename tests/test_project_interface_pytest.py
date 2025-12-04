"""
Project Interface Tests - pytest version
"""

import pytest
from core.project import Project


def test_project_initialization():
    """Test project initialization"""
    project = Project(
        province_id=1,
        project_type='agriculture',
        month_created=3
    )

    assert project.province_id == 1
    assert project.project_type == 'agriculture'
    assert project.cost == 50
    assert project.effect_type == 'income_bonus'
    assert project.effect_value == 0.08
    assert project.month_created == 3


def test_all_project_types():
    """Test all project types"""
    project_types = [
        ('agriculture', 50, 'income_bonus', 0.08),
        ('infrastructure', 80, 'development_bonus', 0.5),
        ('tax_relief', 30, 'loyalty_bonus', 15),
        ('security', 60, 'stability_bonus', 12)
    ]

    for proj_type, cost, effect_type, effect_value in project_types:
        project = Project(1, proj_type, 3)
        assert project.cost == cost
        assert project.effect_type == effect_type
        assert project.effect_value == effect_value


def test_to_dict_interface():
    """Test conversion to dictionary"""
    project = Project(1, 'agriculture', 3)
    dict_data = project.to_dict()

    required_fields = [
        'province_id', 'project_type', 'cost',
        'effect_type', 'effect_value', 'month_created'
    ]

    for field in required_fields:
        assert field in dict_data

    assert dict_data['province_id'] == 1
    assert dict_data['project_type'] == 'agriculture'
    assert dict_data['cost'] == 50.0


def test_project_effects():
    """Test project effect values"""
    # Agricultural reform
    agriculture = Project(1, 'agriculture', 3)
    assert agriculture.effect_value == 0.08  # 8% income increase

    # Infrastructure
    infrastructure = Project(1, 'infrastructure', 3)
    assert infrastructure.effect_value == 0.5  # Development +0.5

    # Tax relief
    tax_relief = Project(1, 'tax_relief', 3)
    assert tax_relief.effect_value == 15  # Loyalty +15

    # Security enhancement
    security = Project(1, 'security', 3)
    assert security.effect_value == 12  # Stability +12


def test_project_costs():
    """Test project costs"""
    assert Project(1, 'agriculture', 3).cost == 50
    assert Project(1, 'infrastructure', 3).cost == 80
    assert Project(1, 'tax_relief', 3).cost == 30
    assert Project(1, 'security', 3).cost == 60

    # Verify cost ordering (tax relief is cheapest, infrastructure is most expensive)
    costs = [
        Project(1, 'tax_relief', 3).cost,
        Project(1, 'agriculture', 3).cost,
        Project(1, 'security', 3).cost,
        Project(1, 'infrastructure', 3).cost
    ]
    assert costs == sorted(costs)
