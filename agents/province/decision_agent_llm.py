"""
LLM-driven DecisionAgent - Enhanced decision making with AI

Responsibilities:
- LLM-powered instruction evaluation with multi-dimensional analysis
- Intelligent behavior selection based on contextual understanding
- Risk assessment with chain reaction prediction
- Decision-maker vs officer interaction simulation
- Structured decision output compatible with existing interfaces
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from agents.base import BaseAgent, AgentMode
from agents.province.models import (
    PerceptionContext, PlayerInstruction, BehaviorDefinition,
    InstructionEvaluation, Decision, BehaviorType, RiskLevel,
    InstructionStatus, TrendDirection
)
from agents.province.behaviors import (
    get_behavior_template, validate_behavior_parameters,
    calculate_behavior_cost, calculate_behavior_effect,
    list_available_behaviors
)
from pydantic import BaseModel, Field


class DecisionMode(str, Enum):
    """Decision operation modes"""
    RULE_BASED = "rule_based"  # Original rule-based logic
    LLM_DRIVEN = "llm_assisted"  # Pure LLM decision making (maps to llm_assisted)
    HYBRID = "hybrid"  # LLM + rule validation


class InteractionRound(str, Enum):
    """Decision interaction rounds"""
    INITIAL = "initial"
    OFFICER_FEEDBACK = "officer_feedback"
    FINAL_ADJUSTMENT = "final_adjustment"


class LLMDecisionInput(BaseModel):
    """Input for LLM decision making"""
    perception_context: Dict[str, Any]
    player_instruction: Optional[Dict[str, Any]] = None
    province_state: Dict[str, Any]
    available_behaviors: List[Dict[str, Any]]
    current_season: str
    risk_tolerance: str = "moderate"
    interaction_round: InteractionRound = InteractionRound.INITIAL


class LLMBehaviorChoice(BaseModel):
    """LLM behavior choice with reasoning"""
    behavior_type: str
    parameters: Dict[str, Any]
    reasoning: str
    risk_level: str
    confidence: float
    expected_outcomes: Dict[str, float]
    alternative_behaviors: List[str] = Field(default_factory=list)


class LLMDecisionOutput(BaseModel):
    """LLM structured decision output"""
    reasoning: str
    primary_behaviors: List[LLMBehaviorChoice]
    supporting_behaviors: List[LLMBehaviorChoice] = Field(default_factory=list)
    overall_risk_level: str
    risk_factors: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    confidence_score: float
    interaction_notes: Optional[str] = None


class OfficerFeedback(BaseModel):
    """Officer feedback on decision feasibility"""
    feasibility_assessment: str
    implementation_challenges: List[str] = Field(default_factory=list)
    resource_requirements: Dict[str, Any] = Field(default_factory=dict)
    timeline_concerns: List[str] = Field(default_factory=list)
    political_implications: List[str] = Field(default_factory=list)
    alternative_suggestions: List[Dict[str, Any]] = Field(default_factory=list)
    overall_recommendation: str


class EnhancedDecisionAgent(BaseAgent):
    """
    Enhanced DecisionAgent with LLM-driven decision making
    
    Features:
    - LLM-powered intelligent decision making
    - Multi-round decision refinement
    - Contextual behavior selection
    - Advanced risk assessment
    - Backward compatibility with existing interface
    """

    def __init__(self, agent_id: str, config: Dict[str, Any]):
        """
        Initialize Enhanced DecisionAgent
        
        Args:
            agent_id: Unique agent identifier
            config: Configuration dict with llm_config, mode, etc.
        """
        # Store decision mode before calling super
        self.decision_mode = DecisionMode(config.get('mode', 'rule_based'))
        self.province_id = config.get('province_id')
        self.interaction_rounds = config.get('interaction_rounds', 1)
        self.risk_tolerance = config.get('risk_tolerance', 'moderate')
        
        # Create modified config for BaseAgent
        base_config = config.copy()
        # Map our decision modes to BaseAgent's AgentMode
        if self.decision_mode == DecisionMode.RULE_BASED:
            base_config['mode'] = 'rule_based'
        else:
            base_config['mode'] = 'llm_assisted'  # Both LLM_DRIVEN and HYBRID use LLM_ASSISTED
        
        super().__init__(agent_id, base_config)
        self.interaction_rounds = config.get('interaction_rounds', 1)
        self.risk_tolerance = config.get('risk_tolerance', 'moderate')
        
        # Fallback to rule-based agent for backward compatibility
        self.rule_based_agent = None
        if self.decision_mode != DecisionMode.LLM_DRIVEN:
            from agents.province.decision_agent import DecisionAgent
            # Use rule-based config for the fallback agent
            rule_based_config = config.copy()
            rule_based_config['mode'] = 'rule_based'
            self.rule_based_agent = DecisionAgent(agent_id, rule_based_config)

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize agent"""
        if self.rule_based_agent:
            await self.rule_based_agent.initialize(config)

    async def on_month_start(self, game_state: Dict[str, Any], provinces: List[Dict[str, Any]]) -> None:
        """Called at month start"""
        if self.rule_based_agent:
            await self.rule_based_agent.on_month_start(game_state, provinces)

    async def take_action(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute action"""
        if self.rule_based_agent:
            return await self.rule_based_agent.take_action(context)
        return None

    def get_state(self) -> Dict[str, Any]:
        """Get agent state"""
        return {
            'agent_id': self.agent_id,
            'province_id': self.province_id,
            'mode': self.decision_mode.value,
            'interaction_rounds': self.interaction_rounds,
            'risk_tolerance': self.risk_tolerance
        }

    # ========== Main Decision Method ==========

    async def make_decision(
        self,
        perception: PerceptionContext,
        instruction: Optional[PlayerInstruction],
        province_state: Dict[str, Any]
    ) -> Decision:
        """
        Main decision entry point - enhanced with LLM capabilities
        
        Args:
            perception: PerceptionContext from PerceptionAgent
            instruction: Optional player instruction
            province_state: Current province state
            
        Returns:
            Decision with selected behaviors
        """
        # Route to appropriate decision method based on mode
        if self.decision_mode == DecisionMode.RULE_BASED and self.rule_based_agent:
            return await self.rule_based_agent.make_decision(perception, instruction, province_state)
        elif self.decision_mode == DecisionMode.HYBRID:
            return await self._make_hybrid_decision(perception, instruction, province_state)
        else:  # LLM_DRIVEN (llm_assisted)
            return await self._make_llm_driven_decision(perception, instruction, province_state)

    # ========== LLM-Driven Decision Methods ==========

    async def _make_llm_driven_decision(
        self,
        perception: PerceptionContext,
        instruction: Optional[PlayerInstruction],
        province_state: Dict[str, Any]
    ) -> Decision:
        """Make decision using pure LLM approach"""
        try:
            # Step 1: Initial LLM decision
            initial_output = await self._call_llm_for_decision(
                perception, instruction, province_state, InteractionRound.INITIAL
            )
            
            if not initial_output:
                # Fallback to rule-based if LLM fails
                if self.rule_based_agent:
                    return await self.rule_based_agent.make_decision(perception, instruction, province_state)
                else:
                    return self._create_fallback_decision(perception, instruction, "LLM call failed")
            
            # Step 2: Officer feedback (if interaction rounds > 0)
            if self.interaction_rounds > 0:
                officer_feedback = await self._get_officer_feedback(
                    initial_output, perception, province_state
                )
                
                # Step 3: Final adjustment based on feedback
                final_output = await self._call_llm_for_decision(
                    perception, instruction, province_state,
                    InteractionRound.FINAL_ADJUSTMENT,
                    initial_output, officer_feedback
                )
                
                if final_output:
                    return self._convert_llm_output_to_decision(
                        final_output, perception, instruction
                    )
            
            # Return initial decision if no interaction or final failed
            return self._convert_llm_output_to_decision(
                initial_output, perception, instruction
            )
            
        except Exception as e:
            print(f"LLM decision making failed: {e}")
            # Fallback to rule-based
            if self.rule_based_agent:
                return await self.rule_based_agent.make_decision(perception, instruction, province_state)
            else:
                return self._create_fallback_decision(perception, instruction, f"Exception: {str(e)}")

    async def _make_hybrid_decision(
        self,
        perception: PerceptionContext,
        instruction: Optional[PlayerInstruction],
        province_state: Dict[str, Any]
    ) -> Decision:
        """Make decision using hybrid approach (LLM + rules)"""
        # Get LLM suggestion
        llm_output = await self._call_llm_for_decision(
            perception, instruction, province_state, InteractionRound.INITIAL
        )
        
        if llm_output:
            # Convert to behaviors and validate with rules
            behaviors = []
            for llm_behavior in llm_output.primary_behaviors + llm_output.supporting_behaviors:
                # Normalize behavior type string
                normalized_type = self._normalize_behavior_type(llm_behavior.behavior_type)
                if not normalized_type:
                    continue

                behavior_type = BehaviorType(normalized_type)
                
                # Validate with rules
                is_valid, error_msg = validate_behavior_parameters(
                    behavior_type, llm_behavior.parameters
                )
                
                if is_valid:
                    behavior = BehaviorDefinition(
                        behavior_type=behavior_type,
                        behavior_name=llm_behavior.behavior_type.replace('_', ' ').title(),
                        parameters=llm_behavior.parameters,
                        reasoning=llm_behavior.reasoning
                    )
                    behaviors.append(behavior)
            
            # Calculate effects and risk
            estimated_effects = self._calculate_estimated_effects(behaviors, province_state)
            normalized_risk = self._normalize_risk_level(llm_output.overall_risk_level)
            risk_level = RiskLevel(normalized_risk)
            
            return Decision(
                province_id=perception.province_id,
                month=perception.current_month,
                year=perception.current_year,
                behaviors=behaviors,
                in_response_to_instruction=instruction.instruction_id if instruction else None,
                reasoning=llm_output.reasoning,
                risk_level=risk_level,
                estimated_effects=estimated_effects
            )
        else:
            # Fallback to pure rule-based
            if self.rule_based_agent:
                return await self.rule_based_agent.make_decision(perception, instruction, province_state)
            else:
                return self._create_fallback_decision(perception, instruction, "Hybrid decision failed")

    # ========== LLM Interaction Methods ==========

    async def _call_llm_for_decision(
        self,
        perception: PerceptionContext,
        instruction: Optional[PlayerInstruction],
        province_state: Dict[str, Any],
        interaction_round: InteractionRound,
        previous_output: Optional[LLMDecisionOutput] = None,
        officer_feedback: Optional[OfficerFeedback] = None
    ) -> Optional[LLMDecisionOutput]:
        """Call LLM for decision making"""
        
        # Prepare input data
        llm_input = self._prepare_llm_input(
            perception, instruction, province_state, interaction_round,
            previous_output, officer_feedback
        )
        
        # Create system prompt based on interaction round
        system_prompt = self._create_system_prompt(interaction_round)
        
        # Create user prompt
        user_prompt = self._create_user_prompt(llm_input)
        
        try:
            # Call LLM with structured output
            response = await self.call_llm_structured(
                prompt=user_prompt,
                response_model=LLMDecisionOutput,
                system_prompt=system_prompt
            )
            return response
            
        except Exception as e:
            print(f"LLM call failed in {interaction_round}: {e}")
            return None

    def _prepare_llm_input(
        self,
        perception: PerceptionContext,
        instruction: Optional[PlayerInstruction],
        province_state: Dict[str, Any],
        interaction_round: InteractionRound,
        previous_output: Optional[LLMDecisionOutput] = None,
        officer_feedback: Optional[OfficerFeedback] = None
    ) -> LLMDecisionInput:
        """Prepare input data for LLM"""
        
        # Convert perception context to dict
        perception_dict = perception.model_dump()
        
        # Get available behaviors
        available_behaviors = list_available_behaviors()
        
        # Determine current season
        current_season = self._get_season(perception.current_month)
        
        # Prepare instruction data
        instruction_dict = None
        if instruction:
            instruction_dict = instruction.model_dump()
        
        return LLMDecisionInput(
            perception_context=perception_dict,
            player_instruction=instruction_dict,
            province_state=province_state,
            available_behaviors=available_behaviors,
            current_season=current_season,
            risk_tolerance=self.risk_tolerance,
            interaction_round=interaction_round
        )

    def _create_system_prompt(self, interaction_round: InteractionRound) -> str:
        """Create system prompt for LLM"""
        base_prompt = """You are an experienced provincial governor in a grand strategy game, skilled in governance, economics, and political decision-making.

Your responsibilities:
1. Analyze complex provincial situations and make sound decisions
2. Balance multiple objectives: fiscal health, population loyalty, stability, and development
3. Consider long-term consequences and risk mitigation
4. Provide clear reasoning for all decisions"""

        if interaction_round == InteractionRound.INITIAL:
            return base_prompt + """

For this initial decision:
- Analyze the provided data comprehensively
- Consider all available policy options
- Think about timing and implementation challenges
- Assess risks and opportunities
- Make the best decision for provincial welfare"""

        elif interaction_round == InteractionRound.OFFICER_FEEDBACK:
            return base_prompt + """

You are now receiving feedback from your administrative officer about implementation feasibility. Consider:
- Resource and timeline constraints
- Political implications
- Alternative approaches
- Risk mitigation strategies"""

        else:  # FINAL_ADJUSTMENT
            return base_prompt + """

Based on officer feedback, refine your decision:
- Address identified challenges
- Adjust parameters if needed
- Consider alternative approaches
- Ensure implementation feasibility
- Maintain decision quality"""

    def _create_user_prompt(self, llm_input: LLMDecisionInput) -> str:
        """Create detailed user prompt for LLM"""
        recent_data = llm_input.perception_context['recent_data']
        trends = llm_input.perception_context['trends']
        
        prompt = f"""
You are governing {llm_input.perception_context['province_name']} in {llm_input.current_season}.

CURRENT SITUATION:
- Population: {recent_data['population']:,}
- Development Level: {recent_data['development_level']}/10
- Loyalty: {recent_data['loyalty']}/100
- Stability: {recent_data['stability']}/100
- Monthly Income: {recent_data['actual_income']:.0f}
- Monthly Surplus: {recent_data['actual_surplus']:.0f}

TRENDS:
- Income: {trends['income_trend']} ({trends['income_change_rate']:+.1f}%)
- Loyalty: {trends['loyalty_trend']} ({trends['loyalty_change_rate']:+.1f})
- Stability: {trends['stability_trend']} ({trends['stability_change_rate']:+.1f})
- Overall Risk: {trends['risk_level']}

CRITICAL EVENTS: {len(llm_input.perception_context['critical_events'])} active
"""

        if llm_input.player_instruction:
            instruction = llm_input.player_instruction
            prompt += f"""

PLAYER INSTRUCTION:
Type: {instruction['instruction_type']}
Template: {instruction['template_name']}
Parameters: {json.dumps(instruction.get('parameters', {}), indent=2)}
"""

        prompt += f"""

AVAILABLE POLICIES:
"""
        for behavior in llm_input.available_behaviors:
            prompt += f"- {behavior['name']}: {behavior['description']}\n"
            if behavior['parameter_ranges']:
                prompt += f"  Parameters: {json.dumps(behavior['parameter_ranges'])}\n"

        prompt += f"""

DECISION REQUIREMENTS:
1. Select 1-3 primary behaviors to implement
2. Choose appropriate parameters within valid ranges
3. Provide clear reasoning for each choice
4. Assess risk level (low/medium/high)
5. Estimate expected outcomes
6. Consider alternative behaviors

RISK TOLERANCE: {llm_input.risk_tolerance}

Provide your decision in the specified JSON format with:
- Comprehensive reasoning
- Selected behaviors with parameters
- Risk assessment
- Expected outcomes for key metrics"""

        return prompt

    async def _get_officer_feedback(
        self,
        initial_decision: LLMDecisionOutput,
        perception: PerceptionContext,
        province_state: Dict[str, Any]
    ) -> OfficerFeedback:
        """Get officer feedback on decision feasibility"""
        
        # Create feedback prompt
        feedback_prompt = f"""
As an administrative officer, provide feasibility feedback on the governor's proposed decision:

PROPOSED DECISION:
{initial_decision.reasoning}

PRIMARY BEHAVIORS:
"""
        for behavior in initial_decision.primary_behaviors:
            feedback_prompt += f"- {behavior.behavior_type}: {behavior.reasoning}\n"
            feedback_prompt += f"  Risk: {behavior.risk_level}, Confidence: {behavior.confidence:.1f}\n"

        feedback_prompt += f"""

CURRENT RESOURCES:
- Available Surplus: {province_state.get('actual_surplus', 0):.0f}
- Population Mood: {perception.recent_data.loyalty}/100
- Administrative Capacity: {perception.recent_data.stability}/100

Provide feedback on:
1. Implementation feasibility
2. Resource requirements
3. Timeline concerns
4. Political implications
5. Alternative suggestions
6. Overall recommendation

Be specific and practical in your assessment."""

        system_prompt = """You are an experienced administrative officer providing practical feedback on policy implementation. Focus on feasibility, resource requirements, and potential challenges."""

        feedback_data = await self.call_llm_structured(
            prompt=feedback_prompt,
            response_model=OfficerFeedback,
            system_prompt=system_prompt
        )
        
        if not feedback_data:
            # Return default feedback
            return OfficerFeedback(
                feasibility_assessment="Proposed decision appears feasible",
                overall_recommendation="Proceed with implementation"
            )
        
        return feedback_data

    # ========== Conversion Methods ==========

    def _normalize_risk_level(self, risk_level_str: str) -> str:
        """Normalize LLM risk level string to enum format

        Examples:
            "LOW" -> "low"
            "Medium" -> "medium"
            "high" -> "high"
        """
        if not risk_level_str:
            return "low"

        return risk_level_str.lower()

    def _normalize_behavior_type(self, behavior_type_str: str) -> Optional[str]:
        """Normalize LLM behavior type string to enum format

        Examples:
            "Loyalty Campaign" -> "loyalty_campaign"
            "Infrastructure Investment" -> "infrastructure_investment"
            "loyalty_campaign" -> "loyalty_campaign" (already normalized)
        """
        if not behavior_type_str:
            return None

        # If already in correct format (lowercase with underscores)
        if '_' in behavior_type_str and behavior_type_str.islower():
            return behavior_type_str

        # Convert from title case or mixed case to lowercase with underscores
        # "Loyalty Campaign" -> "loyalty_campaign"
        normalized = behavior_type_str.lower().replace(' ', '_').replace('-', '_')

        # Map common variations to correct enum values
        mapping = {
            'loyaltycampaign': 'loyalty_campaign',
            'stabilitymeasure': 'stability_measure',
            'emergencyrelief': 'emergency_relief',
            'infrastructureinvestment': 'infrastructure_investment',
            'taxadjustment': 'tax_adjustment',
            'corruptioncrackdown': 'corruption_crackdown',
            'economicstimulus': 'economic_stimulus',
            'austeritymeasure': 'austerity_measure'
        }

        return mapping.get(normalized, normalized)

    def _convert_llm_output_to_decision(
        self,
        llm_output: LLMDecisionOutput,
        perception: PerceptionContext,
        instruction: Optional[PlayerInstruction]
    ) -> Decision:
        """Convert LLM output to Decision model"""

        behaviors = []

        # Convert primary behaviors
        for llm_behavior in llm_output.primary_behaviors:
            try:
                # Normalize behavior type string
                normalized_type = self._normalize_behavior_type(llm_behavior.behavior_type)
                if not normalized_type:
                    print(f"Warning: Empty behavior type from LLM")
                    continue

                behavior_type = BehaviorType(normalized_type)
                behavior = BehaviorDefinition(
                    behavior_type=behavior_type,
                    behavior_name=llm_behavior.behavior_type.replace('_', ' ').title(),
                    parameters=llm_behavior.parameters,
                    reasoning=llm_behavior.reasoning,
                    is_valid=True
                )
                behaviors.append(behavior)
            except ValueError:
                print(f"Warning: Unknown behavior type {llm_behavior.behavior_type}")
                continue
        
        # Convert supporting behaviors
        for llm_behavior in llm_output.supporting_behaviors:
            try:
                # Normalize behavior type string
                normalized_type = self._normalize_behavior_type(llm_behavior.behavior_type)
                if not normalized_type:
                    print(f"Warning: Empty behavior type from LLM")
                    continue

                behavior_type = BehaviorType(normalized_type)
                behavior = BehaviorDefinition(
                    behavior_type=behavior_type,
                    behavior_name=llm_behavior.behavior_type.replace('_', ' ').title(),
                    parameters=llm_behavior.parameters,
                    reasoning=llm_behavior.reasoning,
                    is_valid=True
                )
                behaviors.append(behavior)
            except ValueError:
                print(f"Warning: Unknown behavior type {llm_behavior.behavior_type}")
                continue
        
        # Validate behaviors
        valid_behaviors = []
        for behavior in behaviors:
            is_valid, error_msg = validate_behavior_parameters(
                behavior.behavior_type, behavior.parameters
            )
            behavior.is_valid = is_valid
            behavior.validation_error = error_msg
            if is_valid:
                valid_behaviors.append(behavior)
        
        # Calculate estimated effects
        province_state = {
            'actual_income': perception.recent_data.actual_income,
            'actual_surplus': perception.recent_data.actual_surplus
        }
        estimated_effects = self._calculate_estimated_effects(valid_behaviors, province_state)

        # Normalize risk level
        normalized_risk = self._normalize_risk_level(llm_output.overall_risk_level)

        return Decision(
            province_id=perception.province_id,
            month=perception.current_month,
            year=perception.current_year,
            behaviors=valid_behaviors,
            in_response_to_instruction=instruction.instruction_id if instruction else None,
            reasoning=llm_output.reasoning,
            risk_level=RiskLevel(normalized_risk),
            estimated_effects=estimated_effects
        )

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

    def _create_fallback_decision(
        self,
        perception: PerceptionContext,
        instruction: Optional[PlayerInstruction],
        reason: str
    ) -> Decision:
        """Create a safe fallback decision"""
        return Decision(
            province_id=perception.province_id,
            month=perception.current_month,
            year=perception.current_year,
            behaviors=[],  # No behaviors in fallback
            in_response_to_instruction=instruction.instruction_id if instruction else None,
            reasoning=f"Fallback decision due to: {reason}",
            risk_level=RiskLevel.LOW,
            estimated_effects={}
        )

    # ========== Utility Methods ==========

    def _get_season(self, month: int) -> str:
        """Get season from month"""
        if month in [12, 1, 2]:
            return "Winter"
        elif month in [3, 4, 5]:
            return "Spring"
        elif month in [6, 7, 8]:
            return "Summer"
        else:
            return "Autumn"

    # ========== Abstract Method Implementations ==========

    async def _mock_llm_response(self, response_model) -> Any:
        """Generate mock LLM response for structured output"""
        if response_model == LLMDecisionOutput:
            return LLMDecisionOutput(
                reasoning="Based on provincial analysis, implementing moderate infrastructure investment and loyalty campaign to address declining trends.",
                primary_behaviors=[
                    LLMBehaviorChoice(
                        behavior_type="infrastructure_investment",
                        parameters={"amount": 150, "duration": 12},
                        reasoning="Address infrastructure needs to support development",
                        risk_level="low",
                        confidence=0.8,
                        expected_outcomes={"development_change": 0.75, "loyalty_change": 3.0}
                    ),
                    LLMBehaviorChoice(
                        behavior_type="loyalty_campaign",
                        parameters={"intensity": 1.0, "duration": 6},
                        reasoning="Improve population loyalty to ensure stability",
                        risk_level="low",
                        confidence=0.7,
                        expected_outcomes={"loyalty_change": 8.0, "stability_change": 3.0}
                    )
                ],
                overall_risk_level="low",
                risk_factors=[],
                opportunities=["Infrastructure development will boost future income", "Loyalty improvement enables future reforms"],
                confidence_score=0.75
            )
        elif response_model == OfficerFeedback:
            return OfficerFeedback(
                feasibility_assessment="Proposed infrastructure investment and loyalty campaign are feasible",
                implementation_challenges=["Requires coordination between departments", "Timeline may be tight for loyalty campaign"],
                resource_requirements={"surplus": 200, "administrative_capacity": 0.8},
                timeline_concerns=["Loyalty campaign should show results within 3 months"],
                political_implications=["Infrastructure investment will be popular", "Loyalty campaign timing is good"],
                alternative_suggestions=[],
                overall_recommendation="Proceed with implementation as planned"
            )
        return None

    async def _mock_llm_text_response(self, prompt: str) -> str:
        """Generate mock text response"""
        return "Decision made based on comprehensive provincial analysis and administrative feedback."