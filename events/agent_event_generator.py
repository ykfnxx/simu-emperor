"""
Agent Proactive Event Generator

GovernorAgent can proactively generate events (real or fabricated) for strategic purposes
"""

import random
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from .event_models import AgentEvent, AgentEventType, EventEffect, EffectScope, EffectOperation, EventVisibility


class AgentEventGenerator:
    """Agent Event Generator"""

    def __init__(self):
        """Initialize Agent event generator"""
        # Define event preferences for different Agent personalities
        self.event_preferences = {
            'corrupt': [  # Corrupt official
                AgentEventType.FINANCIAL_SHORTAGE,
                AgentEventType.MAINTENANCE_ISSUE,
                AgentEventType.PUBLIC_PROTEST,
                AgentEventType.TAX_ADJUSTMENT
            ],
            'deceptive': [  # Deceptive official
                AgentEventType.TRADE_DISRUPTION,
                AgentEventType.POLITICAL_REFORM,
                AgentEventType.ECONOMIC_OPPORTUNITY,
                AgentEventType.BUDGET_REALLOCATION
            ],
            'ambitious': [  # Ambitious official
                AgentEventType.ECONOMIC_OPPORTUNITY,
                AgentEventType.INFRASTRUCTURE_PROJECT,
                AgentEventType.POLITICAL_REFORM
            ],
            'cautious': [  # Cautious official
                AgentEventType.MAINTENANCE_ISSUE,
                AgentEventType.ACCIDENT
            ],
            'pragmatic': [  # Pragmatic official
                AgentEventType.BUDGET_REALLOCATION,
                AgentEventType.TAX_ADJUSTMENT,
                AgentEventType.MAINTENANCE_ISSUE
            ],
            'honest': [  # Honest official
                AgentEventType.INFRASTRUCTURE_PROJECT,
                AgentEventType.ACCIDENT
            ]
        }

    def assess_situation_for_event_generation(
        self,
        governor: Any,
        current_state: Dict[str, Any],
        game_context: Dict[str, Any]
    ) -> float:
        """
        Assess current situation to determine if event generation is appropriate

        Return value: 0.0-2.0, as a multiplier for generation probability

        Considerations:
        - Central attention level
        - Treasury status
        - Loyalty
        - Current needs (covering deception/requesting resources)
        """
        multiplier = 1.0

        # Factor 1: Central attention level
        central_attention = game_context.get('central_attention', 0.5)
        if central_attention > 0.7:
            # High central attention, reduce event generation (to avoid suspicion)
            multiplier *= 0.5
        elif central_attention < 0.3:
            # Low central attention, increase event generation
            multiplier *= 1.5

        # Factor 2: Current economic status
        treasury = game_context.get('treasury', 1000)
        income = current_state.get('actual_income', 0)

        if treasury < 500:
            # Tight treasury, increase generation of finance-related events
            multiplier *= 1.3

        if income < 300:
            # Low income, increase generation of economy-related events
            multiplier *= 1.2

        # Factor 3: Loyalty
        loyalty = getattr(governor.personality, 'loyalty_base', 70)
        if loyalty < 50:
            # Low loyalty, more likely to generate deceptive events
            multiplier *= 1.4

        # Factor 4: Whether cover-up is needed
        needs_cover = game_context.get('needs_cover', False)
        if needs_cover:
            # Need to cover up data anomalies, significantly increase generation probability
            multiplier *= 2.0

        # Factor 5: Event generation capability
        generation_rate = governor.personality.capabilities.event_generation_rate
        multiplier *= (0.5 + generation_rate)

        return min(multiplier, 2.0)

    def select_event_type(
        self,
        governor: Any,
        current_state: Dict[str, Any],
        game_context: Dict[str, Any]
    ) -> AgentEventType:
        """
        Select appropriate event type

        Based on:
        - Governor personality
        - Current needs (covering up/requesting resources/showing achievements)
        - Province status
        """
        # Get Governor personality type
        trait = governor.personality.primary_trait

        # Get preferred events based on personality
        preferred_events = self.event_preferences.get(trait, list(AgentEventType))

        # Adjust weights based on current needs
        weights = [1.0] * len(preferred_events)

        # If cover-up is needed
        if game_context.get('needs_cover', False):
            # Prioritize events that can explain data anomalies
            cover_events = [
                AgentEventType.FINANCIAL_SHORTAGE,
                AgentEventType.MAINTENANCE_ISSUE,
                AgentEventType.PUBLIC_PROTEST,
                AgentEventType.TRADE_DISRUPTION
            ]
            for i, event_type in enumerate(preferred_events):
                if event_type in cover_events:
                    weights[i] *= 3.0

        # If central resources are needed
        if game_context.get('needs_resources', False):
            resource_events = [
                AgentEventType.NATURAL_DISASTER,
                AgentEventType.PLAGUE_OUTBREAK,
                AgentEventType.FINANCIAL_SHORTAGE,
                AgentEventType.PUBLIC_PROTEST
            ]
            for i, event_type in enumerate(preferred_events):
                if event_type in resource_events:
                    weights[i] *= 2.0

        # If income is high and wants to show achievements
        income = current_state.get('actual_income', 0)
        if income > 500:
            achievement_events = [
                AgentEventType.ECONOMIC_OPPORTUNITY,
                AgentEventType.INFRASTRUCTURE_PROJECT
            ]
            for i, event_type in enumerate(preferred_events):
                if event_type in achievement_events:
                    weights[i] *= 1.5

        # Normalize weights
        total_weight = sum(weights)
        if total_weight == 0:
            weights = [1.0] * len(preferred_events)
        else:
            weights = [w / total_weight for w in weights]

        # Weighted random selection
        return random.choices(preferred_events, weights=weights, k=1)[0]

    def create_event_from_type(
        self,
        event_type: AgentEventType,
        governor: Any,
        province_id: int,
        month: int
    ) -> AgentEvent:
        """
        Create AgentEvent based on event type

        Args:
            event_type: Event type
            governor: GovernorAgent object
            province_id: Province ID
            month: Current month

        Returns:
            AgentEvent object
        """
        # Use the event_type directly
        event_type_value = event_type

        # Define template parameters for different event types
        event_configs = {
            # Finance related
            AgentEventType.TAX_ADJUSTMENT: {
                'name': 'Tax Adjustment',
                'description': 'Local government adjusts tax policies',
                'severity': 0.4,
                'effects': [
                    {'scope': EffectScope.LOYALTY, 'operation': EffectOperation.ADD, 'value': -10, 'duration': 6},
                    {'scope': EffectScope.INCOME, 'operation': EffectOperation.MULTIPLY, 'value': 1.15, 'duration': 6}
                ]
            },
            AgentEventType.BUDGET_REALLOCATION: {
                'name': 'Budget Reallocation',
                'description': 'Local government reallocates budget',
                'severity': 0.3,
                'effects': [
                    {'scope': EffectScope.EXPENDITURE, 'operation': EffectOperation.MULTIPLY, 'value': 0.9, 'duration': 3}
                ]
            },
            AgentEventType.FINANCIAL_SHORTAGE: {
                'name': 'Financial Shortage',
                'description': 'Local finance experiences shortage',
                'severity': 0.6,
                'effects': [
                    {'scope': EffectScope.EXPENDITURE, 'operation': EffectOperation.MULTIPLY, 'value': 1.2, 'duration': 4}
                ]
            },

            # Infrastructure
            AgentEventType.INFRASTRUCTURE_PROJECT: {
                'name': 'Infrastructure Project',
                'description': 'Launch new infrastructure project',
                'severity': 0.3,
                'effects': [
                    {'scope': EffectScope.DEVELOPMENT, 'operation': EffectOperation.ADD, 'value': 0.5},
                    {'scope': EffectScope.EXPENDITURE, 'operation': EffectOperation.MULTIPLY, 'value': 1.3, 'duration': 3}
                ]
            },
            AgentEventType.MAINTENANCE_ISSUE: {
                'name': 'Maintenance Issue',
                'description': 'Infrastructure needs emergency maintenance',
                'severity': 0.5,
                'effects': [
                    {'scope': EffectScope.EXPENDITURE, 'operation': EffectOperation.MULTIPLY, 'value': 1.25, 'duration': 2}
                ]
            },

            # Social events
            AgentEventType.PUBLIC_PROTEST: {
                'name': 'Public Protest',
                'description': 'Public dissatisfaction with policies',
                'severity': 0.7,
                'effects': [
                    {'scope': EffectScope.STABILITY, 'operation': EffectOperation.MULTIPLY, 'value': 0.8, 'duration': 3},
                    {'scope': EffectScope.EXPENDITURE, 'operation': EffectOperation.MULTIPLY, 'value': 1.3, 'duration': 2}
                ]
            },
            AgentEventType.SOCIAL_UNREST: {
                'name': 'Social Unrest',
                'description': 'Signs of social instability',
                'severity': 0.8,
                'effects': [
                    {'scope': EffectScope.STABILITY, 'operation': EffectOperation.ADD, 'value': -20, 'duration': 4},
                    {'scope': EffectScope.EXPENDITURE, 'operation': EffectOperation.MULTIPLY, 'value': 1.4, 'duration': 3}
                ]
            },
            AgentEventType.POPULATION_MIGRATION: {
                'name': 'Population Migration',
                'description': 'Large-scale population migration',
                'severity': 0.6,
                'effects': [
                    {'scope': EffectScope.POPULATION, 'operation': EffectOperation.ADD, 'value': -2000},
                    {'scope': EffectScope.INCOME, 'operation': EffectOperation.MULTIPLY, 'value': 0.9, 'duration': 5}
                ]
            },

            # Natural disasters/accidents
            AgentEventType.NATURAL_DISASTER: {
                'name': 'Natural Disaster',
                'description': 'Natural disaster causes losses',
                'severity': 0.9,
                'effects': [
                    {'scope': EffectScope.STABILITY, 'operation': EffectOperation.MULTIPLY, 'value': 0.7, 'duration': 3},
                    {'scope': EffectScope.INCOME, 'operation': EffectOperation.MULTIPLY, 'value': 0.7, 'duration': 2}
                ]
            },
            AgentEventType.ACCIDENT: {
                'name': 'Accident',
                'description': 'Unexpected accident occurs',
                'severity': 0.5,
                'effects': [
                    {'scope': EffectScope.EXPENDITURE, 'operation': EffectOperation.MULTIPLY, 'value': 1.3, 'duration': 2}
                ]
            },
            AgentEventType.PLAGUE_OUTBREAK: {
                'name': 'Plague Outbreak',
                'description': 'Serious plague outbreak',
                'severity': 0.8,
                'effects': [
                    {'scope': EffectScope.POPULATION, 'operation': EffectOperation.ADD, 'value': -3000},
                    {'scope': EffectScope.EXPENDITURE, 'operation': EffectOperation.MULTIPLY, 'value': 1.4, 'duration': 3}
                ]
            },

            # Economic events
            AgentEventType.TRADE_DISRUPTION: {
                'name': 'Trade Disruption',
                'description': 'Trade routes interrupted',
                'severity': 0.6,
                'effects': [
                    {'scope': EffectScope.INCOME, 'operation': EffectOperation.MULTIPLY, 'value': 0.8, 'duration': 4}
                ]
            },
            AgentEventType.ECONOMIC_OPPORTUNITY: {
                'name': 'Economic Opportunity',
                'description': 'New economic opportunity discovered',
                'severity': 0.4,
                'effects': [
                    {'scope': EffectScope.INCOME, 'operation': EffectOperation.MULTIPLY, 'value': 1.25, 'duration': 6}
                ]
            },

            # Political events
            AgentEventType.OFFICIAL_INVESTIGATION: {
                'name': 'Official Investigation',
                'description': 'Investigation of local officials',
                'severity': 0.7,
                'effects': [
                    {'scope': EffectScope.STABILITY, 'operation': EffectOperation.MULTIPLY, 'value': 0.85, 'duration': 3}
                ]
            },
            AgentEventType.POLITICAL_REFORM: {
                'name': 'Political Reform',
                'description': 'Implementation of political reform',
                'severity': 0.6,
                'effects': [
                    {'scope': EffectScope.LOYALTY, 'operation': EffectOperation.ADD, 'value': 15, 'duration': 5}
                ]
            }
        }

        config = event_configs.get(event_type, {
            'name': 'Unknown Event',
            'description': 'Unknown event type',
            'severity': 0.5,
            'effects': []
        })

        # Generate effect list
        effects = []
        for effect_def in config['effects']:
            effect = EventEffect(
                scope=effect_def['scope'],
                operation=effect_def['operation'],
                value=effect_def['value']
            )
            effects.append(effect)

        # Determine duration (if any)
        duration = None
        if config['effects'] and 'duration' in config['effects'][0]:
            duration = config['effects'][0]['duration']

        # Create event
        return AgentEvent(
            event_id=f"agent_event_{province_id}_{month}_{random.randint(1000, 9999)}",
            name=config['name'],
            description=config['description'],
            province_id=province_id,
            generated_by=governor.agent_id,
            generated_by_agent_id=governor.agent_id,  # Add agent_id field
            instant_effects=[],
            continuous_effects=effects,
            start_month=month,
            end_month=month + duration if duration else None,
            severity=config['severity'],
            narrative=f"Local official report: {config['description']}",
            visibility=EventVisibility.PROVINCIAL
        )

    def generate_agent_event(
        self,
        governor: Any,
        current_state: Dict[str, Any],
        game_context: Dict[str, Any]
    ) -> Optional[AgentEvent]:
        """
        Complete process to generate Agent event

        Args:
            governor: GovernorAgent object
            current_state: Current province state
            game_context: Game context

        Returns:
            AgentEvent or None
        """
        # Assess situation
        situation_score = self.assess_situation_for_event_generation(
            governor, current_state, game_context
        )

        # Determine event generation probability
        generation_rate = governor.personality.capabilities.event_generation_rate
        actual_generation_rate = generation_rate * situation_score

        if random.random() >= actual_generation_rate:
            return None

        # Select event type
        event_type = self.select_event_type(governor, current_state, game_context)

        # Decide whether it's a real event or fabricated
        needs_cover = game_context.get('needs_cover', False)
        fabrication_skill = governor.personality.capabilities.fabrication_skill

        # Fabrication probability
        fabrication_chance = 0.3  # Base probability
        fabrication_chance *= (1.5 if needs_cover else 0.5)  # If cover-up needed
        fabrication_chance *= fabrication_skill  # Consider fabrication skill
        fabrication_chance = min(fabrication_chance, 0.8)

        is_fabricated = random.random() < fabrication_chance

        # Create event
        province_id = current_state.get('province_id')
        month = game_context.get('month', 1)

        event = self.create_event_from_type(event_type, governor, province_id, month)

        # Set fabrication attributes
        if is_fabricated:
            event.is_fabricated = True
            event.fabrication_reason = "To cover up data anomalies or obtain central resources"
            event.supporting_evidence = "Local government document (ID: XXXX)"

        # Set visibility
        concealment_probability = governor.personality.hide_event_probability
        if random.random() < concealment_probability:
            event.visibility = EventVisibility.HIDDEN
            event.is_hidden_by_governor = True
            event.hidden_reason = "Event is still under assessment, not yet disclosed"

        return event
