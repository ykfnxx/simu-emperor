"""
Event Generator

Generate random events based on game state
"""

import random
from typing import Dict, List, Any, Optional
from .event_models import Event, EventType, EventEffect, EffectScope, EffectOperation
from .event_templates import EVENT_TEMPLATES, RARITY_WEIGHTS
from datetime import datetime
import math


class EventGenerator:
    """Event Generator"""

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize event generator

        Args:
            config: Configuration parameters
                - event_probability: Base event probability (default 0.3)
                - national_event_ratio: National event ratio (default 0.2)
                - max_events_per_month: Maximum events per month (default 3)
        """
        self.config = config or {}
        self.event_probability = self.config.get('event_probability', 0.3)
        self.national_event_ratio = self.config.get('national_event_ratio', 0.2)
        self.max_events_per_month = self.config.get('max_events_per_month', 3)

        # Load event definitions from templates
        self.templates = EVENT_TEMPLATES

        # Rarity weights
        self.rarity_weights = RARITY_WEIGHTS

    def _generate_event_id(self, template_id: str, month: int, province_id: Optional[int] = None) -> str:
        """
        Generate unique event ID

        Args:
            template_id: Template ID
            month: Event month
            province_id: Province ID (None for national events)

        Returns:
            Unique event ID string
        """
        import uuid

        # Create prefix based on event type
        prefix = 'NAT' if province_id is None else f'PROV{province_id}'

        # Generate unique ID using UUID
        unique_part = str(uuid.uuid4())[:8]

        return f"{prefix}_{template_id}_M{month}_{unique_part}"

    def generate_events(self,
                       game_state: Dict[str, Any],
                       provinces: List[Dict[str, Any]],
                       current_month: int) -> List[Event]:
        """
        Generate events for this month

        Args:
            game_state: Game state
            provinces: List of provinces
            current_month: Current month

        Returns:
            List of generated events
        """
        events = []

        # Determine number of events this month
        if random.random() > self.event_probability:
            return events  # No events this month

        # Determine number of events (between 1 and max_events_per_month)
        num_events = random.randint(1, self.max_events_per_month)

        # Adjust based on rarity distribution
        rarity_roll = random.random()
        if rarity_roll < 0.1:  # 10% chance of only 1 event
            num_events = 1
        elif rarity_roll < 0.3:  # 20% chance of 2 events
            num_events = min(2, num_events)

        for _ in range(num_events):
            # Determine event type
            is_national = random.random() < self.national_event_ratio

            if is_national:
                event = self._generate_national_event(game_state, current_month)
            else:
                # Randomly select a province
                province = random.choice(provinces)
                event = self._generate_province_event(province, current_month)

            if event:
                events.append(event)

        return events

    def _generate_national_event(self,
                                 game_state: Dict[str, Any],
                                 current_month: int) -> Optional[Event]:
        """
        Generate national event

        Args:
            game_state: Game state
            current_month: Current month

        Returns:
            Event object or None
        """
        # Get available templates
        templates = self.templates.get('national', [])

        if not templates:
            return None

        # Filter suitable templates based on game state
        eligible_templates = []
        for template in templates:
            if self._check_template_conditions(template, game_state):
                eligible_templates.append(template)

        if not eligible_templates:
            return None

        # Weighted random selection by rarity
        weights = []
        for template in eligible_templates:
            rarity = template.get('metadata', {}).get('rarity', 'common')
            weight = self.rarity_weights.get(rarity, 0.6)
            weights.append(weight)

        # Normalize weights
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]

        # Weighted random selection
        template = random.choices(eligible_templates, weights=weights, k=1)[0]

        # Create event from template
        return self._create_event_from_template(
            template, EventType.NATIONAL, current_month
        )

    def _generate_province_event(self,
                                 province: Dict[str, Any],
                                 current_month: int) -> Optional[Event]:
        """
        Generate province event

        Args:
            province: Province data
            current_month: Current month

        Returns:
            Event object or None
        """
        # Get available templates
        templates = self.templates.get('province', [])

        if not templates:
            return None

        # Filter based on province state
        eligible_templates = []
        for template in templates:
            if self._check_template_conditions(template, province):
                eligible_templates.append(template)

        if not eligible_templates:
            return None

        # Weighted random selection by rarity
        weights = []
        for template in eligible_templates:
            rarity = template.get('metadata', {}).get('rarity', 'common')
            weight = self.rarity_weights.get(rarity, 0.6)
            weights.append(weight)

        # Normalize weights
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]

        # Weighted random selection
        template = random.choices(eligible_templates, weights=weights, k=1)[0]

        # Create event from template
        return self._create_event_from_template(
            template, EventType.PROVINCE, current_month,
            province_id=province.get('province_id')
        )

    def _check_template_conditions(self,
                                   template: Dict[str, Any],
                                   context: Dict[str, Any]) -> bool:
        """
        Check if template conditions are met

        Args:
            template: Event template
            context: Context data

        Returns:
            Whether conditions are met
        """
        conditions = template.get('conditions', {})

        if not conditions:
            return True  # No condition restrictions

        for key, condition in conditions.items():
            if key not in context:
                continue

            value = context[key]

            # Handle different types of conditions
            if isinstance(condition, dict):
                # Range condition
                if 'min' in condition and value < condition['min']:
                    return False
                if 'max' in condition and value > condition['max']:
                    return False
            elif isinstance(condition, (int, float)):
                # Minimum value condition
                if value < condition:
                    return False
            elif isinstance(condition, str):
                # Equality condition
                if str(value) != condition:
                    return False

        return True

    def _create_event_from_template(self,
                                    template: Dict[str, Any],
                                    event_type: EventType,
                                    current_month: int,
                                    province_id: Optional[int] = None) -> Event:
        """
        Create event from template

        Args:
            template: Event template
            event_type: Event type
            current_month: Current month
            province_id: Province ID (for province events)

        Returns:
            Event object
        """
        # Generate effects
        instant_effects = []
        continuous_effects = []

        # Process instant effects
        for effect_template in template.get('instant_effects', []):
            effect = EventEffect(
                scope=EffectScope(effect_template['scope']),
                operation=EffectOperation(effect_template['operation']),
                value=effect_template['value']
            )
            instant_effects.append(effect)

        # Process continuous effects
        for effect_template in template.get('continuous_effects', []):
            effect = EventEffect(
                scope=EffectScope(effect_template['scope']),
                operation=EffectOperation(effect_template['operation']),
                value=effect_template['value'],
                duration=effect_template.get('duration')
            )
            continuous_effects.append(effect)

        # Determine duration
        duration = template.get('duration')
        end_month = None
        if duration:
            end_month = current_month + duration - 1

        # Generate event ID
        event_id = self._generate_event_id(
            template['id'], current_month, province_id
        )

        return Event(
            event_id=event_id,
            name=template['name'],
            description=template['description'],
            event_type=event_type,
            province_id=province_id,
            instant_effects=instant_effects,
            continuous_effects=continuous_effects,
            start_month=current_month,
            end_month=end_month,
            severity=template.get('metadata', {}).get('severity', 0.5),
            public_perception=template.get('metadata', {}).get('public_perception')
        )

        """
        Generate event ID

        Args:
            template_id: Template ID
            current_month: Current month
            province_id: Province ID

        Returns:
            Event ID
        """
        if province_id:
            return f"{template_id}_{current_month}_{province_id}_{random.randint(100, 999)}"
        else:
            return f"{template_id}_{current_month}_national_{random.randint(100, 999)}"

    def recalculate_event_probability(self,
                                    game_state: Dict[str, Any],
                                    recent_events: List[Event]) -> float:
        """
        Recalculate event probability based on game state

        Considerations:
        - Treasury status
        - Province stability
        - Recent event count (to avoid event clustering)

        Args:
            game_state: Game state
            recent_events: List of recent events

        Returns:
            Adjusted event probability
        """
        base_probability = self.event_probability

        # Adjust based on treasury
        treasury = game_state.get('treasury', 1000)
        if treasury < 200:
            # Low treasury, increase event probability (economic crisis, social unrest, etc.)
            base_probability *= 1.5
        elif treasury > 2000:
            # High treasury, reduce negative event probability
            base_probability *= 0.8

        # Adjust based on recent event count
        recent_event_count = len(recent_events)
        if recent_event_count > 5:
            # Too many recent events, reduce probability to avoid event clustering
            base_probability *= 0.5

        return min(base_probability, 1.0)
