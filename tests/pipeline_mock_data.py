"""
Mock Data Generator for Three-Agent Pipeline Testing

Provides realistic test data for Perception, Decision, and Execution agents.
Supports multiple scenarios: normal, crisis, prosperity, growth, decline.
"""

from typing import Dict, Any, List
from agents.province.models import (
    PerceptionContext, MonthlyDetailedData, QuarterlySummary, AnnualSummary,
    EventIndex, TrendAnalysis, TrendDirection, RiskLevel, EventSummary
)
from pydantic import BaseModel


class MockDataGenerator:
    """Generate realistic mock data for testing the three-agent pipeline"""

    @staticmethod
    def create_perception_context(scenario: str = "normal", province_id: int = 1, month: int = 1, year: int = 1) -> PerceptionContext:
        """
        Create a complete PerceptionContext for testing

        Args:
            scenario: Scenario type (normal, crisis, prosperity, growth, decline)
            province_id: Province identifier
            month: Current month
            year: Current year

        Returns:
            Complete PerceptionContext with realistic data
        """
        scenario_data = MockDataGenerator._get_scenario_data(scenario)

        return PerceptionContext(
            province_id=province_id,
            province_name=f"Province {province_id}",
            current_month=month,
            current_year=year,
            recent_data=MockDataGenerator._create_monthly_data(scenario, month, year),
            quarterly_summaries=MockDataGenerator._create_quarterly_summaries(scenario, year),
            annual_summaries=MockDataGenerator._create_annual_summaries(scenario, year),
            critical_events=MockDataGenerator._create_critical_events(scenario),
            trends=MockDataGenerator._create_trend_analysis(scenario),
            data_quality="complete",
            warnings=[]
        )

    @staticmethod
    def create_province_state(scenario: str = "normal") -> Dict[str, Any]:
        """
        Create province state dictionary for decision making

        Args:
            scenario: Scenario type (normal, crisis, prosperity, growth, decline)

        Returns:
            Province state dictionary
        """
        scenario_data = MockDataGenerator._get_scenario_data(scenario)

        return {
            'actual_income': scenario_data['income'],
            'actual_expenditure': scenario_data['expenditure'],
            'reported_income': scenario_data['income'] * scenario_data.get('reporting_ratio', 1.0),
            'reported_expenditure': scenario_data['expenditure'] * scenario_data.get('reporting_ratio', 1.0),
            'actual_surplus': scenario_data['income'] - scenario_data['expenditure'],
            'loyalty': scenario_data['loyalty'],
            'stability': scenario_data['stability'],
            'development_level': scenario_data['development'],
            'population': scenario_data['population']
        }

    @staticmethod
    def _get_scenario_data(scenario: str) -> Dict[str, Any]:
        """Get scenario-specific base data"""
        scenarios = {
            'normal': {
                'income': 950,
                'expenditure': 900,
                'loyalty': 65,
                'stability': 70,
                'development': 5.5,
                'population': 50000,
                'income_trend': TrendDirection.STABLE,
                'loyalty_trend': TrendDirection.STABLE,
                'risk_level': RiskLevel.LOW
            },
            'crisis': {
                'income': 600,
                'expenditure': 800,
                'loyalty': 30,
                'stability': 25,
                'development': 3.5,
                'population': 45000,
                'income_trend': TrendDirection.DECREASING,
                'loyalty_trend': TrendDirection.DECREASING,
                'risk_level': RiskLevel.HIGH,
                'reporting_ratio': 0.85
            },
            'prosperity': {
                'income': 1300,
                'expenditure': 1000,
                'loyalty': 85,
                'stability': 80,
                'development': 7.5,
                'population': 65000,
                'income_trend': TrendDirection.INCREASING,
                'loyalty_trend': TrendDirection.INCREASING,
                'risk_level': RiskLevel.LOW
            },
            'growth': {
                'income': 900,
                'expenditure': 880,
                'loyalty': 70,
                'stability': 72,
                'development': 6.0,
                'population': 52000,
                'income_trend': TrendDirection.INCREASING,
                'loyalty_trend': TrendDirection.INCREASING,
                'risk_level': RiskLevel.LOW
            },
            'decline': {
                'income': 800,
                'expenditure': 950,
                'loyalty': 55,
                'stability': 50,
                'development': 5.0,
                'population': 48000,
                'income_trend': TrendDirection.DECREASING,
                'loyalty_trend': TrendDirection.DECREASING,
                'risk_level': RiskLevel.MEDIUM
            }
        }

        return scenarios.get(scenario, scenarios['normal'])

    @staticmethod
    def _create_monthly_data(scenario: str, month: int, year: int) -> MonthlyDetailedData:
        """Create monthly detailed data"""
        data = MockDataGenerator._get_scenario_data(scenario)

        # Add events for crisis scenario
        events = []
        if scenario == 'crisis':
            events.append(EventSummary(
                event_id="crisis_rebellion_001",
                event_type="rebellion",
                name="Peasant Uprising",
                severity=0.8,
                month=month,
                year=year,
                description="Armed rebellion erupted in the eastern region"
            ))

        return MonthlyDetailedData(
            month=month,
            year=year,
            population=data['population'],
            development_level=data['development'],
            loyalty=data['loyalty'],
            stability=data['stability'],
            actual_income=data['income'],
            actual_expenditure=data['expenditure'],
            reported_income=data['income'] * data.get('reporting_ratio', 1.0),
            reported_expenditure=data['expenditure'] * data.get('reporting_ratio', 1.0),
            actual_surplus=data['income'] - data['expenditure'],
            reported_surplus=(data['income'] * data.get('reporting_ratio', 1.0) -
                           data['expenditure'] * data.get('reporting_ratio', 1.0)),
            events=events
        )

    @staticmethod
    def _create_quarterly_summaries(scenario: str, year: int) -> List[QuarterlySummary]:
        """Create quarterly summaries"""
        data = MockDataGenerator._get_scenario_data(scenario)

        summaries = []
        for quarter in range(1, 5):
            # Vary data slightly by quarter
            quarter_multiplier = 1.0 + (quarter - 2.5) * 0.05

            summaries.append(QuarterlySummary(
                quarter=quarter,
                year=year,
                avg_income=data['income'] * quarter_multiplier,
                median_income=data['income'] * quarter_multiplier * 0.95,
                avg_expenditure=data['expenditure'] * quarter_multiplier,
                median_expenditure=data['expenditure'] * quarter_multiplier * 0.98,
                total_surplus=(data['income'] - data['expenditure']) * 3 * quarter_multiplier,
                income_trend=data['income_trend'],
                expenditure_trend=TrendDirection.STABLE,
                loyalty_change=0.0,
                stability_change=0.0,
                major_events=[],
                special_event_types=[],
                summary=f"Q{quarter} {scenario.capitalize()} performance recorded."
            ))

        return summaries

    @staticmethod
    def _create_annual_summaries(scenario: str, year: int) -> List[AnnualSummary]:
        """Create annual summaries"""
        data = MockDataGenerator._get_scenario_data(scenario)

        summaries = []
        for i, prev_year in enumerate([year - 1, year - 2, year - 3]):
            if prev_year <= 0:
                continue

            # Slight variation between years
            year_multiplier = 1.0 - i * 0.05

            summaries.append(AnnualSummary(
                year=prev_year,
                total_income=data['income'] * 12 * year_multiplier,
                total_expenditure=data['expenditure'] * 12 * year_multiplier,
                avg_monthly_income=data['income'] * year_multiplier,
                avg_monthly_expenditure=data['expenditure'] * year_multiplier,
                total_surplus=(data['income'] - data['expenditure']) * 12 * year_multiplier,
                population_change=0,
                development_change=0.0,
                loyalty_start=data['loyalty'],
                loyalty_end=data['loyalty'],
                loyalty_change=0.0,
                major_events=[],
                disaster_count=1 if scenario == 'crisis' else 0,
                rebellion_count=1 if scenario == 'crisis' else 0,
                performance_rating='good' if scenario == 'prosperity' else 'average',
                summary=f"Year {prev_year} ended with {scenario} conditions."
            ))

        return summaries

    @staticmethod
    def _create_critical_events(scenario: str) -> List[EventIndex]:
        """Create critical events index"""
        events = []

        if scenario == 'crisis':
            events.append(EventIndex(
                index_id=1,
                event_id="crisis_rebellion_001",
                event_category="rebellion",
                event_name="Peasant Uprising",
                severity=0.8,
                month=1,
                year=1,
                impact_description="Large-scale armed rebellion threatens provincial stability",
                is_resolved=False
            ))
            events.append(EventIndex(
                index_id=2,
                event_id="crisis_flood_001",
                event_category="disaster",
                event_name="Great Flood",
                severity=0.7,
                month=2,
                year=1,
                impact_description="Severe flooding destroyed crops and infrastructure",
                is_resolved=False
            ))

        elif scenario == 'normal':
            events.append(EventIndex(
                index_id=1,
                event_id="normal_bandits_001",
                event_category="crisis",
                event_name="Bandit Activity",
                severity=0.4,
                month=3,
                year=1,
                impact_description="Minor bandit groups disrupting trade routes",
                is_resolved=True
            ))

        return events

    @staticmethod
    def _create_trend_analysis(scenario: str) -> TrendAnalysis:
        """Create trend analysis"""
        data = MockDataGenerator._get_scenario_data(scenario)

        risk_factors = []
        opportunities = []

        # Scenario-specific risk factors and opportunities
        if scenario == 'crisis':
            risk_factors = [
                "Very low loyalty - risk of uprising",
                "Very low stability - chaos potential",
                "Negative budget - financial crisis",
                "Declining income trend",
                "Declining loyalty"
            ]
            opportunities = []
        elif scenario == 'prosperity':
            risk_factors = []
            opportunities = [
                "Strong income growth supports expansion",
                "Loyalty improvement enables reforms",
                "Large surplus for investment"
            ]
        elif scenario == 'normal':
            risk_factors = []
            opportunities = [
                "Stable conditions for gradual improvement"
            ]
        elif scenario == 'decline':
            risk_factors = [
                "Declining income trend",
                "Declining loyalty",
                "Negative budget - financial strain"
            ]
            opportunities = []

        return TrendAnalysis(
            income_trend=data['income_trend'],
            income_change_rate=-15.0 if scenario == 'crisis' else (12.0 if scenario == 'prosperity' else 0.0),
            expenditure_trend=TrendDirection.STABLE,
            expenditure_change_rate=0.0,
            loyalty_trend=data['loyalty_trend'],
            loyalty_change_rate=-5.0 if scenario == 'crisis' else (8.0 if scenario == 'prosperity' else 0.0),
            stability_trend=data['loyalty_trend'],
            stability_change_rate=-8.0 if scenario == 'crisis' else (5.0 if scenario == 'prosperity' else 0.0),
            risk_level=data['risk_level'],
            risk_factors=risk_factors,
            opportunities=opportunities
        )


def get_scenario_description(scenario: str) -> str:
    """Get human-readable scenario description"""
    descriptions = {
        'normal': "Normal operating conditions - stable metrics, low risk",
        'crisis': "Crisis scenario - low loyalty/stability, rebellion, financial deficit",
        'prosperity': "Prosperity scenario - high metrics, surplus, growth opportunities",
        'growth': "Growth scenario - improving trends, positive momentum",
        'decline': "Decline scenario - deteriorating conditions, warning signs"
    }
    return descriptions.get(scenario, "Unknown scenario")


def list_scenarios() -> List[str]:
    """List available test scenarios"""
    return ['normal', 'crisis', 'prosperity', 'growth', 'decline']
