"""
Behavior Definition System for Province Agent

Defines all available behavior types, their parameter ranges,
validation rules, and effect calculations.
"""

from typing import Dict, Any, List, Optional, Tuple
from agents.province.models import BehaviorType, BehaviorEffect


class BehaviorTemplate:
    """Template for a behavior type with parameter ranges and validation"""

    def __init__(
        self,
        behavior_type: BehaviorType,
        name: str,
        description: str,
        parameter_ranges: Dict[str, Tuple[float, float]],
        default_parameters: Dict[str, Any],
        cost_function: callable,
        effect_function: callable,
        validation_rules: List[callable] = None
    ):
        self.behavior_type = behavior_type
        self.name = name
        self.description = description
        self.parameter_ranges = parameter_ranges
        self.default_parameters = default_parameters
        self.cost_function = cost_function
        self.effect_function = effect_function
        self.validation_rules = validation_rules or []

    def validate_parameters(self, params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate parameters against ranges and rules"""
        # Check parameter ranges
        for param, (min_val, max_val) in self.parameter_ranges.items():
            if param in params:
                value = params[param]
                if not isinstance(value, (int, float)):
                    return False, f"Parameter {param} must be a number"
                if value < min_val or value > max_val:
                    return False, f"Parameter {param}={value} out of range [{min_val}, {max_val}]"

        # Check validation rules
        for rule in self.validation_rules:
            is_valid, error_msg = rule(params)
            if not is_valid:
                return False, error_msg

        return True, None

    def calculate_cost(self, params: Dict[str, Any]) -> float:
        """Calculate the cost of executing this behavior"""
        return self.cost_function(params)

    def calculate_effect(self, params: Dict[str, Any], province_state: Dict[str, Any]) -> BehaviorEffect:
        """Calculate the effects of executing this behavior"""
        return self.effect_function(params, province_state)


# ========== Behavior Templates ==========

BEHAVIOR_TEMPLATES: Dict[BehaviorType, BehaviorTemplate] = {}


def _register_behavior_template(template: BehaviorTemplate):
    """Register a behavior template"""
    BEHAVIOR_TEMPLATES[template.behavior_type] = template


# ========== Cost Functions ==========

def _tax_adjustment_cost(params: Dict[str, Any]) -> float:
    """Tax adjustment has no direct cost"""
    return 0.0


def _infrastructure_investment_cost(params: Dict[str, Any]) -> float:
    """Cost is the investment amount"""
    return params.get('amount', 100)


def _loyalty_campaign_cost(params: Dict[str, Any]) -> float:
    """Cost scales with intensity"""
    intensity = params.get('intensity', 1.0)  # 0.5 to 2.0
    return 50 * intensity


def _stability_measure_cost(params: Dict[str, Any]) -> float:
    """Cost scales with intensity"""
    intensity = params.get('intensity', 1.0)
    return 40 * intensity


def _emergency_relief_cost(params: Dict[str, Any]) -> float:
    """Cost is the relief amount"""
    return params.get('amount', 100)


def _corruption_crackdown_cost(params: Dict[str, Any]) -> float:
    """Cost scales with intensity"""
    intensity = params.get('intensity', 1.0)
    return 60 * intensity


def _economic_stimulus_cost(params: Dict[str, Any]) -> float:
    """Cost is the stimulus amount"""
    return params.get('amount', 150)


def _austerity_measure_cost(params: Dict[str, Any]) -> float:
    """Austerity saves money, negative cost"""
    return -params.get('savings_amount', 100)


# ========== Effect Functions ==========

def _apply_tax_adjustment(params: Dict[str, Any], province_state: Dict[str, Any]) -> BehaviorEffect:
    """Calculate tax adjustment effects"""
    rate_change = params.get('rate_change', 0.0)  # -0.20 to 0.20

    # Income change
    income_multiplier = 1.0 + rate_change
    base_income = province_state.get('actual_income', 800)
    income_change = base_income * rate_change

    # Loyalty and stability impact
    loyalty_change = -rate_change * 50  # Increasing tax hurts loyalty
    stability_change = -rate_change * 30

    return BehaviorEffect(
        behavior_type=BehaviorType.TAX_ADJUSTMENT,
        behavior_name="Tax Adjustment",
        income_change=income_change,
        loyalty_change=loyalty_change,
        stability_change=stability_change
    )


def _apply_infrastructure_investment(params: Dict[str, Any], province_state: Dict[str, Any]) -> BehaviorEffect:
    """Calculate infrastructure investment effects"""
    amount = params.get('amount', 100)
    duration = params.get('duration', 12)

    # Expenditure
    expenditure_change = amount

    # Development improvement
    development_change = amount / 200.0

    # Minor loyalty boost
    loyalty_change = min(5.0, amount / 50.0)

    # Stability improvement
    stability_change = min(3.0, amount / 100.0)

    # Future income potential (not immediate)
    income_change = 0.0

    return BehaviorEffect(
        behavior_type=BehaviorType.INFRASTRUCTURE_INVESTMENT,
        behavior_name="Infrastructure Investment",
        expenditure_change=expenditure_change,
        development_change=development_change,
        loyalty_change=loyalty_change,
        stability_change=stability_change,
        income_change=income_change,
        other_effects={
            'future_income_bonus': amount * 0.1,
            'duration_months': duration
        }
    )


def _apply_loyalty_campaign(params: Dict[str, Any], province_state: Dict[str, Any]) -> BehaviorEffect:
    """Calculate loyalty campaign effects"""
    intensity = params.get('intensity', 1.0)  # 0.5 to 2.0

    # Expenditure
    expenditure_change = 50 * intensity

    # Loyalty improvement
    loyalty_change = 8 * intensity

    # Minor stability improvement
    stability_change = 3 * intensity

    return BehaviorEffect(
        behavior_type=BehaviorType.LOYALTY_CAMPAIGN,
        behavior_name="Loyalty Campaign",
        expenditure_change=expenditure_change,
        loyalty_change=loyalty_change,
        stability_change=stability_change
    )


def _apply_stability_measure(params: Dict[str, Any], province_state: Dict[str, Any]) -> BehaviorEffect:
    """Calculate stability measure effects"""
    intensity = params.get('intensity', 1.0)

    # Expenditure
    expenditure_change = 40 * intensity

    # Stability improvement
    stability_change = 10 * intensity

    # Minor loyalty improvement
    loyalty_change = 2 * intensity

    return BehaviorEffect(
        behavior_type=BehaviorType.STABILITY_MEASURE,
        behavior_name="Stability Measure",
        expenditure_change=expenditure_change,
        loyalty_change=loyalty_change,
        stability_change=stability_change
    )


def _apply_emergency_relief(params: Dict[str, Any], province_state: Dict[str, Any]) -> BehaviorEffect:
    """Calculate emergency relief effects"""
    amount = params.get('amount', 100)

    # Expenditure
    expenditure_change = amount

    # Significant loyalty boost
    loyalty_change = min(15.0, amount / 20.0)

    # Stability improvement
    stability_change = min(10.0, amount / 30.0)

    return BehaviorEffect(
        behavior_type=BehaviorType.EMERGENCY_RELIEF,
        behavior_name="Emergency Relief",
        expenditure_change=expenditure_change,
        loyalty_change=loyalty_change,
        stability_change=stability_change
    )


def _apply_corruption_crackdown(params: Dict[str, Any], province_state: Dict[str, Any]) -> BehaviorEffect:
    """Calculate corruption crackdown effects"""
    intensity = params.get('intensity', 1.0)

    # Expenditure
    expenditure_change = 60 * intensity

    # Stability impact (can be destabilizing)
    stability_change = -5 * intensity

    # Loyalty mixed (some like it, some don't)
    loyalty_change = 0.0

    # Reduces corruption tendency
    corruption_change = -0.1 * intensity

    return BehaviorEffect(
        behavior_type=BehaviorType.CORRUPTION_CRACKDOWN,
        behavior_name="Corruption Crackdown",
        expenditure_change=expenditure_change,
        loyalty_change=loyalty_change,
        stability_change=stability_change,
        other_effects={
            'corruption_reduction': corruption_change
        }
    )


def _apply_economic_stimulus(params: Dict[str, Any], province_state: Dict[str, Any]) -> BehaviorEffect:
    """Calculate economic stimulus effects"""
    amount = params.get('amount', 150)

    # Expenditure
    expenditure_change = amount

    # Income boost (delayed effect)
    income_change = amount * 0.2

    # Loyalty improvement
    loyalty_change = min(10.0, amount / 30.0)

    return BehaviorEffect(
        behavior_type=BehaviorType.ECONOMIC_STIMULUS,
        behavior_name="Economic Stimulus",
        expenditure_change=expenditure_change,
        income_change=income_change,
        loyalty_change=loyalty_change
    )


def _apply_austerity_measure(params: Dict[str, Any], province_state: Dict[str, Any]) -> BehaviorEffect:
    """Calculate austerity measure effects"""
    savings_amount = params.get('savings_amount', 100)
    intensity = params.get('intensity', 1.0)

    # Expenditure reduction (negative change = savings)
    expenditure_change = -savings_amount

    # Loyalty penalty
    loyalty_change = -8 * intensity

    # Stability penalty
    stability_change = -5 * intensity

    return BehaviorEffect(
        behavior_type=BehaviorType.AUSTERITY_MEASURE,
        behavior_name="Austerity Measure",
        expenditure_change=expenditure_change,
        loyalty_change=loyalty_change,
        stability_change=stability_change
    )


# ========== Validation Rules ==========

def _validate_surplus_for_spending(params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Rule: Check if province has surplus for spending behaviors"""
    # This would need province context, simplified here
    return True, None


def _validate_tax_rate(params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Rule: Tax rate shouldn't be too extreme"""
    rate_change = params.get('rate_change', 0.0)
    if abs(rate_change) > 0.25:
        return False, "Tax rate change too extreme (max ±25%)"
    return True, None


# ========== Initialize Behavior Templates ==========

def initialize_behavior_templates():
    """Initialize all behavior templates"""

    # Tax Adjustment
    _register_behavior_template(BehaviorTemplate(
        behavior_type=BehaviorType.TAX_ADJUSTMENT,
        name="Tax Adjustment",
        description="Adjust tax rates to increase or decrease revenue",
        parameter_ranges={
            'rate_change': (-0.20, 0.20),  # -20% to +20%
            'duration': (1, 12)
        },
        default_parameters={'rate_change': 0.05, 'duration': 6},
        cost_function=_tax_adjustment_cost,
        effect_function=_apply_tax_adjustment,
        validation_rules=[_validate_tax_rate]
    ))

    # Infrastructure Investment
    _register_behavior_template(BehaviorTemplate(
        behavior_type=BehaviorType.INFRASTRUCTURE_INVESTMENT,
        name="Infrastructure Investment",
        description="Invest in infrastructure to improve development",
        parameter_ranges={
            'amount': (50, 500),
            'duration': (6, 24)
        },
        default_parameters={'amount': 150, 'duration': 12},
        cost_function=_infrastructure_investment_cost,
        effect_function=_apply_infrastructure_investment
    ))

    # Loyalty Campaign
    _register_behavior_template(BehaviorTemplate(
        behavior_type=BehaviorType.LOYALTY_CAMPAIGN,
        name="Loyalty Campaign",
        description="Run campaigns to improve population loyalty",
        parameter_ranges={
            'intensity': (0.5, 2.0),
            'duration': (3, 12)
        },
        default_parameters={'intensity': 1.0, 'duration': 6},
        cost_function=_loyalty_campaign_cost,
        effect_function=_apply_loyalty_campaign
    ))

    # Stability Measure
    _register_behavior_template(BehaviorTemplate(
        behavior_type=BehaviorType.STABILITY_MEASURE,
        name="Stability Measure",
        description="Implement measures to improve stability",
        parameter_ranges={
            'intensity': (0.5, 2.0),
            'duration': (3, 12)
        },
        default_parameters={'intensity': 1.0, 'duration': 6},
        cost_function=_stability_measure_cost,
        effect_function=_apply_stability_measure
    ))

    # Emergency Relief
    _register_behavior_template(BehaviorTemplate(
        behavior_type=BehaviorType.EMERGENCY_RELIEF,
        name="Emergency Relief",
        description="Provide emergency relief to boost loyalty and stability",
        parameter_ranges={
            'amount': (50, 300),
            'target': (0, 1)  # 0=general, 1=specific region
        },
        default_parameters={'amount': 100, 'target': 0},
        cost_function=_emergency_relief_cost,
        effect_function=_apply_emergency_relief
    ))

    # Corruption Crackdown
    _register_behavior_template(BehaviorTemplate(
        behavior_type=BehaviorType.CORRUPTION_CRACKDOWN,
        name="Corruption Crackdown",
        description="Launch crackdown on corruption",
        parameter_ranges={
            'intensity': (0.5, 2.0),
            'duration': (6, 24)
        },
        default_parameters={'intensity': 1.0, 'duration': 12},
        cost_function=_corruption_crackdown_cost,
        effect_function=_apply_corruption_crackdown
    ))

    # Economic Stimulus
    _register_behavior_template(BehaviorTemplate(
        behavior_type=BehaviorType.ECONOMIC_STIMULUS,
        name="Economic Stimulus",
        description="Stimulate the economy with investment",
        parameter_ranges={
            'amount': (100, 400),
            'duration': (6, 18)
        },
        default_parameters={'amount': 200, 'duration': 12},
        cost_function=_economic_stimulus_cost,
        effect_function=_apply_economic_stimulus
    ))

    # Austerity Measure
    _register_behavior_template(BehaviorTemplate(
        behavior_type=BehaviorType.AUSTERITY_MEASURE,
        name="Austerity Measure",
        description="Implement austerity to reduce expenditure",
        parameter_ranges={
            'savings_amount': (50, 200),
            'intensity': (0.5, 2.0),
            'duration': (6, 24)
        },
        default_parameters={'savings_amount': 100, 'intensity': 1.0, 'duration': 12},
        cost_function=_austerity_measure_cost,
        effect_function=_apply_austerity_measure
    ))


# Initialize on module load
initialize_behavior_templates()


# ========== Utility Functions ==========

def get_behavior_template(behavior_type: BehaviorType) -> Optional[BehaviorTemplate]:
    """Get behavior template by type"""
    return BEHAVIOR_TEMPLATES.get(behavior_type)


def list_available_behaviors() -> List[Dict[str, Any]]:
    """List all available behavior types"""
    return [
        {
            'type': template.behavior_type.value,
            'name': template.name,
            'description': template.description,
            'parameter_ranges': template.parameter_ranges,
            'default_parameters': template.default_parameters
        }
        for template in BEHAVIOR_TEMPLATES.values()
    ]


def validate_behavior_parameters(behavior_type: BehaviorType, params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate behavior parameters"""
    template = get_behavior_template(behavior_type)
    if template is None:
        return False, f"Unknown behavior type: {behavior_type}"

    return template.validate_parameters(params)


def calculate_behavior_cost(behavior_type: BehaviorType, params: Dict[str, Any]) -> float:
    """Calculate behavior cost"""
    template = get_behavior_template(behavior_type)
    if template is None:
        return 0.0

    return template.calculate_cost(params)


def calculate_behavior_effect(behavior_type: BehaviorType, params: Dict[str, Any], province_state: Dict[str, Any]) -> BehaviorEffect:
    """Calculate behavior effect"""
    template = get_behavior_template(behavior_type)
    if template is None:
        return BehaviorEffect(
            behavior_type=behavior_type,
            behavior_name="Unknown Behavior"
        )

    return template.calculate_effect(params, province_state)
