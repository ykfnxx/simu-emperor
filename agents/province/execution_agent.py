"""
ExecutionAgent - Third stage in Province Agent pipeline

Responsibilities:
- Execute behavior definitions
- Calculate behavior effects
- Modify province attributes
- Generate events
- Generate monthly reports
- Record behavior history
"""

import uuid
from typing import List, Dict, Any
from agents.base import BaseAgent
from agents.province.models import (
    Decision, ExecutedBehavior, BehaviorEvent, ExecutionResult,
    BehaviorEffect
)
from agents.province.behaviors import calculate_behavior_effect


class ExecutionAgent(BaseAgent):
    """
    ExecutionAgent - Third stage in Province Agent pipeline

    Responsible for:
    - Executing behaviors from Decision
    - Calculating and applying effects
    - Generating events
    - Creating monthly reports
    """

    def __init__(self, agent_id: str, config: Dict[str, Any]):
        """
        Initialize ExecutionAgent

        Args:
            agent_id: Unique agent identifier
            config: Configuration dict
        """
        super().__init__(agent_id, config)
        self.province_id = config.get('province_id')

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize agent"""
        pass

    async def on_month_start(self, game_state: Dict[str, Any], provinces: List[Dict[str, Any]]) -> None:
        """Called at month start"""
        pass

    async def take_action(self, context: Dict[str, Any]) -> Any:
        """Execute action"""
        return None

    def get_state(self) -> Dict[str, Any]:
        """Get agent state"""
        return {
            'agent_id': self.agent_id,
            'province_id': self.province_id
        }

    # ========== Main Execution Method ==========

    async def execute(
        self,
        decision: Decision,
        province_state: Dict[str, Any],
        month: int,
        year: int
    ) -> ExecutionResult:
        """
        Main execution entry point

        Args:
            decision: Decision from DecisionAgent
            province_state: Current province state (will be modified)
            month: Current month
            year: Current year

        Returns:
            ExecutionResult with executed behaviors and generated events
        """
        executed_behaviors = []
        generated_events = []
        cumulative_effects = BehaviorEffect(
            behavior_type=decision.behaviors[0].behavior_type if decision.behaviors else None,
            behavior_name="Cumulative"
        )

        # Execute each behavior
        for behavior_def in decision.behaviors:
            # Calculate effect
            effect = calculate_behavior_effect(
                behavior_def.behavior_type,
                behavior_def.parameters,
                province_state
            )

            # Apply effect to province state
            self._apply_effect_to_province(effect, province_state)

            # Generate event
            event = self._generate_behavior_event(
                behavior_def, effect, province_state, month, year
            )
            generated_events.append(event)

            # Create executed behavior record
            executed_behavior = ExecutedBehavior(
                behavior_type=behavior_def.behavior_type,
                behavior_name=behavior_def.behavior_name,
                parameters=behavior_def.parameters,
                effects=effect,
                reasoning=behavior_def.reasoning,
                execution_success=True,
                execution_message=f"Successfully executed {behavior_def.behavior_name}"
            )
            executed_behaviors.append(executed_behavior)

            # Accumulate effects
            cumulative_effects.income_change += effect.income_change
            cumulative_effects.expenditure_change += effect.expenditure_change
            cumulative_effects.loyalty_change += effect.loyalty_change
            cumulative_effects.stability_change += effect.stability_change
            cumulative_effects.development_change += effect.development_change
            cumulative_effects.population_change += effect.population_change

            # Merge other effects
            for key, value in effect.other_effects.items():
                if key in cumulative_effects.other_effects:
                    cumulative_effects.other_effects[key] += value
                else:
                    cumulative_effects.other_effects[key] = value

        # Generate execution summary
        execution_summary = self._generate_execution_summary(
            executed_behaviors, cumulative_effects, province_state
        )

        return ExecutionResult(
            province_id=decision.province_id,
            month=month,
            year=year,
            executed_behaviors=executed_behaviors,
            generated_events=generated_events,
            total_effects=cumulative_effects,
            province_state_after=province_state.copy(),
            execution_summary=execution_summary
        )

    def _apply_effect_to_province(self, effect: BehaviorEffect, province_state: Dict[str, Any]) -> None:
        """Apply behavior effect to province state"""
        # Apply income/expenditure changes to actual values
        if 'actual_income' in province_state:
            province_state['actual_income'] += effect.income_change
        if 'actual_expenditure' in province_state:
            province_state['actual_expenditure'] += effect.expenditure_change

        # Apply loyalty change
        if 'loyalty' in province_state:
            province_state['loyalty'] = max(0, min(100, province_state['loyalty'] + effect.loyalty_change))

        # Apply stability change
        if 'stability' in province_state:
            province_state['stability'] = max(0, min(100, province_state['stability'] + effect.stability_change))

        # Apply development change
        if 'development_level' in province_state:
            province_state['development_level'] = max(0, min(10, province_state['development_level'] + effect.development_change))

        # Apply population change
        if 'population' in province_state:
            province_state['population'] = max(0, province_state['population'] + effect.population_change)

        # Store other effects
        if 'other_effects' not in province_state:
            province_state['other_effects'] = {}
        for key, value in effect.other_effects.items():
            if key in province_state['other_effects']:
                province_state['other_effects'][key] += value
            else:
                province_state['other_effects'][key] = value

    def _generate_behavior_event(
        self,
        behavior_def,
        effect: BehaviorEffect,
        province_state: Dict[str, Any],
        month: int,
        year: int
    ) -> BehaviorEvent:
        """Generate event from behavior execution"""
        # Generate event name and description based on behavior type
        event_type = behavior_def.behavior_type.value
        event_name = behavior_def.behavior_name

        # Generate description
        description = self._generate_event_description(behavior_def, effect, province_state)

        # Calculate severity based on impact
        severity = self._calculate_event_severity(effect, province_state)

        # Build effects dict
        effects_dict = {
            'income_change': effect.income_change,
            'expenditure_change': effect.expenditure_change,
            'loyalty_change': effect.loyalty_change,
            'stability_change': effect.stability_change,
            'development_change': effect.development_change
        }

        # Add other effects
        effects_dict.update(effect.other_effects)

        # Determine visibility
        visibility = self._determine_event_visibility(behavior_def, effect)

        return BehaviorEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            name=event_name,
            description=description,
            severity=severity,
            effects=effects_dict,
            visibility=visibility,
            is_agent_generated=True
        )

    def _generate_event_description(
        self,
        behavior_def,
        effect: BehaviorEffect,
        province_state: Dict[str, Any]
    ) -> str:
        """Generate event description"""
        behavior_type = behavior_def.behavior_type.value

        descriptions = {
            'tax_adjustment': f"Tax rates adjusted by {behavior_def.parameters.get('rate_change', 0)*100:+.1f}%",
            'infrastructure_investment': f"Invested {behavior_def.parameters.get('amount', 0)} in infrastructure projects",
            'loyalty_campaign': f"Launched loyalty campaign with intensity {behavior_def.parameters.get('intensity', 1.0):.1f}",
            'stability_measure': f"Implemented stability measures with intensity {behavior_def.parameters.get('intensity', 1.0):.1f}",
            'emergency_relief': f"Distributed {behavior_def.parameters.get('amount', 0)} in emergency relief",
            'corruption_crackdown': f"Launched corruption crackdown with intensity {behavior_def.parameters.get('intensity', 1.0):.1f}",
            'economic_stimulus': f"Injected {behavior_def.parameters.get('amount', 0)} into economy as stimulus",
            'austerity_measure': f"Implemented austerity measures saving {behavior_def.parameters.get('savings_amount', 0)}"
        }

        base_description = descriptions.get(behavior_type, f"Executed {behavior_def.behavior_name}")

        # Add effects summary
        effects_summary = []
        if abs(effect.loyalty_change) > 1:
            effects_summary.append(f"loyalty {effect.loyalty_change:+.1f}")
        if abs(effect.stability_change) > 1:
            effects_summary.append(f"stability {effect.stability_change:+.1f}")
        if abs(effect.income_change) > 10:
            effects_summary.append(f"income {effect.income_change:+.0f}")
        if abs(effect.expenditure_change) > 10:
            effects_summary.append(f"expenditure {effect.expenditure_change:+.0f}")

        if effects_summary:
            return f"{base_description} ({', '.join(effects_summary)})"
        return base_description

    def _calculate_event_severity(
        self,
        effect: BehaviorEffect,
        province_state: Dict[str, Any]
    ) -> float:
        """Calculate event severity based on impact"""
        severity = 0.3  # Base severity

        # Impact magnitude
        impact_magnitude = (
            abs(effect.loyalty_change) / 20.0 +
            abs(effect.stability_change) / 20.0 +
            abs(effect.income_change) / 500.0 +
            abs(effect.expenditure_change) / 500.0
        )

        severity = min(1.0, severity + impact_magnitude)

        # Special cases
        if effect.loyalty_change < -10 or effect.stability_change < -10:
            severity = min(1.0, severity + 0.3)

        return max(0.1, min(1.0, severity))

    def _determine_event_visibility(self, behavior_def, effect: BehaviorEffect) -> str:
        """Determine event visibility level"""
        # Critical actions get higher visibility
        if behavior_def.behavior_type.value in ['corruption_crackdown', 'emergency_relief']:
            return 'public'

        # Significant impacts get higher visibility
        if abs(effect.loyalty_change) > 10 or abs(effect.stability_change) > 10:
            return 'public'

        if abs(effect.income_change) > 200 or abs(effect.expenditure_change) > 200:
            return 'public'

        # Default to provincial
        return 'provincial'

    def _generate_execution_summary(
        self,
        executed_behaviors: List[ExecutedBehavior],
        cumulative_effects: BehaviorEffect,
        province_state: Dict[str, Any]
    ) -> str:
        """Generate execution summary"""
        if not executed_behaviors:
            return "No behaviors executed."

        # Count behaviors by type
        behavior_count = len(executed_behaviors)

        # Build summary
        summary_parts = [
            f"Executed {behavior_count} behavior(s):"
        ]

        # List behaviors
        for behavior in executed_behaviors:
            summary_parts.append(f"  - {behavior.behavior_name}: {behavior.execution_message}")

        # Add net effects
        if abs(cumulative_effects.income_change) > 1 or abs(cumulative_effects.expenditure_change) > 1:
            summary_parts.append(
                f"Net financial impact: income {cumulative_effects.income_change:+.0f}, "
                f"expenditure {cumulative_effects.expenditure_change:+.0f}"
            )

        if abs(cumulative_effects.loyalty_change) > 0.5 or abs(cumulative_effects.stability_change) > 0.5:
            summary_parts.append(
                f"Net social impact: loyalty {cumulative_effects.loyalty_change:+.1f}, "
                f"stability {cumulative_effects.stability_change:+.1f}"
            )

        return "\n".join(summary_parts)

    # ========== Abstract Method Implementations ==========

    async def _mock_llm_response(self, response_model) -> Any:
        """Generate mock LLM response"""
        return None  # Not used in ExecutionAgent

    async def _mock_llm_text_response(self, prompt: str) -> str:
        """Generate mock text response"""
        return "Behaviors executed successfully."
