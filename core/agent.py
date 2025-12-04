"""
AI Agent module - Local officials
Responsible for managing provinces and potentially concealing data
"""

import random


class Agent:
    """Local official AI"""

    def __init__(self, corruption_tendency: float, loyalty: float):
        """Initialize Agent

        Args:
            corruption_tendency: Corruption tendency (0-1)
            loyalty: Loyalty (0-100)
        """
        self.corruption_tendency = corruption_tendency
        self.loyalty = loyalty
        self.last_month_corrupted = False
        self.corruption_ratio = 0.0  # Concealment ratio (0-0.3)
        self.expenditure_inflation = 0.0  # Expenditure inflation ratio (0-0.2)

    def calculate_corruption_chance(self) -> float:
        """Calculate concealment probability for this month

        Base probability 30% + loyalty modifier (lower loyalty means higher probability)
        Maximum probability does not exceed 70%
        """
        base_chance = 0.3  # Base 30% probability
        loyalty_modifier = (100 - self.loyalty) / 200  # Lower loyalty means higher probability
        return min(base_chance + loyalty_modifier, 0.7)

    def decide_corruption(self):
        """Decide whether to conceal (called monthly)"""
        corruption_chance = self.calculate_corruption_chance()

        if random.random() < corruption_chance:
            # Concealment: randomly conceal 10-30% of income, inflate 5-20% of expenditure
            self.corruption_ratio = random.uniform(0.1, 0.3)
            self.expenditure_inflation = random.uniform(0.05, 0.2)
            self.last_month_corrupted = True
        else:
            # Honest reporting
            self.corruption_ratio = 0.0
            self.expenditure_inflation = 0.0
            self.last_month_corrupted = False

    def generate_report(self, actual_income: float, actual_expenditure: float) -> dict:
        """Generate report data

        Args:
            actual_income: Actual income
            actual_expenditure: Actual expenditure

        Returns:
            dict: Contains reported income and expenditure
        """
        return {
            'income': actual_income * (1 - self.corruption_ratio),
            'expenditure': actual_expenditure * (1 + self.expenditure_inflation)
        }
