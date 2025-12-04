"""
Agent Interface Tests - pytest version
"""

import pytest
from core.agent import Agent


def test_agent_initialization():
    """Test Agent initialization"""
    agent = Agent(corruption_tendency=0.4, loyalty=70)
    assert agent.corruption_tendency == 0.4
    assert agent.loyalty == 70


def test_corruption_chance_calculation():
    """Test corruption probability calculation"""
    # High loyalty (low probability)
    agent_high = Agent(0.4, 90)
    chance_high = agent_high.calculate_corruption_chance()
    assert 0 <= chance_high <= 1
    assert chance_high < 0.5

    # Low loyalty (high probability)
    agent_low = Agent(0.4, 50)
    chance_low = agent_low.calculate_corruption_chance()
    assert 0 <= chance_low <= 1
    assert chance_low > 0.4

    # Loyalty 0 (maximum probability 70%)
    agent_zero = Agent(0.4, 0)
    chance_zero = agent_zero.calculate_corruption_chance()
    assert chance_zero == 0.7


def test_corruption_decision_interface():
    """Test corruption decision"""
    agent = Agent(0.4, 70)
    assert agent.last_month_corrupted is False

    agent.decide_corruption()
    assert agent.last_month_corrupted in [True, False]

    if agent.last_month_corrupted:
        assert 0.1 <= agent.corruption_ratio <= 0.3
        assert 0.05 <= agent.expenditure_inflation <= 0.2


def test_report_generation_interface():
    """Test report generation"""
    agent = Agent(0.4, 70)
    agent.decide_corruption()
    report = agent.generate_report(1000.0, 200.0)

    assert 'income' in report
    assert 'expenditure' in report
    assert report['income'] > 0
    assert report['expenditure'] > 0


def test_report_generation_accuracy():
    """Test report calculation accuracy"""
    agent = Agent(0.4, 70)
    agent.corruption_ratio = 0.2
    agent.expenditure_inflation = 0.1
    agent.last_month_corrupted = True

    report = agent.generate_report(1000.0, 200.0)
    assert abs(report['income'] - 800.0) < 0.01
    assert abs(report['expenditure'] - 220.0) < 0.01


def test_corruption_ratio_range():
    """Test multiple decisions to verify corruption ratio range"""
    agent = Agent(0.4, 50)  # High corruption probability

    corruption_count = 0
    total_trials = 1000

    for _ in range(total_trials):
        agent.decide_corruption()
        if agent.last_month_corrupted:
            corruption_count += 1
            # Verify ratios are in reasonable range
            assert 0.1 <= agent.corruption_ratio <= 0.3
            assert 0.05 <= agent.expenditure_inflation <= 0.2

    # Verify corruption probability roughly matches expectation (allowing some error)
    assert 0.5 <= corruption_count / total_trials <= 0.7
