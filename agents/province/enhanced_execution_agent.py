"""
Enhanced ExecutionAgent - Third stage in Province Agent pipeline with LLM capabilities

Responsibilities:
- Execute behavior definitions with LLM enhancement
- Calculate and optimize behavior effects
- Generate creative, context-aware events
- Provide execution quality assessment
- Support adaptive execution strategies
"""

import uuid
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from agents.base import BaseAgent
from agents.province.models import (
    Decision, ExecutedBehavior, BehaviorEvent, ExecutionResult,
    BehaviorEffect, BehaviorDefinition, BehaviorType
)
from agents.province.enhanced_execution_models import (
    ExecutionMode, ExecutionContext, LLMExecutionInterpretation,
    LLMExecutionInput, CreativeEventOutput, ExecutionQualityReport,
    ExecutionPrediction, OptimizedExecutionSequence, ExecutionPhase,
    ExecutionRecord, HistoricalContext, EnhancedExecutionResult
)
from agents.province.behaviors import calculate_behavior_effect


class EnhancedExecutionAgent(BaseAgent):
    """
    Enhanced ExecutionAgent with LLM capabilities
    
    Supports multiple execution modes:
    - STANDARD: Rule-based execution (original behavior)
    - LLM_ENHANCED: Full LLM-enhanced execution
    - HYBRID: Combination of both approaches
    """

    def __init__(self, agent_id: str, config: Dict[str, Any]):
        """
        Initialize EnhancedExecutionAgent
        
        Args:
            agent_id: Unique agent identifier
            config: Configuration dict with execution mode and settings
        """
        # Handle execution mode - map to BaseAgent mode
        base_config = config.copy()
        execution_mode = base_config.get('execution_mode', 'standard')
        if execution_mode == 'llm_enhanced' or execution_mode == 'hybrid':
            base_config['mode'] = 'llm_assisted'
        else:
            base_config['mode'] = 'rule_based'
        
        super().__init__(agent_id, base_config)
        self.province_id = config.get('province_id')
        self.execution_mode = ExecutionMode(config.get('execution_mode', 'standard'))
        self.llm_config = config.get('llm_config', {})
        self.quality_threshold = config.get('quality_threshold', 0.7)
        self.enable_learning = config.get('enable_learning', True)
        self.execution_history: List[ExecutionRecord] = []
        
        # Initialize logger
        self.logger = logging.getLogger(f"EnhancedExecutionAgent.{agent_id}")
        
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize agent with enhanced configuration"""
        # Load historical execution data if available
        if 'historical_data' in config:
            self._load_historical_data(config['historical_data'])
    
    async def on_month_start(self, game_state: Dict[str, Any], provinces: List[Dict[str, Any]]) -> None:
        """Called at month start - execution agent doesn't need monthly initialization"""
        pass
    
    async def take_action(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute action - execution agent uses specialized execute methods"""
        return None
    
    def get_state(self) -> Dict[str, Any]:
        """Get agent state"""
        return {
            'agent_id': self.agent_id,
            'province_id': self.province_id,
            'execution_mode': self.execution_mode.value,
            'execution_history_count': len(self.execution_history),
            'quality_threshold': self.quality_threshold,
            'enable_learning': self.enable_learning
        }
            
    def _load_historical_data(self, historical_data: List[Dict[str, Any]]) -> None:
        """Load historical execution data for learning"""
        self.execution_history = []
        for record in historical_data:
            try:
                execution_record = ExecutionRecord(**record)
                self.execution_history.append(execution_record)
            except Exception as e:
                self.logger.warning(f"Failed to load historical record: {e}")

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

    async def execute_with_llm(
        self,
        decision: Decision,
        province_state: Dict[str, Any],
        execution_context: Optional[ExecutionContext] = None,
        historical_context: Optional[HistoricalContext] = None
    ) -> EnhancedExecutionResult:
        """
        Execute decision with LLM enhancement
        
        Args:
            decision: Decision from DecisionAgent
            province_state: Current province state (will be modified)
            execution_context: Context for execution
            historical_context: Historical context for learning
            
        Returns:
            EnhancedExecutionResult with quality assessment and insights
        """
        # Use default context if not provided
        if execution_context is None:
            execution_context = self._build_default_execution_context(province_state)
            
        # Get LLM interpretation if in enhanced mode
        interpretation = None
        if self.execution_mode in [ExecutionMode.LLM_ENHANCED, ExecutionMode.HYBRID]:
            interpretation = await self._interpret_execution_with_llm(
                decision, province_state, execution_context, historical_context
            )
            
        # Execute behaviors
        execution_result = await self._execute_behaviors(
            decision, province_state, interpretation, execution_context
        )
        
        # Assess execution quality
        quality_report = await self._assess_execution_quality(
            execution_result, decision, province_state
        )
        
        # Generate predictions for future executions
        prediction = None
        if self.execution_mode in [ExecutionMode.LLM_ENHANCED, ExecutionMode.HYBRID]:
            prediction = await self._predict_execution_outcomes(
                decision, province_state
            )
            
        # Record for learning
        if self.enable_learning:
            await self._record_execution(decision, execution_result, quality_report)
            
        return EnhancedExecutionResult(
            execution_result=execution_result.model_dump(),
            quality_report=quality_report,
            execution_interpretation=interpretation,
            predictive_insights=prediction
        )

    async def _interpret_execution_with_llm(
        self,
        decision: Decision,
        province_state: Dict[str, Any],
        execution_context: ExecutionContext,
        historical_context: Optional[HistoricalContext] = None
    ) -> LLMExecutionInterpretation:
        """
        Use LLM to interpret and optimize execution strategy
        
        Args:
            decision: Decision to execute
            province_state: Current province state
            execution_context: Execution context
            historical_context: Historical context
            
        Returns:
            LLM interpretation of optimal execution strategy
        """
        # Build comprehensive prompt
        prompt = f"""
        You are an experienced provincial administrator executing policy decisions.
        
        PROVINCE STATE:
        - Population: {province_state.get('population', 0):,}
        - Loyalty: {province_state.get('loyalty', 50)}/100
        - Stability: {province_state.get('stability', 50)}/100
        - Monthly Income: {province_state.get('actual_income', 0)}
        - Available Surplus: {province_state.get('actual_surplus', 0)}
        - Development Level: {province_state.get('development_level', 5)}/10
        
        DECISION TO EXECUTE:
        Behaviors: {[b.behavior_type.value for b in decision.behaviors]}
        Risk Level: {decision.risk_level.value}
        Reasoning: {decision.reasoning}
        
        EXECUTION CONTEXT:
        - Season: {execution_context.season}
        - Population Mood: {execution_context.population_mood}
        - Economic Conditions: {execution_context.economic_conditions}
        - Political Stability: {execution_context.political_stability}
        - Recent Events: {', '.join(execution_context.recent_events[-5:])}
        """
        
        if historical_context and historical_context.recent_executions:
            prompt += f"""
        
        HISTORICAL CONTEXT:
        - Recent similar decisions: {len(historical_context.recent_executions)}
        - Average success rate: {sum(r.quality_score for r in historical_context.recent_executions) / len(historical_context.recent_executions):.2f}
        - Key lessons learned: {', '.join(historical_context.lessons_learned[-3:])}
        """
            
        prompt += """
        
        Provide execution interpretation focusing on:
        1. Optimal execution timing and phasing
        2. Resource allocation strategy
        3. Risk mitigation during execution
        4. Expected challenges and solutions
        5. Success metrics and milestones
        6. Adaptation strategies for changing conditions
        
        Return a structured response with:
        - execution_strategy: Overall approach (1-2 sentences)
        - timing_recommendations: List of timing suggestions
        - resource_allocation: Resource allocation strategy dict
        - risk_mitigation: List of risk mitigation measures
        - expected_challenges: List of anticipated challenges
        - success_metrics: List of success measurement criteria
        - confidence_level: Confidence score 0.0-1.0
        - execution_phases: Optional list of execution phases
        """
        
        try:
            return await self.call_llm_structured(prompt, LLMExecutionInterpretation)
        except Exception as e:
            self.logger.error(f"LLM interpretation failed: {e}")
            # Return fallback interpretation
            return LLMExecutionInterpretation(
                execution_strategy="Proceed with standard execution approach",
                timing_recommendations=["Execute promptly", "Monitor results closely"],
                resource_allocation={"primary": "standard_allocation"},
                risk_mitigation=["Monitor province stability", "Prepare contingency plans"],
                expected_challenges=["Potential resistance to change", "Resource constraints"],
                success_metrics=["Maintain stability", "Achieve intended effects"],
                confidence_level=0.6
            )

    async def _execute_behaviors(
        self,
        decision: Decision,
        province_state: Dict[str, Any],
        interpretation: Optional[LLMExecutionInterpretation],
        execution_context: ExecutionContext
    ) -> ExecutionResult:
        """
        Execute behaviors with optional LLM enhancement
        
        Args:
            decision: Decision to execute
            province_state: Province state (will be modified)
            interpretation: Optional LLM interpretation
            execution_context: Execution context
            
        Returns:
            ExecutionResult with executed behaviors and events
        """
        executed_behaviors = []
        generated_events = []
        cumulative_effects = BehaviorEffect(
            behavior_type=decision.behaviors[0].behavior_type if decision.behaviors else None,
            behavior_name="Cumulative"
        )

        # Optimize execution sequence if we have interpretation
        behavior_sequence = decision.behaviors
        if interpretation and interpretation.execution_phases:
            behavior_sequence = await self._optimize_execution_sequence(
                decision.behaviors, interpretation, province_state
            )

        # Execute each behavior
        for behavior_def in behavior_sequence:
            # Calculate base effect
            base_effect = calculate_behavior_effect(
                behavior_def.behavior_type,
                behavior_def.parameters,
                province_state
            )
            
            # Modify effect based on context and interpretation
            enhanced_effect = await self._enhance_behavior_effect(
                base_effect, behavior_def, province_state, execution_context, interpretation
            )

            # Apply effect to province state
            self._apply_effect_to_province(enhanced_effect, province_state)

            # Generate enhanced event
            event = await self._generate_enhanced_event(
                behavior_def, enhanced_effect, province_state, execution_context, interpretation
            )
            generated_events.append(event)

            # Create executed behavior record
            executed_behavior = ExecutedBehavior(
                behavior_type=behavior_def.behavior_type,
                behavior_name=behavior_def.behavior_name,
                parameters=behavior_def.parameters,
                effects=enhanced_effect,
                reasoning=behavior_def.reasoning,
                execution_success=True,
                execution_message=f"Successfully executed {behavior_def.behavior_name} with enhanced effects"
            )
            executed_behaviors.append(executed_behavior)

            # Accumulate effects
            self._accumulate_effects(cumulative_effects, enhanced_effect)

        # Generate enhanced execution summary
        execution_summary = await self._generate_enhanced_execution_summary(
            executed_behaviors, cumulative_effects, province_state, interpretation
        )

        return ExecutionResult(
            province_id=decision.province_id,
            month=decision.month,
            year=decision.year,
            executed_behaviors=executed_behaviors,
            generated_events=generated_events,
            total_effects=cumulative_effects,
            province_state_after=province_state.copy(),
            execution_summary=execution_summary
        )

    async def _enhance_behavior_effect(
        self,
        base_effect: BehaviorEffect,
        behavior_def: BehaviorDefinition,
        province_state: Dict[str, Any],
        execution_context: ExecutionContext,
        interpretation: Optional[LLMExecutionInterpretation]
    ) -> BehaviorEffect:
        """
        Enhance behavior effect based on context and LLM interpretation
        
        Args:
            base_effect: Base calculated effect
            behavior_def: Behavior definition
            province_state: Current province state
            execution_context: Execution context
            interpretation: Optional LLM interpretation
            
        Returns:
            Enhanced BehaviorEffect
        """
        # Start with base effect
        enhanced_effect = base_effect.model_copy()

        # Apply context-based modifications
        enhanced_effect = self._apply_contextual_modifications(
            enhanced_effect, province_state, execution_context
        )
        
        # Apply interpretation-based enhancements
        if interpretation:
            enhanced_effect = self._apply_interpretation_modifications(
                enhanced_effect, interpretation, province_state
            )
            
        return enhanced_effect

    def _apply_contextual_modifications(
        self,
        effect: BehaviorEffect,
        province_state: Dict[str, Any],
        execution_context: ExecutionContext
    ) -> BehaviorEffect:
        """Apply context-based effect modifications"""
        # Seasonal modifications
        if execution_context.season == 'winter':
            # Infrastructure projects are harder in winter
            if effect.behavior_type == BehaviorType.INFRASTRUCTURE_INVESTMENT:
                effect.expenditure_change *= 1.1  # 10% cost increase
                
        # Population mood modifications
        if execution_context.population_mood == 'negative':
            # Negative mood reduces effectiveness of loyalty campaigns
            if effect.behavior_type == BehaviorType.LOYALTY_CAMPAIGN:
                effect.loyalty_change *= 0.8  # 20% reduction
                
        # Economic condition modifications
        if execution_context.economic_conditions == 'crisis':
            # Economic stimulus more effective during crisis
            if effect.behavior_type == BehaviorType.ECONOMIC_STIMULUS:
                effect.income_change *= 1.2  # 20% boost
                effect.development_change *= 1.15  # 15% boost
                
        return effect

    def _apply_interpretation_modifications(
        self,
        effect: BehaviorEffect,
        interpretation: LLMExecutionInterpretation,
        province_state: Dict[str, Any]
    ) -> BehaviorEffect:
        """Apply interpretation-based effect modifications"""
        # Apply confidence-based scaling
        confidence_factor = interpretation.confidence_level
        
        # Scale positive effects with confidence
        if confidence_factor > 0.7:
            effect.loyalty_change *= (0.9 + 0.2 * confidence_factor)
            effect.stability_change *= (0.9 + 0.2 * confidence_factor)
            effect.income_change *= (0.95 + 0.1 * confidence_factor)
            
        # Apply risk mitigation effects
        if interpretation.risk_mitigation:
            # Better risk mitigation improves stability
            stability_bonus = len(interpretation.risk_mitigation) * 0.5
            effect.stability_change += min(stability_bonus, 2.0)
            
        return effect

    async def _generate_enhanced_event(
        self,
        behavior_def: BehaviorDefinition,
        effect: BehaviorEffect,
        province_state: Dict[str, Any],
        execution_context: ExecutionContext,
        interpretation: Optional[LLMExecutionInterpretation]
    ) -> BehaviorEvent:
        """
        Generate enhanced, creative event using LLM
        
        Args:
            behavior_def: Behavior definition
            effect: Calculated effect
            province_state: Province state
            execution_context: Execution context
            interpretation: Optional LLM interpretation
            
        Returns:
            Enhanced BehaviorEvent
        """
        # Use LLM for creative event generation in enhanced mode
        if self.execution_mode in [ExecutionMode.LLM_ENHANCED, ExecutionMode.HYBRID]:
            try:
                return await self._generate_creative_event_with_llm(
                    behavior_def, effect, province_state, execution_context, interpretation
                )
            except Exception as e:
                self.logger.error(f"Creative event generation failed: {e}")
                # Fall back to standard event generation
                
        # Standard event generation (fallback)
        return self._generate_standard_event(behavior_def, effect, province_state)

    async def _generate_creative_event_with_llm(
        self,
        behavior_def: BehaviorDefinition,
        effect: BehaviorEffect,
        province_state: Dict[str, Any],
        execution_context: ExecutionContext,
        interpretation: Optional[LLMExecutionInterpretation]
    ) -> BehaviorEvent:
        """Generate creative event using LLM"""
        prompt = f"""
        Create a detailed event description for this provincial action:
        
        ACTION: {behavior_def.behavior_name}
        PARAMETERS: {json.dumps(behavior_def.parameters, indent=2)}
        EXPECTED EFFECTS: {json.dumps(effect.model_dump(), indent=2)}
        
        PROVINCE CONTEXT:
        - Population: {province_state.get('population', 0):,}
        - Loyalty: {province_state.get('loyalty', 50)}/100
        - Stability: {province_state.get('stability', 50)}/100
        - Development: {province_state.get('development_level', 5)}/10
        - Economic Conditions: {execution_context.economic_conditions}
        - Population Mood: {execution_context.population_mood}
        - Season: {execution_context.season}
        
        EXECUTION CONTEXT:
        - Recent Events: {', '.join(execution_context.recent_events[-3:])}
        - Political Stability: {execution_context.political_stability}
        """
        
        if interpretation:
            prompt += f"""
        
        EXECUTION STRATEGY:
        - Approach: {interpretation.execution_strategy}
        - Key Challenges: {', '.join(interpretation.expected_challenges[:2])}
        - Risk Mitigation: {', '.join(interpretation.risk_mitigation[:2])}
        """
            
        prompt += """
        
        Generate:
        1. A creative event name that captures the essence of this action
        2. A detailed, immersive description that brings the event to life
        3. Appropriate severity (0.1-1.0) based on impact and context
        4. Visibility level (local, provincial, public, national)
        5. Special characteristics that make this event unique
        6. Narrative tone that matches the context (celebratory, concerned, neutral, etc.)
        
        Make it engaging and contextually appropriate. Consider the province's current state,
        recent events, and the broader political/economic climate.
        """
        
        creative_output = await self.call_llm_structured(prompt, CreativeEventOutput)
        
        # Build effects dict
        effects_dict = {
            'income_change': effect.income_change,
            'expenditure_change': effect.expenditure_change,
            'loyalty_change': effect.loyalty_change,
            'stability_change': effect.stability_change,
            'development_change': effect.development_change,
            'population_change': effect.population_change
        }
        effects_dict.update(effect.other_effects)
        
        return BehaviorEvent(
            event_id=str(uuid.uuid4()),
            event_type=behavior_def.behavior_type.value,
            name=creative_output.event_name,
            description=creative_output.description,
            severity=creative_output.severity,
            effects=effects_dict,
            visibility=creative_output.visibility,
            is_agent_generated=True
        )

    def _generate_standard_event(
        self,
        behavior_def: BehaviorDefinition,
        effect: BehaviorEffect,
        province_state: Dict[str, Any]
    ) -> BehaviorEvent:
        """Generate standard event (fallback)"""
        # Use original logic from ExecutionAgent
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
        behavior_def: BehaviorDefinition,
        effect: BehaviorEffect,
        province_state: Dict[str, Any]
    ) -> str:
        """Generate event description (fallback logic)"""
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

    def _determine_event_visibility(self, behavior_def: BehaviorDefinition, effect: BehaviorEffect) -> str:
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

    async def _optimize_execution_sequence(
        self,
        behaviors: List[BehaviorDefinition],
        interpretation: LLMExecutionInterpretation,
        province_state: Dict[str, Any]
    ) -> List[BehaviorDefinition]:
        """Optimize execution sequence based on interpretation"""
        # Simple optimization for now - could be enhanced with dependency analysis
        if not interpretation.execution_phases:
            return behaviors
            
        # For now, return behaviors in original order
        # Future enhancement: reorder based on dependencies and optimal sequencing
        return behaviors

    def _accumulate_effects(self, cumulative: BehaviorEffect, new_effect: BehaviorEffect) -> None:
        """Accumulate effects into cumulative effect"""
        cumulative.income_change += new_effect.income_change
        cumulative.expenditure_change += new_effect.expenditure_change
        cumulative.loyalty_change += new_effect.loyalty_change
        cumulative.stability_change += new_effect.stability_change
        cumulative.development_change += new_effect.development_change
        cumulative.population_change += new_effect.population_change
        
        # Merge other effects
        for key, value in new_effect.other_effects.items():
            if key in cumulative.other_effects:
                cumulative.other_effects[key] += value
            else:
                cumulative.other_effects[key] = value

    async def _generate_enhanced_execution_summary(
        self,
        executed_behaviors: List[ExecutedBehavior],
        cumulative_effects: BehaviorEffect,
        province_state: Dict[str, Any],
        interpretation: Optional[LLMExecutionInterpretation]
    ) -> str:
        """Generate enhanced execution summary"""
        if not executed_behaviors:
            return "No behaviors executed."
        
        behavior_count = len(executed_behaviors)
        
        # Build summary
        summary_parts = [
            f"Enhanced execution completed: {behavior_count} behavior(s) processed"
        ]
        
        if interpretation:
            summary_parts.append(f"Strategy: {interpretation.execution_strategy}")
            if interpretation.confidence_level < 0.7:
                summary_parts.append(f"Note: Lower confidence execution ({interpretation.confidence_level:.1f})")
        
        # List behaviors with enhanced details
        for behavior in executed_behaviors:
            summary_parts.append(f"  - {behavior.behavior_name}: {behavior.execution_message}")
            if hasattr(behavior, 'enhanced_details'):
                summary_parts.append(f"    Enhanced effects applied")
        
        # Add net effects with context
        financial_impact = cumulative_effects.income_change - cumulative_effects.expenditure_change
        if abs(financial_impact) > 5:
            impact_desc = "positive" if financial_impact > 0 else "negative"
            summary_parts.append(
                f"Net financial impact: {financial_impact:+.0f} ({impact_desc} balance)"
            )
        
        if abs(cumulative_effects.loyalty_change) > 0.5 or abs(cumulative_effects.stability_change) > 0.5:
            summary_parts.append(
                f"Social impact: loyalty {cumulative_effects.loyalty_change:+.1f}, "
                f"stability {cumulative_effects.stability_change:+.1f}"
            )
        
        # Add quality indicator
        if interpretation and interpretation.confidence_level > 0.8:
            summary_parts.append("Execution quality: High")
        elif interpretation and interpretation.confidence_level > 0.6:
            summary_parts.append("Execution quality: Good")
        else:
            summary_parts.append("Execution quality: Standard")
        
        return "\n".join(summary_parts)

    async def _assess_execution_quality(
        self,
        execution_result: ExecutionResult,
        original_decision: Decision,
        province_state: Dict[str, Any]
    ) -> ExecutionQualityReport:
        """
        Assess execution quality comprehensively
        
        Args:
            execution_result: Result of execution
            original_decision: Original decision
            province_state: Province state after execution
            
        Returns:
            ExecutionQualityReport with quality assessment
        """
        # Calculate effectiveness (how well we achieved intended goals)
        effectiveness = self._calculate_effectiveness(execution_result, original_decision)
        
        # Calculate efficiency (resource utilization)
        efficiency = self._calculate_efficiency(execution_result)
        
        # Calculate impact (overall social and economic impact)
        impact = self._calculate_impact(execution_result, province_state)
        
        # Calculate risk management
        risk_management = self._calculate_risk_management(execution_result, original_decision)
        
        # Calculate adaptability
        adaptability = self._calculate_adaptability(execution_result)
        
        # Overall score (weighted average)
        overall_score = (
            effectiveness * 0.3 +
            efficiency * 0.2 +
            impact * 0.2 +
            risk_management * 0.15 +
            adaptability * 0.15
        )
        
        # Generate detailed assessment
        detailed_assessment = self._generate_quality_assessment(
            effectiveness, efficiency, impact, risk_management, adaptability
        )
        
        # Generate recommendations
        recommendations = self._generate_quality_recommendations(
            effectiveness, efficiency, impact, risk_management, adaptability
        )
        
        return ExecutionQualityReport(
            effectiveness=effectiveness,
            efficiency=efficiency,
            impact=impact,
            risk_management=risk_management,
            adaptability=adaptability,
            overall_score=overall_score,
            detailed_assessment=detailed_assessment,
            improvement_recommendations=recommendations,
            success_factors=self._identify_success_factors(execution_result),
            failure_factors=self._identify_failure_factors(execution_result)
        )

    def _calculate_effectiveness(
        self,
        execution_result: ExecutionResult,
        original_decision: Decision
    ) -> float:
        """Calculate execution effectiveness"""
        if not execution_result.executed_behaviors:
            return 0.0
            
        # Check if all planned behaviors were executed
        planned_behaviors = len(original_decision.behaviors)
        executed_behaviors = len(execution_result.executed_behaviors)
        behavior_completion = executed_behaviors / planned_behaviors if planned_behaviors > 0 else 0
        
        # Check if execution messages indicate success
        success_messages = sum(1 for b in execution_result.executed_behaviors 
                              if b.execution_success and 'success' in b.execution_message.lower())
        message_success_rate = success_messages / executed_behaviors if executed_behaviors > 0 else 0
        
        # Combine factors
        return (behavior_completion * 0.6 + message_success_rate * 0.4)

    def _calculate_efficiency(self, execution_result: ExecutionResult) -> float:
        """Calculate execution efficiency"""
        if not execution_result.executed_behaviors:
            return 0.0
            
        # Calculate resource efficiency
        total_effects = execution_result.total_effects
        
        # Positive effects vs negative effects ratio
        positive_impact = (
            max(0, total_effects.income_change) +
            max(0, total_effects.loyalty_change) +
            max(0, total_effects.stability_change) +
            max(0, total_effects.development_change)
        )
        
        negative_impact = (
            max(0, -total_effects.income_change) +
            max(0, -total_effects.loyalty_change) +
            max(0, -total_effects.stability_change) +
            max(0, -total_effects.development_change)
        )
        
        total_impact = positive_impact + negative_impact
        if total_impact == 0:
            return 0.5  # Neutral efficiency
            
        efficiency = positive_impact / total_impact
        return max(0.0, min(1.0, efficiency))

    def _calculate_impact(
        self,
        execution_result: ExecutionResult,
        province_state: Dict[str, Any]
    ) -> float:
        """Calculate overall impact"""
        total_effects = execution_result.total_effects
        
        # Calculate magnitude of changes (normalized)
        income_impact = abs(total_effects.income_change) / 1000.0  # Normalize to 1000
        loyalty_impact = abs(total_effects.loyalty_change) / 20.0   # Normalize to 20 points
        stability_impact = abs(total_effects.stability_change) / 20.0
        development_impact = abs(total_effects.development_change) / 5.0
        
        # Calculate weighted impact score
        impact_score = (
            min(income_impact, 1.0) * 0.3 +
            min(loyalty_impact, 1.0) * 0.25 +
            min(stability_impact, 1.0) * 0.25 +
            min(development_impact, 1.0) * 0.2
        )
        
        return max(0.0, min(1.0, impact_score))

    def _calculate_risk_management(
        self,
        execution_result: ExecutionResult,
        original_decision: Decision
    ) -> float:
        """Calculate risk management effectiveness"""
        # Check if execution avoided major negative impacts
        total_effects = execution_result.total_effects
        
        # Severe negative impacts indicate poor risk management
        severe_negative_loyalty = total_effects.loyalty_change < -15
        severe_negative_stability = total_effects.stability_change < -15
        severe_negative_income = total_effects.income_change < -500
        
        risk_indicators = sum([
            severe_negative_loyalty,
            severe_negative_stability,
            severe_negative_income
        ])
        
        # Lower risk indicators = better risk management
        risk_management_score = 1.0 - (risk_indicators / 3.0)
        
        # Consider original decision risk level
        if original_decision.risk_level.value == 'high':
            # High-risk decisions are harder to manage safely
            risk_management_score *= 0.8
        elif original_decision.risk_level.value == 'low':
            # Low-risk decisions should be very safe
            risk_management_score = min(risk_management_score, 0.9)
            
        return max(0.0, min(1.0, risk_management_score))

    def _calculate_adaptability(self, execution_result: ExecutionResult) -> float:
        """Calculate adaptability score"""
        # Look for signs of adaptation in execution
        adaptability_indicators = []
        
        for behavior in execution_result.executed_behaviors:
            # Check for adaptation keywords in execution messages
            message = behavior.execution_message.lower()
            if any(keyword in message for keyword in ['enhanced', 'adapted', 'optimized', 'adjusted']):
                adaptability_indicators.append(1)
            else:
                adaptability_indicators.append(0)
                
        if not adaptability_indicators:
            return 0.5  # Neutral adaptability
            
        adaptability_score = sum(adaptability_indicators) / len(adaptability_indicators)
        return max(0.0, min(1.0, adaptability_score))

    def _generate_quality_assessment(
        self,
        effectiveness: float,
        efficiency: float,
        impact: float,
        risk_management: float,
        adaptability: float
    ) -> str:
        """Generate detailed quality assessment narrative"""
        assessment_parts = []
        
        # Effectiveness assessment
        if effectiveness > 0.8:
            assessment_parts.append("Execution was highly effective, successfully implementing all planned behaviors.")
        elif effectiveness > 0.6:
            assessment_parts.append("Execution was generally effective with minor implementation gaps.")
        else:
            assessment_parts.append("Execution effectiveness was limited, with significant implementation challenges.")
        
        # Efficiency assessment
        if efficiency > 0.8:
            assessment_parts.append("Resource utilization was excellent, maximizing positive outcomes.")
        elif efficiency > 0.5:
            assessment_parts.append("Resource utilization was adequate with room for optimization.")
        else:
            assessment_parts.append("Resource utilization needs improvement to minimize negative impacts.")
        
        # Impact assessment
        if impact > 0.7:
            assessment_parts.append("The execution created significant positive impact across multiple dimensions.")
        elif impact > 0.4:
            assessment_parts.append("The execution achieved moderate impact on province conditions.")
        else:
            assessment_parts.append("The execution had limited measurable impact.")
        
        # Risk management assessment
        if risk_management > 0.8:
            assessment_parts.append("Risk was well-managed throughout the execution process.")
        elif risk_management > 0.6:
            assessment_parts.append("Risk management was generally adequate.")
        else:
            assessment_parts.append("Risk management needs significant improvement.")
        
        # Adaptability assessment
        if adaptability > 0.7:
            assessment_parts.append("The execution demonstrated strong adaptability to conditions.")
        elif adaptability > 0.4:
            assessment_parts.append("The execution showed moderate adaptability.")
        else:
            assessment_parts.append("The execution lacked sufficient adaptability.")
        
        return " ".join(assessment_parts)

    def _generate_quality_recommendations(
        self,
        effectiveness: float,
        efficiency: float,
        impact: float,
        risk_management: float,
        adaptability: float
    ) -> List[str]:
        """Generate quality improvement recommendations"""
        recommendations = []
        
        if effectiveness < 0.7:
            recommendations.append("Improve behavior implementation planning and execution")
            recommendations.append("Enhance execution monitoring and feedback mechanisms")
            
        if efficiency < 0.6:
            recommendations.append("Optimize resource allocation to minimize negative side effects")
            recommendations.append("Implement better cost-benefit analysis for behaviors")
            
        if impact < 0.5:
            recommendations.append("Increase behavior intensity or scope to achieve greater impact")
            recommendations.append("Focus on high-impact behaviors that address key province needs")
            
        if risk_management < 0.7:
            recommendations.append("Implement more comprehensive risk assessment procedures")
            recommendations.append("Develop better contingency plans for high-risk decisions")
            
        if adaptability < 0.5:
            recommendations.append("Enhance real-time monitoring to detect changing conditions")
            recommendations.append("Develop more flexible execution strategies")
            
        if not recommendations:
            recommendations.append("Maintain current high-quality execution standards")
            recommendations.append("Consider sharing successful practices with other provinces")
            
        return recommendations

    def _identify_success_factors(self, execution_result: ExecutionResult) -> List[str]:
        """Identify factors that contributed to success"""
        success_factors = []
        
        # Check for successful behaviors
        successful_behaviors = sum(1 for b in execution_result.executed_behaviors if b.execution_success)
        if successful_behaviors > 0:
            success_factors.append(f"Successfully executed {successful_behaviors} behaviors")
        
        # Check for positive effects
        total_effects = execution_result.total_effects
        if total_effects.loyalty_change > 0:
            success_factors.append("Improved province loyalty")
        if total_effects.stability_change > 0:
            success_factors.append("Enhanced political stability")
        if total_effects.income_change > 0:
            success_factors.append("Increased provincial income")
        if total_effects.development_change > 0:
            success_factors.append("Promoted economic development")
            
        return success_factors if success_factors else ["Basic execution completed"]

    def _identify_failure_factors(self, execution_result: ExecutionResult) -> List[str]:
        """Identify factors that limited success"""
        failure_factors = []
        
        # Check for failed behaviors
        failed_behaviors = sum(1 for b in execution_result.executed_behaviors if not b.execution_success)
        if failed_behaviors > 0:
            failure_factors.append(f"Failed to execute {failed_behaviors} behaviors properly")
        
        # Check for negative effects
        total_effects = execution_result.total_effects
        if total_effects.loyalty_change < -5:
            failure_factors.append("Significant loyalty decline")
        if total_effects.stability_change < -5:
            failure_factors.append("Political stability compromised")
        if total_effects.income_change < -100:
            failure_factors.append("Substantial income reduction")
            
        return failure_factors if failure_factors else ["No significant issues identified"]

    async def _predict_execution_outcomes(
        self,
        decision: Decision,
        province_state: Dict[str, Any]
    ) -> ExecutionPrediction:
        """
        Predict likely execution outcomes based on historical data
        
        Args:
            decision: Decision to predict outcomes for
            province_state: Current province state
            
        Returns:
            ExecutionPrediction with predicted outcomes
        """
        # Use historical data for prediction
        historical_similar = self._find_similar_executions(decision, province_state)
        
        if not historical_similar:
            # No historical data, return neutral prediction
            return ExecutionPrediction(
                success_rate=0.7,
                expected_effectiveness=6.0,
                potential_challenges=["Limited historical data for prediction"],
                recommended_optimizations=["Monitor execution closely"],
                risk_factors=["Unknown execution outcomes"],
                confidence_level=0.3
            )
        
        # Calculate statistics from historical data
        success_count = sum(1 for h in historical_similar if h.quality_score > 0.7)
        success_rate = success_count / len(historical_similar) if historical_similar else 0.5
        
        avg_quality = sum(h.quality_score for h in historical_similar) / len(historical_similar)
        expected_effectiveness = 1.0 + (9.0 * avg_quality)  # Scale 1-10
        
        # Extract common challenges and recommendations
        all_challenges = []
        all_recommendations = []
        all_risks = []
        
        for historical in historical_similar:
            all_challenges.extend(historical.challenges_encountered)
            all_recommendations.extend(historical.adaptations_made)
            # Extract risk factors from historical data
            if historical.success_indicators:
                if 'risk_factors' in historical.success_indicators:
                    all_risks.extend(historical.success_indicators['risk_factors'])
        
        # Get most common items
        common_challenges = self._get_most_common(all_challenges, 3)
        common_recommendations = self._get_most_common(all_recommendations, 3)
        common_risks = self._get_most_common(all_risks, 3)
        
        confidence_level = min(0.9, 0.3 + (0.6 * len(historical_similar) / 10.0))
        
        return ExecutionPrediction(
            success_rate=success_rate,
            expected_effectiveness=expected_effectiveness,
            potential_challenges=common_challenges,
            recommended_optimizations=common_recommendations,
            risk_factors=common_risks,
            confidence_level=confidence_level
        )

    def _find_similar_executions(
        self,
        decision: Decision,
        province_state: Dict[str, Any]
    ) -> List[ExecutionRecord]:
        """Find historically similar executions"""
        similar = []
        
        for historical in self.execution_history:
            # Check if behaviors match
            historical_behaviors = {b.behavior_type for b in historical.decision.behaviors}
            current_behaviors = {b.behavior_type for b in decision.behaviors}
            behavior_similarity = len(historical_behaviors & current_behaviors) / max(len(current_behaviors), 1)
            
            # Check if province conditions are similar
            # This is a simplified similarity check - could be enhanced
            if behavior_similarity > 0.5:  # At least 50% behavior overlap
                similar.append(historical)
        
        return similar

    def _get_most_common(self, items: List[str], max_items: int) -> List[str]:
        """Get most common items from list"""
        if not items:
            return []
        
        from collections import Counter
        counter = Counter(items)
        return [item for item, count in counter.most_common(max_items)]

    async def _record_execution(
        self,
        decision: Decision,
        execution_result: ExecutionResult,
        quality_report: ExecutionQualityReport
    ) -> None:
        """Record execution for learning purposes"""
        execution_record = ExecutionRecord(
            execution_id=str(uuid.uuid4()),
            province_id=decision.province_id,
            month=decision.month,
            year=decision.year,
            decision=decision,
            execution_result=execution_result.model_dump(),
            quality_score=quality_report.overall_score,
            success_indicators={
                'effectiveness': quality_report.effectiveness,
                'efficiency': quality_report.efficiency,
                'impact': quality_report.impact,
                'risk_management': quality_report.risk_management,
                'adaptability': quality_report.adaptability
            },
            challenges_encountered=quality_report.failure_factors,
            adaptations_made=quality_report.improvement_recommendations[:2]  # Top 2 recommendations
        )
        
        self.execution_history.append(execution_record)
        
        # Keep only recent history to prevent memory bloat
        if len(self.execution_history) > 100:
            self.execution_history = self.execution_history[-100:]

    def _build_default_execution_context(self, province_state: Dict[str, Any]) -> ExecutionContext:
        """Build default execution context from province state"""
        # Determine population mood based on loyalty
        loyalty = province_state.get('loyalty', 50)
        if loyalty > 70:
            population_mood = 'positive'
        elif loyalty < 30:
            population_mood = 'negative'
        else:
            population_mood = 'neutral'
        
        # Determine economic conditions
        income = province_state.get('actual_income', 0)
        if income > 1000:
            economic_conditions = 'booming'
        elif income > 500:
            economic_conditions = 'stable'
        elif income > 200:
            economic_conditions = 'struggling'
        else:
            economic_conditions = 'crisis'
        
        # Determine political stability
        stability = province_state.get('stability', 50)
        if stability > 70:
            political_stability = 'stable'
        elif stability < 30:
            political_stability = 'unstable'
        else:
            political_stability = 'tense'
        
        return ExecutionContext(
            season='spring',  # Default, should be set by caller
            population_mood=population_mood,
            economic_conditions=economic_conditions,
            political_stability=political_stability
        )

    # ========== Backward Compatibility ==========

    async def execute(
        self,
        decision: Decision,
        province_state: Dict[str, Any],
        month: int,
        year: int
    ) -> ExecutionResult:
        """
        Legacy execute method for backward compatibility
        
        Args:
            decision: Decision from DecisionAgent
            province_state: Current province state (will be modified)
            month: Current month
            year: Current year
            
        Returns:
            ExecutionResult (standard format)
        """
        # Build basic context
        execution_context = ExecutionContext()
        
        # Execute with LLM enhancement (but return standard result)
        enhanced_result = await self.execute_with_llm(
            decision=decision,
            province_state=province_state,
            execution_context=execution_context
        )
        
        # Return the standard execution result
        return ExecutionResult(**enhanced_result.execution_result)

    # ========== Abstract Method Implementations ==========

    async def _mock_llm_response(self, response_model) -> Any:
        """Generate mock LLM response for testing"""
        if response_model == LLMExecutionInterpretation:
            return LLMExecutionInterpretation(
                execution_strategy="Mock execution strategy for testing",
                timing_recommendations=["Execute promptly", "Monitor closely"],
                resource_allocation={"primary": "standard_allocation"},
                risk_mitigation=["Monitor stability", "Prepare contingencies"],
                expected_challenges=["Standard implementation challenges"],
                success_metrics=["Maintain stability", "Achieve objectives"],
                confidence_level=0.8
            )
        elif response_model == CreativeEventOutput:
            return CreativeEventOutput(
                event_name="Mock Policy Implementation",
                description="A standard policy implementation event occurred in the province.",
                severity=0.5,
                visibility="provincial",
                special_characteristics=["standard_implementation"],
                narrative_tone="neutral"
            )
        elif response_model == ExecutionQualityReport:
            return ExecutionQualityReport(
                effectiveness=0.8,
                efficiency=0.7,
                impact=0.6,
                risk_management=0.8,
                adaptability=0.5,
                overall_score=0.68,
                detailed_assessment="Mock quality assessment for testing purposes.",
                improvement_recommendations=["Monitor execution closely", "Optimize resource allocation"],
                success_factors=["Successful implementation", "Positive effects"],
                failure_factors=["Minor optimization opportunities"]
            )
        elif response_model == ExecutionPrediction:
            return ExecutionPrediction(
                success_rate=0.75,
                expected_effectiveness=6.5,
                potential_challenges=["Resource constraints", "Implementation complexity"],
                recommended_optimizations=["Careful planning", "Stakeholder engagement"],
                risk_factors=["Economic volatility", "Political uncertainty"],
                confidence_level=0.6
            )
        return None

    async def _mock_llm_text_response(self, prompt: str) -> str:
        """Generate mock text response"""
        return "Mock enhanced execution response for testing purposes."