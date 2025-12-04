"""
Province module - Pure data class, no business logic
"""

from typing import Dict, Any


class Province:
    """Province data class

    Responsibilities:
    - Store all attributes of a province (pure data, no logic)
    - Provide to_dict() for serialization
    - Provide update_values() for batch value updates
    - Three-layer data model: Actual values → Adjusted values → Reported values
    """

    def __init__(self, data: Dict[str, Any]):
        """Initialize province (pure data, no logic)

        Args:
            data: Dictionary containing province attributes
        """
        # Basic attributes
        self.province_id = data['province_id']
        self.name = data['name']
        self.population = data['population']
        self.development_level = data['development_level']
        self.loyalty = data.get('loyalty', 70)
        self.stability = data.get('stability', 70)
        self.base_income = data.get('base_income', 0.0)

        # ===== Three-layer data model =====

        # Layer 1: Actual values (calculated from events and base calculations)
        self.actual_income = data.get('actual_income', 0.0)
        self.actual_expenditure = data.get('actual_expenditure', 0.0)

        # Layer 2: Adjusted values (values after Agent adjustments, including concealment/exaggeration)
        self.adjusted_income = data.get('adjusted_income', 0.0)
        self.adjusted_expenditure = data.get('adjusted_expenditure', 0.0)

        # Layer 3: Reported values (final values reported to central government, may be further adjusted)
        self.reported_income = data.get('reported_income', 0.0)
        self.reported_expenditure = data.get('reported_expenditure', 0.0)

        # Reporting related information
        self.reporting_bias_ratio = data.get('reporting_bias_ratio', 0.0)  # -0.5 (concealment) ~ +0.5 (exaggeration)
        self.reporting_narrative = data.get('reporting_narrative', "")      # Adjustment explanation
        self.is_fabricated = data.get('is_fabricated', False)              # Whether fabricated

        # Event hiding
        self.hidden_events = data.get('hidden_events', [])                 # List of hidden event IDs
        self.concealment_reasoning = data.get('concealment_reasoning', "") # Concealment reason

        # Surplus (accumulated) - Calculate reported surplus and actual surplus separately
        self.reported_surplus = data.get('reported_surplus', 0.0)          # Reported surplus (accumulated)
        self.actual_surplus = data.get('actual_surplus', 0.0)              # Actual surplus (accumulated)

        # Agent related attributes (for restoring Agent state)
        self.corruption_tendency = data.get('corruption_tendency', 0.3)
        self.last_month_corrupted = data.get('last_month_corrupted', False)

    def update_values(self, actual_income: float, actual_expenditure: float,
                     reported_income: float, reported_expenditure: float) -> None:
        """Update income/expenditure values and surplus (pure data update, no logic)

        Args:
            actual_income: Actual income
            actual_expenditure: Actual expenditure
            reported_income: Reported income
            reported_expenditure: Reported expenditure
        """
        # Update income and expenditure
        self.actual_income = actual_income
        self.actual_expenditure = actual_expenditure
        self.reported_income = reported_income
        self.reported_expenditure = reported_expenditure

        # Calculate monthly surplus (difference between income and expenditure)
        actual_monthly_surplus = actual_income - actual_expenditure
        reported_monthly_surplus = reported_income - reported_expenditure

        # Accumulate surplus (add to previous surplus)
        self.actual_surplus += actual_monthly_surplus
        self.reported_surplus += reported_monthly_surplus

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (for saving to database)

        Returns:
            Dictionary containing all province attributes
        """
        return {
            'province_id': self.province_id,
            'name': self.name,
            'population': self.population,
            'development_level': self.development_level,
            'loyalty': self.loyalty,
            'stability': self.stability,
            'base_income': self.base_income,

            # Three-layer data model
            'actual_income': self.actual_income,
            'actual_expenditure': self.actual_expenditure,
            'adjusted_income': self.adjusted_income,
            'adjusted_expenditure': self.adjusted_expenditure,
            'reported_income': self.reported_income,
            'reported_expenditure': self.reported_expenditure,

            # Reporting information
            'reporting_bias_ratio': self.reporting_bias_ratio,
            'reporting_narrative': self.reporting_narrative,
            'is_fabricated': self.is_fabricated,

            # Event hiding
            'hidden_events': self.hidden_events,
            'concealment_reasoning': self.concealment_reasoning,

            # Surplus (accumulated)
            'reported_surplus': self.reported_surplus,
            'actual_surplus': self.actual_surplus,

            # Agent related
            'corruption_tendency': self.corruption_tendency,
            'last_month_corrupted': self.last_month_corrupted
        }

    def __repr__(self) -> str:
        """String representation"""
        return f"<Province {self.province_id}: {self.name}>"
