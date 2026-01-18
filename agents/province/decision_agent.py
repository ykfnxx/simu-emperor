"""
DecisionAgent - Second stage in Province Agent pipeline

Responsibilities:
- Receive PerceptionContext and player instructions
- Evaluate instruction feasibility
- Select behavior types based on context
- Determine behavior parameters
- Validate parameters
- Assess risks
"""

import random
from typing import List, Dict, Any, Optional
from agents.base import BaseAgent
from agents.province.models import (
    PerceptionContext, PlayerInstruction, BehaviorDefinition,
    InstructionEvaluation, Decision, BehaviorType, RiskLevel,
    InstructionStatus
)
from agents.province.behaviors import (
    get_behavior_template, validate_behavior_parameters,
    calculate_behavior_cost, calculate_behavior_effect,
    list_available_behaviors
)


class DecisionAgent(BaseAgent):
    """
    DecisionAgent - Second stage in Province Agent pipeline

    Responsible for:
    - Evaluating player instructions
    - Selecting autonomous behaviors when no instruction
    - Determining behavior parameters
    - Validating and assessing risks
    """

    def __init__(self, agent_id: str, config: Dict[str, Any]):
        """
        Initialize DecisionAgent

        Args:
            agent_id: Unique agent identifier
            config: Configuration dict with llm_config
        """
        super().__init__(agent_id, config)
        self.province_id = config.get('province_id')

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize agent"""
        pass

    async def on_month_start(self, game_state: Dict[str, Any], provinces: List[Dict[str, Any]]) -> None:
        """Called at month start"""
        pass

    async def take_action(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute action"""
        return None

    def get_state(self) -> Dict[str, Any]:
        """Get agent state"""
        return {
            'agent_id': self.agent_id,
            'province_id': self.province_id,
            'mode': self.mode.value
        }

    # ========== Main Decision Method ==========

    async def make_decision(
        self,
        perception: PerceptionContext,
        instruction: Optional[PlayerInstruction],
        province_state: Dict[str, Any]
    ) -> Decision:
        """
        Main decision entry point

        Args:
            perception: PerceptionContext from PerceptionAgent
            instruction: Optional player instruction
            province_state: Current province state

        Returns:
            Decision with selected behaviors
        """
        behaviors = []
        in_response_to = instruction.instruction_id if instruction else None
        reasoning_parts = []

        # Step 1: Evaluate instruction if present
        if instruction:
            evaluation = await self._evaluate_instruction(instruction, perception, province_state)

            if evaluation.is_feasible:
                # Create behaviors for instruction
                instruction_behaviors = await self._create_behaviors_for_instruction(
                    instruction, perception, province_state
                )
                behaviors.extend(instruction_behaviors)
                reasoning_parts.append(f"Executing instruction: {instruction.instruction_type}")
            else:
                # Instruction not feasible, select autonomous behaviors
                reasoning_parts.append(f"Instruction not feasible: {evaluation.constraints}")
                autonomous_behaviors = await self._select_autonomous_behaviors(
                    perception, province_state
                )
                behaviors.extend(autonomous_behaviors)
        else:
            # No instruction, select autonomous behaviors
            autonomous_behaviors = await self._select_autonomous_behaviors(
                perception, province_state
            )
            behaviors.extend(autonomous_behaviors)
            reasoning_parts.append("Autonomous decision based on province status")

        # Step 2: Validate behavior parameters
        valid_behaviors = []
        for behavior in behaviors:
            is_valid, error_msg = validate_behavior_parameters(
                behavior.behavior_type,
                behavior.parameters
            )
            behavior.is_valid = is_valid
            behavior.validation_error = error_msg
            if is_valid:
                valid_behaviors.append(behavior)

        # Step 3: Assess overall risk
        risk_assessment = await self._assess_overall_risk(
            valid_behaviors, perception, province_state
        )

        # Step 4: Generate reasoning
        reasoning = ". ".join(reasoning_parts)

        # Step 5: Calculate estimated effects
        estimated_effects = self._calculate_estimated_effects(
            valid_behaviors, province_state
        )

        return Decision(
            province_id=perception.province_id,
            month=perception.current_month,
            year=perception.current_year,
            behaviors=valid_behaviors,
            in_response_to_instruction=in_response_to,
            reasoning=reasoning,
            risk_level=risk_assessment,
            estimated_effects=estimated_effects
        )

    # ========== Instruction Evaluation ==========

    async def _evaluate_instruction(
        self,
        instruction: PlayerInstruction,
        perception: PerceptionContext,
        province_state: Dict[str, Any]
    ) -> InstructionEvaluation:
        """Evaluate if instruction is feasible"""
        # Check if instruction type is supported
        behavior_type = self._instruction_to_behavior_type(instruction.instruction_type)
        if behavior_type is None:
            return InstructionEvaluation(
                is_feasible=False,
                confidence=0.0,
                constraints=[f"Unsupported instruction type: {instruction.instruction_type}"],
                required_resources={},
                expected_outcome=None,
                risk_assessment=RiskLevel.HIGH
            )

        # Get behavior template
        template = get_behavior_template(behavior_type)
        if template is None:
            return InstructionEvaluation(
                is_feasible=False,
                confidence=0.0,
                constraints=["Behavior template not found"],
                required_resources={},
                expected_outcome=None,
                risk_assessment=RiskLevel.HIGH
            )

        # Validate parameters
        params = instruction.parameters or template.default_parameters
        is_valid, error_msg = validate_behavior_parameters(behavior_type, params)

        if not is_valid:
            return InstructionEvaluation(
                is_feasible=False,
                confidence=0.0,
                constraints=[error_msg],
                required_resources={},
                expected_outcome=None,
                risk_assessment=RiskLevel.HIGH
            )

        # Check resource constraints
        cost = calculate_behavior_cost(behavior_type, params)
        current_surplus = province_state.get('actual_surplus', 0)

        if cost > current_surplus:
            return InstructionEvaluation(
                is_feasible=False,
                confidence=0.0,
                constraints=[f"Insufficient surplus: need {cost}, have {current_surplus}"],
                required_resources={'surplus': cost},
                expected_outcome=None,
                risk_assessment=RiskLevel.HIGH
            )

        # Check loyalty constraints for risky behaviors
        if behavior_type in [BehaviorType.CORRUPTION_CRACKDOWN, BehaviorType.AUSTERITY_MEASURE]:
            if perception.recent_data.loyalty < 30:
                return InstructionEvaluation(
                    is_feasible=False,
                    confidence=0.0,
                    constraints=["Loyalty too low for this action"],
                    required_resources={},
                    expected_outcome=None,
                    risk_assessment=RiskLevel.HIGH
                )

        # Instruction is feasible
        return InstructionEvaluation(
            is_feasible=True,
            confidence=0.8,
            constraints=[],
            required_resources={'surplus': cost},
            expected_outcome=f"Execute {behavior_type.value}",
            risk_assessment=RiskLevel.LOW
        )

    def _instruction_to_behavior_type(self, instruction_type: str) -> Optional[BehaviorType]:
        """Convert instruction type to behavior type"""
        mapping = {
            'raise_tax': BehaviorType.TAX_ADJUSTMENT,
            'lower_tax': BehaviorType.TAX_ADJUSTMENT,
            'invest_infrastructure': BehaviorType.INFRASTRUCTURE_INVESTMENT,
            'loyalty_campaign': BehaviorType.LOYALTY_CAMPAIGN,
            'stability_measure': BehaviorType.STABILITY_MEASURE,
            'emergency_relief': BehaviorType.EMERGENCY_RELIEF,
            'corruption_crackdown': BehaviorType.CORRUPTION_CRACKDOWN,
            'economic_stimulus': BehaviorType.ECONOMIC_STIMULUS,
            'austerity': BehaviorType.AUSTERITY_MEASURE
        }
        return mapping.get(instruction_type)

    async def _create_behaviors_for_instruction(
        self,
        instruction: PlayerInstruction,
        perception: PerceptionContext,
        province_state: Dict[str, Any]
    ) -> List[BehaviorDefinition]:
        """Create behaviors to execute instruction"""
        behavior_type = self._instruction_to_behavior_type(instruction.instruction_type)
        if behavior_type is None:
            return []

        # Get template and parameters
        template = get_behavior_template(behavior_type)
        if template is None:
            return []

        params = instruction.parameters or template.default_parameters

        # Special handling for tax adjustments
        if instruction.instruction_type == 'lower_tax':
            params = params.copy()
            params['rate_change'] = -abs(params.get('rate_change', 0.05))

        # Create primary behavior
        primary_behavior = BehaviorDefinition(
            behavior_type=behavior_type,
            behavior_name=template.name,
            parameters=params,
            reasoning=f"Executing player instruction: {instruction.instruction_type}"
        )

        behaviors = [primary_behavior]

        # Add supporting behaviors if needed
        if behavior_type == BehaviorType.CORRUPTION_CRACKDOWN:
            # Add stability measure to mitigate unrest
            if perception.recent_data.stability < 50:
                stability_template = get_behavior_template(BehaviorType.STABILITY_MEASURE)
                behaviors.append(BehaviorDefinition(
                    behavior_type=BehaviorType.STABILITY_MEASURE,
                    behavior_name="Stability Measure",
                    parameters={'intensity': 1.0, 'duration': 6},
                    reasoning="Supporting measure to maintain stability during crackdown"
                ))

        elif behavior_type == BehaviorType.AUSTERITY_MEASURE:
            # Add loyalty campaign to mitigate displeasure
            if perception.recent_data.loyalty < 50:
                loyalty_template = get_behavior_template(BehaviorType.LOYALTY_CAMPAIGN)
                behaviors.append(BehaviorDefinition(
                    behavior_type=BehaviorType.LOYALTY_CAMPAIGN,
                    behavior_name="Loyalty Campaign",
                    parameters={'intensity': 0.8, 'duration': 6},
                    reasoning="Mitigate loyalty loss from austerity measures"
                ))

        return behaviors

    async def _select_autonomous_behaviors(
        self,
        perception: PerceptionContext,
        province_state: Dict[str, Any]
    ) -> List[BehaviorDefinition]:
        """Select behaviors based on autonomous decision making"""
        behaviors = []
        recent_data = perception.recent_data
        trends = perception.trends

        # Priority 1: Handle critical risks
        if recent_data.loyalty < 30:
            # Crisis: Very low loyalty
            behaviors.append(BehaviorDefinition(
                behavior_type=BehaviorType.EMERGENCY_RELIEF,
                behavior_name="Emergency Relief",
                parameters={'amount': 150, 'target': 0},
                reasoning="Emergency response to very low loyalty"
            ))

        elif recent_data.stability < 30:
            # Crisis: Very low stability
            behaviors.append(BehaviorDefinition(
                behavior_type=BehaviorType.STABILITY_MEASURE,
                behavior_name="Stability Measure",
                parameters={'intensity': 1.5, 'duration': 6},
                reasoning="Emergency response to very low stability"
            ))

        # Priority 2: Address declining trends
        elif trends.loyalty_trend.value == "decreasing":
            behaviors.append(BehaviorDefinition(
                behavior_type=BehaviorType.LOYALTY_CAMPAIGN,
                behavior_name="Loyalty Campaign",
                parameters={'intensity': 1.0, 'duration': 6},
                reasoning="Counter declining loyalty trend"
            ))

        elif trends.income_trend.value == "decreasing" and recent_data.actual_surplus > 100:
            # Has surplus, can invest
            behaviors.append(BehaviorDefinition(
                behavior_type=BehaviorType.ECONOMIC_STIMULUS,
                behavior_name="Economic Stimulus",
                parameters={'amount': 150, 'duration': 12},
                reasoning="Counter declining income trend"
            ))

        # Priority 3: Capitalize on opportunities
        elif recent_data.actual_surplus > 300 and recent_data.loyalty > 60:
            # Good conditions, invest in future
            behaviors.append(BehaviorDefinition(
                behavior_type=BehaviorType.INFRASTRUCTURE_INVESTMENT,
                behavior_name="Infrastructure Investment",
                parameters={'amount': 200, 'duration': 12},
                reasoning="Invest surplus in development"
            ))

        elif trends.income_trend.value == "increasing" and recent_data.actual_surplus > 200:
            # Growing economy, consider tax adjustment
            behaviors.append(BehaviorDefinition(
                behavior_type=BehaviorType.TAX_ADJUSTMENT,
                behavior_name="Tax Adjustment",
                parameters={'rate_change': 0.05, 'duration': 6},
                reasoning="Capitalize on growth with moderate tax increase"
            ))

        # Priority 4: Default maintenance
        elif len(behaviors) == 0:
            # No urgent issues, maintenance behavior
            if recent_data.loyalty < 60:
                behaviors.append(BehaviorDefinition(
                    behavior_type=BehaviorType.LOYALTY_CAMPAIGN,
                    behavior_name="Loyalty Campaign",
                    parameters={'intensity': 0.7, 'duration': 6},
                    reasoning="Maintenance: Improve loyalty"
                ))
            else:
                behaviors.append(BehaviorDefinition(
                    behavior_type=BehaviorType.INFRASTRUCTURE_INVESTMENT,
                    behavior_name="Infrastructure Investment",
                    parameters={'amount': 100, 'duration': 12},
                    reasoning="Maintenance: Invest in development"
                ))

        return behaviors

    async def _assess_overall_risk(
        self,
        behaviors: List[BehaviorDefinition],
        perception: PerceptionContext,
        province_state: Dict[str, Any]
    ) -> RiskLevel:
        """Assess overall risk level of planned behaviors"""
        if not behaviors:
            return RiskLevel.LOW

        risk_score = 0

        # Check behavior types
        for behavior in behaviors:
            if behavior.behavior_type in [BehaviorType.CORRUPTION_CRACKDOWN, BehaviorType.AUSTERITY_MEASURE]:
                risk_score += 2
            elif behavior.behavior_type in [BehaviorType.TAX_ADJUSTMENT]:
                params = behavior.parameters
                rate_change = params.get('rate_change', 0)
                if rate_change > 0.10:  # Large tax increase
                    risk_score += 2
                elif rate_change > 0.05:
                    risk_score += 1

        # Check current conditions
        if perception.recent_data.loyalty < 40:
            risk_score += 2
        elif perception.recent_data.loyalty < 50:
            risk_score += 1

        if perception.recent_data.stability < 40:
            risk_score += 2

        # Determine risk level
        if risk_score >= 5:
            return RiskLevel.HIGH
        elif risk_score >= 2:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _calculate_estimated_effects(
        self,
        behaviors: List[BehaviorDefinition],
        province_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate estimated total effects of all behaviors"""
        total_effects = {
            'income_change': 0.0,
            'expenditure_change': 0.0,
            'loyalty_change': 0.0,
            'stability_change': 0.0,
            'development_change': 0.0,
            'total_cost': 0.0
        }

        for behavior in behaviors:
            # Calculate cost
            cost = calculate_behavior_cost(behavior.behavior_type, behavior.parameters)
            total_effects['total_cost'] += cost

            # Calculate effects
            effect = calculate_behavior_effect(behavior.behavior_type, behavior.parameters, province_state)

            total_effects['income_change'] += effect.income_change
            total_effects['expenditure_change'] += effect.expenditure_change
            total_effects['loyalty_change'] += effect.loyalty_change
            total_effects['stability_change'] += effect.stability_change
            total_effects['development_change'] += effect.development_change

        return total_effects

    # ========== Abstract Method Implementations ==========

    async def _mock_llm_response(self, response_model) -> Any:
        """Generate mock LLM response"""
        return None  # Not used in DecisionAgent

    async def _mock_llm_text_response(self, prompt: str) -> str:
        """Generate mock text response"""
        return "Decision made based on province analysis."
