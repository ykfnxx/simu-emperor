"""
Core calculation module - Pure functions, no business logic
All functions are pure functions, no side effects, easy to test
"""

from typing import Tuple


def calculate_province_income(
    population: int,
    development_level: float,
    stability: float,
    base_coefficient: float = 4.0,  # Final coefficient: reduced from 15.0 to 4.0
    random_factor: float = 1.0
) -> float:
    """Calculate province income (pure function)

    Formula: Income = (Population/1000) × Development Level × Base Coefficient × (Stability/100) × Random Factor

    Args:
        population: Population size
        development_level: Development level (1-10)
        stability: Stability (0-100)
        base_coefficient: Base income coefficient (default 4.0)
        random_factor: Random fluctuation factor (default 1.0, range 0.9-1.1)

    Returns:
        Calculated income value
    """
    return (
        (population / 1000.0)
        * development_level
        * base_coefficient
        * (stability / 100.0)
        * random_factor
    )


def calculate_province_expenditure(
    population: int,
    stability: float,
    base_coefficient: float = 14.0  # Increased from 8.0 to 14.0, significantly increasing expenditure
) -> float:
    """Calculate province expenditure (pure function)

    Formula: Expenditure = (Population/1000) × Base Coefficient × (2 - Stability/100)
    Lower stability means higher security maintenance costs

    Args:
        population: Population size
        stability: Stability (0-100)
        base_coefficient: Base expenditure coefficient (default 14.0)

    Returns:
        Calculated expenditure value
    """
    return (
        (population / 1000.0)
        * base_coefficient
        * (2.0 - stability / 100.0)
    )


def calculate_corruption_probability(
    corruption_tendency: float,
    loyalty: float,
    base_chance: float = 0.3
) -> float:
    """Calculate corruption probability (pure function)

    Formula: Probability = Base Probability + (100 - Loyalty)/200
    Maximum probability does not exceed 70%

    Args:
        corruption_tendency: Corruption tendency (0-1)
        loyalty: Loyalty (0-100)
        base_chance: Base probability (default 0.3)

    Returns:
        Corruption probability (0-0.7)
    """
    loyalty_modifier = (100 - loyalty) / 200
    return min(base_chance + loyalty_modifier, 0.7)


def apply_corruption_to_values(
    actual_income: float,
    actual_expenditure: float,
    corruption_ratio: float,
    expenditure_inflation: float
) -> Tuple[float, float]:
    """Apply corruption to income/expenditure data (pure function)

    Args:
        actual_income: Actual income
        actual_expenditure: Actual expenditure
        corruption_ratio: Concealment ratio (0-0.3)
        expenditure_inflation: Expenditure inflation ratio (0-0.2)

    Returns:
        Tuple of (reported income, reported expenditure)
    """
    reported_income = actual_income * (1 - corruption_ratio)
    reported_expenditure = actual_expenditure * (1 + expenditure_inflation)
    return reported_income, reported_expenditure


def calculate_treasury_change(provinces_data: list) -> float:
    """Calculate national treasury change (pure function)

    Treasury change = Total actual income of all provinces - Total actual expenditure of all provinces

    Args:
        provinces_data: List of province data, each element must contain actual_income and actual_expenditure

    Returns:
        Treasury change value (positive means surplus, negative means deficit)
    """
    total_income = sum(p.get('actual_income', 0) for p in provinces_data)
    total_expenditure = sum(p.get('actual_expenditure', 0) for p in provinces_data)
    return total_income - total_expenditure


def calculate_project_effect(
    project_type: str,
    effect_value: float,
    current_value: float
) -> float:
    """Calculate project effects (pure function)

    Args:
        project_type: Project type (income_bonus/development_bonus/loyalty_bonus/stability_bonus)
        effect_value: Effect value
        current_value: Current value

    Returns:
        New value after applying effect
    """
    if project_type == 'income_bonus':
        # Income bonus: percentage increase
        return current_value * (1 + effect_value)
    elif project_type in ['development_bonus', 'loyalty_bonus', 'stability_bonus']:
        # Attribute bonus: direct increase (cap at 100)
        return min(100.0, current_value + effect_value)
    else:
        # Unknown type, return original value
        return current_value


def generate_random_factor(seed: int = None) -> float:
    """Generate random factor (pure function)

    Returns a random number between 0.9-1.1, used to introduce random fluctuations

    Args:
        seed: Random seed (optional, for repeatable testing)

    Returns:
        Random factor (0.9-1.1)
    """
    import random
    if seed is not None:
        random.seed(seed)
    return random.uniform(0.9, 1.1)
