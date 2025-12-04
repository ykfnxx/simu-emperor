"""
Game Interface Tests - pytest version
"""

import pytest
import os
from core.game import Game
from core.project import Project


@pytest.fixture
def game():
    """Create test game instance"""
    db_path = "test_game.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    game = Game(db_path)
    yield game

    # Cleanup after test
    if os.path.exists(db_path):
        os.remove(db_path)


def test_game_initialization():
    """Test game initialization"""
    game = Game(":memory:")

    # Verify game state loaded
    assert game.state is not None
    assert 'current_month' in game.state
    assert 'treasury' in game.state
    assert 'debug_mode' in game.state

    # Verify provinces loaded (should be 1 initial province)
    assert len(game.provinces) == 1


def test_next_month_interface(game):
    """Test advancing to next month"""
    initial_month = game.state['current_month']

    game.next_month()

    # Month incremented
    assert game.state['current_month'] == initial_month + 1

    # Verify province data updated
    for province in game.provinces:
        assert province.actual_income > 0
        assert province.actual_expenditure > 0
        assert province.reported_income > 0
        assert province.reported_expenditure > 0


def test_add_project_interface(game):
    """Test adding project"""
    initial_treasury = game.state['treasury']

    project = Project(1, 'agriculture', game.state['current_month'])
    initial_project_count = len(game.db.get_active_projects())

    game.add_project(project)

    # Treasury has been charged
    assert game.state['treasury'] == initial_treasury - project.cost

    # Verify project saved to database
    active_projects = game.db.get_active_projects()
    assert len(active_projects) == initial_project_count + 1


def test_debug_mode_switch(game):
    """Test Debug mode toggle"""
    initial_mode = game.state['debug_mode']
    game.toggle_debug_mode()
    assert game.state['debug_mode'] != initial_mode
    game.toggle_debug_mode()
    assert game.state['debug_mode'] == initial_mode


def test_get_financial_summary(game):
    """Test getting financial summary"""
    # Run one month first
    game.next_month()

    summary = game.get_financial_summary()

    # Verify returned dictionary contains required fields
    required_fields = [
        'month', 'treasury', 'month_starting_treasury',
        'total_reported_income', 'total_reported_expenditure',
        'provinces'
    ]

    for field in required_fields:
        assert field in summary

    assert summary['month'] == game.state['current_month']
    assert summary['treasury'] > 0
    assert len(summary['provinces']) == 1


def test_multiple_months(game):
    """Test multiple month cycles"""
    initial_month = game.state['current_month']

    # Run 5 months
    for i in range(5):
        game.next_month()
        assert game.state['current_month'] == initial_month + i + 1

    # Verify data integrity
    assert len(game.provinces) == 1
    for province in game.provinces:
        assert province.actual_income > 0
        assert province.actual_expenditure > 0


def test_project_effect_integration(game):
    """Test project effect integration"""
    # Select first province
    province = game.provinces[0]
    initial_income = province.base_income

    # Create agriculture project
    project = Project(province.province_id, 'agriculture', game.state['current_month'])
    game.add_project(project)

    # Run one month (project effects take effect next month)
    game.next_month()

    # Verify project activated
    active_projects = game.db.get_active_projects()
    assert len(active_projects) == 1

    # Run another month (project effects take effect)
    game.next_month()

    # Verify project completed
    active_projects_after = game.db.get_active_projects()
    assert len(active_projects_after) == 0

    # Verify effects applied (base_income should increase by ~8%)
    # Note: Due to random fluctuations, this is just a rough verification
    assert province.base_income > initial_income


def test_treasury_update_accuracy(game):
    """Test treasury update accuracy"""
    initial_treasury = game.state['treasury']

    game.next_month()

    # Calculate expected treasury change
    total_actual_income = sum(p.actual_income for p in game.provinces)
    total_actual_expenditure = sum(p.actual_expenditure for p in game.provinces)
    expected_treasury = initial_treasury + (total_actual_income - total_actual_expenditure)

    # Verify treasury updated (considering floating point precision)
    assert abs(game.state['treasury'] - expected_treasury) < 0.01
