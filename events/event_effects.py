"""
Event Effects Calculator

Pure functions to calculate event effects, no side effects
"""

from typing import Dict, List, Optional, Any
from .event_models import Event, EventEffect, EffectOperation, EffectScope

def calculate_event_modifiers(
    events: List[Event],
    province_id: Optional[int] = None,
    current_month: Optional[int] = None
) -> Dict[str, float]:
    """
    Calculate event modifiers (pure function)

    Args:
        events: List of active events
        province_id: Province ID (when calculating province-specific modifiers)
        current_month: Current month (to filter expired events)

    Returns:
        Modifier dictionary containing various modifiers

    Modifier format:
    {
        'income_multiplier': 1.0,
        'income_addition': 0.0,
        'expenditure_multiplier': 1.0,
        'expenditure_addition': 0.0,
        'loyalty_addition': 0.0,
        'stability_addition': 0.0,
        'development_addition': 0.0,
        'population_addition': 0
    }
    """
    modifiers = {
        'income_multiplier': 1.0,
        'income_addition': 0.0,
        'expenditure_multiplier': 1.0,
        'expenditure_addition': 0.0,
        'loyalty_addition': 0.0,
        'stability_addition': 0.0,
        'development_addition': 0.0,
        'population_addition': 0
    }

    for event in events:
        # Skip non-active events
        if not event.is_active:
            continue

        # Check if expired
        if current_month and event.is_expired(current_month):
            continue

        # Skip non-related province events
        if province_id and event.province_id != province_id:
            continue

        # Apply continuous effects
        for effect in event.continuous_effects:
            # Ensure scope is a string (handle use_enum_values case)
            scope = effect.scope.value if hasattr(effect.scope, 'value') else effect.scope

            # Build key
            if effect.operation == EffectOperation.MULTIPLY:
                key = f'{scope}_multiplier'
            else:  # ADD or OVERRIDE
                key = f'{scope}_addition'

            # Apply effect
            if effect.operation == EffectOperation.MULTIPLY:
                modifiers[key] *= effect.value
            elif effect.operation == EffectOperation.ADD:
                modifiers[key] += effect.value
            elif effect.operation == EffectOperation.OVERRIDE:
                # OVERRIDE is rarely used in continuous effects, special handling if needed
                modifiers[key] = effect.value

    return modifiers

def apply_instant_effects(
    event: Event,
    target_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Apply instant effects (pure function)

    Args:
        event: Event
        target_data: Target data (province data)

    Returns:
        Modified data copy
    """
    modified_data = target_data.copy()

    for effect in event.instant_effects:
        scope = effect.scope.value

        # Check if attribute exists
        if scope in modified_data:
            current_value = modified_data[scope]

            # Apply effect
            if effect.operation == EffectOperation.MULTIPLY:
                modified_data[scope] = current_value * effect.value
            elif effect.operation == EffectOperation.ADD:
                modified_data[scope] = current_value + effect.value
            elif effect.operation == EffectOperation.OVERRIDE:
                modified_data[scope] = effect.value

            # Ensure values are within reasonable ranges
            if scope in ['loyalty', 'stability']:
                # Loyalty and stability limited to 0-100
                modified_data[scope] = max(0.0, min(100.0, modified_data[scope]))
            elif scope == 'development_level':
                # Development level at least 1
                modified_data[scope] = max(1.0, modified_data[scope])
            elif scope == 'population':
                # Population at least 1000
                modified_data[scope] = max(1000, int(modified_data[scope]))

    return modified_data

def apply_multiple_instant_effects(
    events: List[Event],
    target_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Apply multiple events' instant effects (in order)

    Args:
        events: List of events
        target_data: Target data

    Returns:
        Modified data
    """
    modified_data = target_data.copy()

    for event in events:
        if event.instant_effects:
            modified_data = apply_instant_effects(event, modified_data)

    return modified_data

def calculate_event_impact(
    event: Event,
    base_values: Dict[str, float]
) -> Dict[str, float]:
    """
    Calculate event impact on base values (pure function)

    Args:
        event: Event
        base_values: Base values dictionary

    Returns:
        Impact values dictionary
    """
    impact = {}

    # Calculate instant effect impact
    for effect in event.instant_effects:
        scope = effect.scope.value
        if scope in base_values:
            if effect.operation == EffectOperation.MULTIPLY:
                impact[scope] = base_values[scope] * (effect.value - 1)
            elif effect.operation == EffectOperation.ADD:
                impact[scope] = effect.value
            elif effect.operation == EffectOperation.OVERRIDE:
                impact[scope] = effect.value - base_values[scope]

    # Calculate continuous effect impact (assuming 1 turn duration)
    for effect in event.continuous_effects:
        scope = effect.scope.value
        if scope in base_values:
            if effect.operation == EffectOperation.MULTIPLY:
                impact[scope] = impact.get(scope, 0) + base_values[scope] * (effect.value - 1)
            elif effect.operation == EffectOperation.ADD:
                impact[scope] = impact.get(scope, 0) + effect.value

    return impact

def merge_modifiers(modifiers_list: List[Dict[str, float]]) -> Dict[str, float]:
    """
    Merge multiple modifiers (pure function)

    Used for handling multiple events taking effect simultaneously

    Args:
        modifiers_list: List of modifiers

    Returns:
        Merged modifiers
    """
    if not modifiers_list:
        return {}

    result = modifiers_list[0].copy()

    for modifiers in modifiers_list[1:]:
        for key, value in modifiers.items():
            if 'multiplier' in key:
                # Multiplicative effects: multiply
                result[key] *= value
            else:
                # Additive effects: add
                result[key] += value

    return result

def validate_modifier_values(modifiers: Dict[str, float]) -> Dict[str, float]:
    """
    Validate and correct modifier values for reasonableness

    Args:
        modifiers: Original modifiers

    Returns:
        Corrected values

    Rules:
    - multiplier limited to 0.1-3.0
    - addition limited to reasonable ranges
    """
    validated = modifiers.copy()

    for key, value in validated.items():
        if 'multiplier' in key:
            # Multiplier limited to 0.1-3.0
            validated[key] = max(0.1, min(3.0, value))
        elif 'addition' in key:
            # Add value limits depend on type
            if 'income' in key or 'expenditure' in key:
                # Income/expenditure add values limited to -1000 to 1000
                validated[key] = max(-1000.0, min(1000.0, value))
            elif 'loyalty' in key or 'stability' in key:
                # Loyalty/stability add values limited to -50 to 50
                validated[key] = max(-50.0, min(50.0, value))
            elif 'development' in key:
                # Development add values limited to -2 to 2
                validated[key] = max(-2.0, min(2.0, value))
            elif 'population' in key:
                # Population add values limited to -10000 to 10000
                validated[key] = max(-10000.0, min(10000.0, value))

    return validated
