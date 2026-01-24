"""
Test suite for Enhanced ExecutionAgent

Tests LLM-enhanced execution capabilities including:
- Execution interpretation and strategy optimization
- Creative event generation with contextual awareness
- Execution quality assessment
- Predictive analytics
- Backward compatibility
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, List
from datetime import datetime

from agents.province.enhanced_execution_agent import EnhancedExecutionAgent
from agents.province.enhanced_execution_models import (
    ExecutionMode, ExecutionContext, LLMExecutionInterpretation,
    ExecutionQualityReport, ExecutionPrediction, CreativeEventOutput,
    HistoricalContext, ExecutionRecord
)
from agents.province.models import (
    Decision, BehaviorDefinition, BehaviorType, BehaviorEffect,
    BehaviorEvent, ExecutionResult, RiskLevel
)


class TestEnhancedExecutionAgent:
    """Test Enhanced ExecutionAgent functionality"""

    @pytest.fixture
    def mock_config(self) -> Dict[str, Any]:
        """Mock configuration for testing"""
        return {
            'province_id': 1,
            'execution_mode': 'llm_enhanced',
            'llm_config': {
                'model': 'claude-3-haiku-20240307',
                'temperature': 0.7,
                'max_tokens': 1000
            },
            'quality_threshold': 0.7,
            'enable_learning': True,
            'mode': 'llm_assisted'  # For BaseAgent compatibility
        }

    @pytest.fixture
    def mock_province_state(self) -> Dict[str, Any]:
        """Mock province state for testing"""
        return {
            'population': 10000,
            'loyalty': 65,
            'stability': 70,
            'development_level': 6,
            'actual_income': 800,
            'actual_expenditure': 600,
            'actual_surplus': 200
        }

    @pytest.fixture
    def mock_decision(self) -> Decision:
        """Mock decision for testing"""
        behaviors = [
            BehaviorDefinition(
                behavior_type=BehaviorType.TAX_ADJUSTMENT,
                behavior_name="Tax Rate Reduction",
                parameters={'rate_change': -0.1, 'target_income': 700},
                reasoning="Reduce tax burden to improve population loyalty"
            ),
            BehaviorDefinition(
                behavior_type=BehaviorType.INFRASTRUCTURE_INVESTMENT,
                behavior_name="Road Improvement",
                parameters={'amount': 150, 'project_type': 'transportation'},
                reasoning="Improve transportation infrastructure for economic growth"
            )
        ]
        
        return Decision(
            province_id=1,
            month=6,
            year=2024,
            behaviors=behaviors,
            reasoning="Stimulate economic growth while maintaining fiscal responsibility",
            risk_level=RiskLevel.MEDIUM
        )

    @pytest.fixture
    def mock_execution_context(self) -> ExecutionContext:
        """Mock execution context for testing"""
        return ExecutionContext(
            season='summer',
            recent_events=['Good harvest', 'Trade agreement signed'],
            population_mood='positive',
            economic_conditions='stable',
            political_stability='stable'
        )

    @pytest.fixture
    def execution_agent(self, mock_config):
        """Create EnhancedExecutionAgent instance"""
        agent = EnhancedExecutionAgent("test_execution_agent", mock_config)
        return agent

    @pytest.mark.asyncio
    async def test_agent_initialization(self, execution_agent, mock_config):
        """Test agent initialization"""
        assert execution_agent.agent_id == "test_execution_agent"
        assert execution_agent.province_id == mock_config['province_id']
        assert execution_agent.execution_mode == ExecutionMode.LLM_ENHANCED
        assert execution_agent.quality_threshold == mock_config['quality_threshold']
        assert execution_agent.enable_learning == mock_config['enable_learning']

    @pytest.mark.asyncio
    async def test_llm_execution_interpretation(self, execution_agent, mock_decision, mock_province_state):
        """Test LLM execution interpretation"""
        execution_context = ExecutionContext()
        
        # Mock LLM response
        mock_interpretation = LLMExecutionInterpretation(
            execution_strategy="Implement tax reduction first, then infrastructure investment",
            timing_recommendations=["Execute during economic stability", "Monitor population response"],
            resource_allocation={'primary': 'tax_reduction', 'secondary': 'infrastructure'},
            risk_mitigation=["Monitor loyalty changes", "Prepare contingency for revenue shortfall"],
            expected_challenges=["Temporary revenue reduction", "Implementation coordination"],
            success_metrics=["Loyalty improvement > 5 points", "Infrastructure completion on schedule"],
            confidence_level=0.8
        )
        
        with patch.object(execution_agent, 'call_llm_structured', return_value=mock_interpretation):
            interpretation = await execution_agent._interpret_execution_with_llm(
                mock_decision, mock_province_state, execution_context
            )
            
            assert interpretation is not None
            assert interpretation.execution_strategy == mock_interpretation.execution_strategy
            assert interpretation.confidence_level == 0.8
            assert len(interpretation.timing_recommendations) > 0

    @pytest.mark.asyncio
    async def test_creative_event_generation(self, execution_agent, mock_decision, mock_province_state):
        """Test creative event generation with LLM"""
        behavior_def = mock_decision.behaviors[0]
        effect = BehaviorEffect(
            behavior_type=behavior_def.behavior_type,
            behavior_name=behavior_def.behavior_name,
            income_change=-50,
            loyalty_change=8,
            stability_change=3
        )
        execution_context = ExecutionContext()
        
        # Mock creative event output
        mock_creative_output = CreativeEventOutput(
            event_name="Summer Tax Relief Initiative",
            description="The provincial administration announced a comprehensive tax relief program during the summer months, bringing welcome relief to local merchants and farmers. The reduction in tax burden has sparked celebrations in market squares across the province.",
            severity=0.6,
            visibility="public",
            special_characteristics=["seasonal_timing", "popular_support"],
            narrative_tone="celebratory"
        )
        
        with patch.object(execution_agent, 'call_llm_structured', return_value=mock_creative_output):
            event = await execution_agent._generate_creative_event_with_llm(
                behavior_def, effect, mock_province_state, execution_context, None
            )
            
            assert event is not None
            assert event.name == "Summer Tax Relief Initiative"
            assert "tax relief" in event.description.lower()
            assert event.visibility == "public"
            assert event.severity == 0.6

    @pytest.mark.asyncio
    async def test_execution_quality_assessment(self, execution_agent, mock_decision):
        """Test execution quality assessment"""
        # Create mock execution result
        executed_behavior = ExecutedBehavior(
            behavior_type=BehaviorType.TAX_ADJUSTMENT,
            behavior_name="Tax Rate Reduction",
            parameters={'rate_change': -0.1},
            effects=BehaviorEffect(
                behavior_type=BehaviorType.TAX_ADJUSTMENT,
                behavior_name="Tax Rate Reduction",
                income_change=-50,
                loyalty_change=8,
                stability_change=3
            ),
            execution_success=True,
            execution_message="Successfully executed tax reduction with enhanced monitoring"
        )
        
        execution_result = ExecutionResult(
            province_id=1,
            month=6,
            year=2024,
            executed_behaviors=[executed_behavior],
            generated_events=[],
            total_effects=executed_behavior.effects,
            province_state_after={'loyalty': 73, 'stability': 73},
            execution_summary="Tax reduction executed successfully"
        )
        
        province_state = {'loyalty': 65, 'stability': 70}
        
        quality_report = await execution_agent._assess_execution_quality(
            execution_result, mock_decision, province_state
        )
        
        assert quality_report is not None
        assert quality_report.overall_score >= 0.0
        assert quality_report.overall_score <= 1.0
        assert quality_report.effectiveness >= 0.0
        assert quality_report.efficiency >= 0.0
        assert len(quality_report.improvement_recommendations) >= 0
        assert len(quality_report.success_factors) > 0

    @pytest.mark.asyncio
    async def test_execution_prediction(self, execution_agent, mock_decision, mock_province_state):
        """Test execution outcome prediction"""
        # Add some historical data
        historical_record = ExecutionRecord(
            execution_id="hist_001",
            province_id=1,
            month=5,
            year=2024,
            decision=mock_decision,
            execution_result={'summary': 'success'},
            quality_score=0.8,
            success_indicators={'effectiveness': 0.8, 'efficiency': 0.7},
            challenges_encountered=['Resource coordination'],
            adaptations_made=['Enhanced monitoring']
        )
        execution_agent.execution_history = [historical_record]
        
        prediction = await execution_agent._predict_execution_outcomes(
            mock_decision, mock_province_state
        )
        
        assert prediction is not None
        assert prediction.success_rate >= 0.0
        assert prediction.success_rate <= 1.0
        assert prediction.expected_effectiveness >= 1.0
        assert prediction.expected_effectiveness <= 10.0
        assert prediction.confidence_level >= 0.0
        assert len(prediction.potential_challenges) >= 0

    @pytest.mark.asyncio
    async def test_backward_compatibility(self, execution_agent, mock_decision, mock_province_state):
        """Test backward compatibility with standard execute method"""
        # Mock the enhanced execution to return standard result
        mock_enhanced_result = EnhancedExecutionResult(
            execution_result=ExecutionResult(
                province_id=1,
                month=6,
                year=2024,
                executed_behaviors=[],
                generated_events=[],
                total_effects=BehaviorEffect(
                    behavior_type=BehaviorType.TAX_ADJUSTMENT,
                    behavior_name="Test"
                ),
                province_state_after=mock_province_state,
                execution_summary="Backward compatibility test"
            ).model_dump(),
            quality_report=ExecutionQualityReport(
                effectiveness=0.8,
                efficiency=0.7,
                impact=0.6,
                risk_management=0.8,
                adaptability=0.5,
                overall_score=0.68,
                detailed_assessment="Test assessment",
                success_factors=["Test success"],
                failure_factors=["Test failure"]
            )
        )
        
        with patch.object(execution_agent, 'execute_with_llm', return_value=mock_enhanced_result):
            result = await execution_agent.execute(
                decision=mock_decision,
                province_state=mock_province_state,
                month=6,
                year=2024
            )
            
            assert isinstance(result, ExecutionResult)
            assert result.province_id == 1
            assert result.month == 6
            assert result.year == 2024

    @pytest.mark.asyncio
    async def test_contextual_effect_modification(self, execution_agent):
        """Test contextual effect modification"""
        base_effect = BehaviorEffect(
            behavior_type=BehaviorType.INFRASTRUCTURE_INVESTMENT,
            behavior_name="Winter Road Work",
            expenditure_change=100,
            development_change=2
        )
        
        province_state = {'loyalty': 60, 'stability': 65}
        execution_context = ExecutionContext(season='winter')
        
        enhanced_effect = execution_agent._apply_contextual_modifications(
            base_effect, province_state, execution_context
        )
        
        # Winter should increase infrastructure costs
        assert enhanced_effect.expenditure_change > base_effect.expenditure_change
        assert enhanced_effect.expenditure_change == 110  # 10% increase

    @pytest.mark.asyncio
    async def test_standard_event_generation_fallback(self, execution_agent, mock_decision, mock_province_state):
        """Test standard event generation fallback"""
        behavior_def = mock_decision.behaviors[0]
        effect = BehaviorEffect(
            behavior_type=behavior_def.behavior_type,
            behavior_name=behavior_def.behavior_name,
            income_change=-50,
            loyalty_change=8
        )
        
        event = execution_agent._generate_standard_event(
            behavior_def, effect, mock_province_state
        )
        
        assert event is not None
        assert event.event_type == behavior_def.behavior_type.value
        assert event.name == behavior_def.behavior_name
        assert 'tax' in event.description.lower() or 'adjustment' in event.description.lower()
        assert event.severity >= 0.1
        assert event.severity <= 1.0

    @pytest.mark.asyncio
    async def test_effect_accumulation(self, execution_agent):
        """Test effect accumulation logic"""
        cumulative = BehaviorEffect(
            behavior_type=BehaviorType.TAX_ADJUSTMENT,
            behavior_name="Cumulative",
            income_change=100,
            loyalty_change=5
        )
        
        new_effect = BehaviorEffect(
            behavior_type=BehaviorType.INFRASTRUCTURE_INVESTMENT,
            behavior_name="New",
            income_change=50,
            loyalty_change=3,
            stability_change=2
        )
        
        execution_agent._accumulate_effects(cumulative, new_effect)
        
        assert cumulative.income_change == 150
        assert cumulative.loyalty_change == 8
        assert cumulative.stability_change == 2

    @pytest.mark.asyncio
    async def test_quality_calculation_components(self, execution_agent, mock_decision):
        """Test individual quality calculation components"""
        # Create test execution result
        executed_behavior = ExecutedBehavior(
            behavior_type=BehaviorType.TAX_ADJUSTMENT,
            behavior_name="Test Behavior",
            effects=BehaviorEffect(
                behavior_type=BehaviorType.TAX_ADJUSTMENT,
                behavior_name="Test Behavior",
                income_change=100,
                loyalty_change=10,
                stability_change=5
            ),
            execution_success=True,
            execution_message="Successfully executed with enhanced monitoring"
        )
        
        execution_result = ExecutionResult(
            province_id=1,
            month=6,
            year=2024,
            executed_behaviors=[executed_behavior],
            generated_events=[],
            total_effects=executed_behavior.effects,
            province_state_after={'loyalty': 75, 'stability': 75},
            execution_summary="Test execution"
        )
        
        # Test effectiveness calculation
        effectiveness = execution_agent._calculate_effectiveness(execution_result, mock_decision)
        assert effectiveness >= 0.0
        assert effectiveness <= 1.0
        
        # Test efficiency calculation
        efficiency = execution_agent._calculate_efficiency(execution_result)
        assert efficiency >= 0.0
        assert efficiency <= 1.0
        
        # Test impact calculation
        province_state = {'loyalty': 65, 'stability': 70}
        impact = execution_agent._calculate_impact(execution_result, province_state)
        assert impact >= 0.0
        assert impact <= 1.0

    @pytest.mark.asyncio
    async def test_mock_responses(self, execution_agent):
        """Test mock LLM responses for testing"""
        # Test LLM interpretation mock
        interpretation = await execution_agent._mock_llm_response(LLMExecutionInterpretation)
        assert isinstance(interpretation, LLMExecutionInterpretation)
        assert interpretation.confidence_level == 0.8
        
        # Test creative event mock
        creative = await execution_agent._mock_llm_response(CreativeEventOutput)
        assert isinstance(creative, CreativeEventOutput)
        assert creative.severity == 0.5
        
        # Test quality report mock
        quality = await execution_agent._mock_llm_response(ExecutionQualityReport)
        assert isinstance(quality, ExecutionQualityReport)
        assert quality.overall_score == 0.68

    @pytest.mark.asyncio
    async def test_error_handling(self, execution_agent, mock_decision, mock_province_state):
        """Test error handling in LLM operations"""
        execution_context = ExecutionContext()
        
        # Test LLM failure handling
        with patch.object(execution_agent, 'call_llm_structured', side_effect=Exception("LLM API Error")):
            interpretation = await execution_agent._interpret_execution_with_llm(
                mock_decision, mock_province_state, execution_context
            )
            
            # Should return fallback interpretation
            assert interpretation is not None
            assert interpretation.confidence_level == 0.6  # Fallback confidence
            assert "standard execution approach" in interpretation.execution_strategy.lower()

    @pytest.mark.asyncio
    async def test_full_enhanced_execution(self, execution_agent, mock_decision, mock_province_state, mock_execution_context):
        """Test full enhanced execution pipeline"""
        # Mock all LLM calls
        mock_interpretation = LLMExecutionInterpretation(
            execution_strategy="Optimized execution strategy",
            timing_recommendations=["Phase 1: Tax reduction", "Phase 2: Infrastructure"],
            resource_allocation={'primary': 'tax_reduction'},
            risk_mitigation=["Monitor revenue impact"],
            expected_challenges=["Revenue short-term reduction"],
            success_metrics=["Loyalty improvement", "Infrastructure completion"],
            confidence_level=0.85
        )
        
        mock_creative_event = CreativeEventOutput(
            event_name="Economic Revitalization Initiative",
            description="A comprehensive economic revitalization program was launched",
            severity=0.7,
            visibility="public",
            special_characteristics=["comprehensive", "strategic"],
            narrative_tone="optimistic"
        )
        
        mock_prediction = ExecutionPrediction(
            success_rate=0.8,
            expected_effectiveness=7.5,
            potential_challenges=["Coordination complexity"],
            recommended_optimizations=["Staged implementation"],
            risk_factors=["Economic uncertainty"],
            confidence_level=0.75
        )
        
        # Mock LLM calls sequentially
        llm_responses = [mock_interpretation, mock_creative_event, mock_creative_event, mock_prediction]
        
        with patch.object(execution_agent, 'call_llm_structured', side_effect=llm_responses):
            result = await execution_agent.execute_with_llm(
                decision=mock_decision,
                province_state=mock_province_state,
                execution_context=mock_execution_context
            )
            
            assert result is not None
            assert result.execution_result is not None
            assert result.quality_report is not None
            assert result.execution_interpretation is not None
            assert result.predictive_insights is not None
            
            # Check quality report
            assert result.quality_report.overall_score >= 0.0
            assert len(result.quality_report.improvement_recommendations) >= 0
            
            # Check interpretation
            assert result.execution_interpretation.confidence_level == 0.85
            assert "optimized" in result.execution_interpretation.execution_strategy.lower()

    @pytest.mark.asyncio
    async def test_performance_benchmarks(self, execution_agent, mock_decision, mock_province_state):
        """Test performance benchmarks"""
        import time
        
        execution_context = ExecutionContext()
        
        # Mock fast LLM responses
        mock_interpretation = LLMExecutionInterpretation(
            execution_strategy="Quick execution",
            confidence_level=0.8
        )
        
        with patch.object(execution_agent, 'call_llm_structured', return_value=mock_interpretation):
            start_time = time.time()
            
            result = await execution_agent.execute_with_llm(
                decision=mock_decision,
                province_state=mock_province_state,
                execution_context=execution_context
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Should complete within reasonable time (even with mocks)
            assert execution_time < 1.0  # Less than 1 second
            assert result is not None


class TestExecutionQualityScoring:
    """Test execution quality scoring algorithms"""

    def test_effectiveness_scoring(self):
        """Test effectiveness scoring logic"""
        # Create test data
        executed_behavior = ExecutedBehavior(
            behavior_type=BehaviorType.TAX_ADJUSTMENT,
            behavior_name="Test",
            effects=BehaviorEffect(
                behavior_type=BehaviorType.TAX_ADJUSTMENT,
                behavior_name="Test"
            ),
            execution_success=True,
            execution_message="Successfully executed"
        )
        
        execution_result = ExecutionResult(
            province_id=1,
            month=6,
            year=2024,
            executed_behaviors=[executed_behavior],
            generated_events=[],
            total_effects=executed_behavior.effects,
            province_state_after={},
            execution_summary="Test"
        )
        
        decision = Decision(
            province_id=1,
            month=6,
            year=2024,
            behaviors=[
                BehaviorDefinition(
                    behavior_type=BehaviorType.TAX_ADJUSTMENT,
                    behavior_name="Test"
                )
            ],
            reasoning="Test"
        )
        
        # Test with agent
        agent = EnhancedExecutionAgent("test", {'province_id': 1, 'mode': 'standard'})
        effectiveness = agent._calculate_effectiveness(execution_result, decision)
        
        assert effectiveness >= 0.0
        assert effectiveness <= 1.0

    def test_efficiency_scoring(self):
        """Test efficiency scoring logic"""
        # Test with positive effects
        positive_effect = BehaviorEffect(
            behavior_type=BehaviorType.ECONOMIC_STIMULUS,
            behavior_name="Positive",
            income_change=100,
            loyalty_change=10,
            stability_change=5
        )
        
        execution_result = ExecutionResult(
            province_id=1,
            month=6,
            year=2024,
            executed_behaviors=[],
            generated_events=[],
            total_effects=positive_effect,
            province_state_after={},
            execution_summary="Test"
        )
        
        agent = EnhancedExecutionAgent("test", {'province_id': 1, 'mode': 'standard'})
        efficiency = agent._calculate_efficiency(execution_result)
        
        assert efficiency >= 0.5  # Should be good with all positive effects
        assert efficiency <= 1.0

    def test_risk_management_scoring(self):
        """Test risk management scoring logic"""
        # Test with high-risk decision
        high_risk_effect = BehaviorEffect(
            behavior_type=BehaviorType.EMERGENCY_RELIEF,
            behavior_name="High Risk",
            loyalty_change=-20,  # Severe negative impact
            stability_change=-10
        )
        
        execution_result = ExecutionResult(
            province_id=1,
            month=6,
            year=2024,
            executed_behaviors=[],
            generated_events=[],
            total_effects=high_risk_effect,
            province_state_after={},
            execution_summary="Test"
        )
        
        decision = Decision(
            province_id=1,
            month=6,
            year=2024,
            behaviors=[],
            reasoning="Test",
            risk_level=RiskLevel.HIGH
        )
        
        agent = EnhancedExecutionAgent("test", {'province_id': 1, 'mode': 'standard'})
        risk_management = agent._calculate_risk_management(execution_result, decision)
        
        assert risk_management < 0.5  # Should be poor with severe negative impacts
        assert risk_management >= 0.0


class TestHistoricalLearning:
    """Test historical learning and pattern recognition"""

    @pytest.mark.asyncio
    async def test_similar_execution_matching(self):
        """Test finding similar historical executions"""
        agent = EnhancedExecutionAgent("test", {'province_id': 1, 'mode': 'standard'})
        
        # Create historical records
        historical_decision = Decision(
            province_id=1,
            month=5,
            year=2024,
            behaviors=[
                BehaviorDefinition(
                    behavior_type=BehaviorType.TAX_ADJUSTMENT,
                    behavior_name="Historical Tax Change"
                )
            ],
            reasoning="Historical test"
        )
        
        historical_record = ExecutionRecord(
            execution_id="hist_001",
            province_id=1,
            month=5,
            year=2024,
            decision=historical_decision,
            execution_result={'summary': 'success'},
            quality_score=0.8,
            success_indicators={'effectiveness': 0.8}
        )
        
        agent.execution_history = [historical_record]
        
        # Test with similar current decision
        current_decision = Decision(
            province_id=1,
            month=6,
            year=2024,
            behaviors=[
                BehaviorDefinition(
                    behavior_type=BehaviorType.TAX_ADJUSTMENT,
                    behavior_name="Current Tax Change"
                )
            ],
            reasoning="Current test"
        )
        
        similar = agent._find_similar_executions(current_decision, {})
        assert len(similar) > 0
        assert similar[0].execution_id == "hist_001"

    @pytest.mark.asyncio
    async def test_prediction_from_history(self):
        """Test prediction generation from historical data"""
        agent = EnhancedExecutionAgent("test", {'province_id': 1, 'mode': 'standard'})
        
        # Create multiple historical records
        for i in range(3):
            historical_decision = Decision(
                province_id=1,
                month=5+i,
                year=2024,
                behaviors=[
                    BehaviorDefinition(
                        behavior_type=BehaviorType.TAX_ADJUSTMENT,
                        behavior_name=f"Tax Change {i}"
                    )
                ],
                reasoning=f"Historical test {i}"
            )
            
            historical_record = ExecutionRecord(
                execution_id=f"hist_{i}",
                province_id=1,
                month=5+i,
                year=2024,
                decision=historical_decision,
                execution_result={'summary': 'success'},
                quality_score=0.7 + (i * 0.1),  # Varying quality
                success_indicators={'effectiveness': 0.7 + (i * 0.1)},
                challenges_encountered=[f"Challenge {i}"],
                adaptations_made=[f"Adaptation {i}"]
            )
            
            agent.execution_history.append(historical_record)
        
        # Test prediction
        current_decision = Decision(
            province_id=1,
            month=8,
            year=2024,
            behaviors=[
                BehaviorDefinition(
                    behavior_type=BehaviorType.TAX_ADJUSTMENT,
                    behavior_name="Current Tax Change"
                )
            ],
            reasoning="Current test"
        )
        
        prediction = await agent._predict_execution_outcomes(current_decision, {})
        
        assert prediction.success_rate >= 0.0
        assert prediction.success_rate <= 1.0
        assert prediction.expected_effectiveness >= 1.0
        assert prediction.confidence_level > 0.3  # Should have some confidence with history
        assert len(prediction.potential_challenges) >= 0


@pytest.mark.asyncio
async def test_integration_with_decision_agent():
    """Test integration with DecisionAgent output"""
    # This test validates that EnhancedExecutionAgent can handle real DecisionAgent output
    agent = EnhancedExecutionAgent("integration_test", {
        'province_id': 1,
        'execution_mode': 'hybrid',
        'mode': 'llm_assisted'
    })
    
    # Create realistic decision from DecisionAgent
    realistic_decision = Decision(
        province_id=1,
        month=6,
        year=2024,
        behaviors=[
            BehaviorDefinition(
                behavior_type=BehaviorType.ECONOMIC_STIMULUS,
                behavior_name="Economic Recovery Package",
                parameters={'amount': 500, 'target_sectors': ['agriculture', 'manufacturing']},
                reasoning="Stimulate economic growth following recent downturn"
            ),
            BehaviorDefinition(
                behavior_type=BehaviorType.STABILITY_MEASURE,
                behavior_name="Administrative Reform",
                parameters={'intensity': 0.7, 'scope': 'provincial'},
                reasoning="Improve governance efficiency and reduce corruption"
            )
        ],
        reasoning="Comprehensive approach to address economic challenges while improving administrative efficiency",
        risk_level=RiskLevel.MEDIUM,
        estimated_effects={
            'expected_income_change': 200,
            'expected_loyalty_change': 5,
            'expected_stability_change': 8
        }
    )
    
    province_state = {
        'population': 15000,
        'loyalty': 58,
        'stability': 62,
        'development_level': 5,
        'actual_income': 650,
        'actual_expenditure': 580,
        'actual_surplus': 70
    }
    
    execution_context = ExecutionContext(
        season='summer',
        recent_events=['Economic slowdown', 'Administrative inefficiency reported'],
        population_mood='concerned',
        economic_conditions='struggling',
        political_stability='tense'
    )
    
    # Mock LLM responses for integration test
    mock_interpretation = LLMExecutionInterpretation(
        execution_strategy="Implement stimulus first to build economic confidence, then administrative reforms",
        timing_recommendations=["Start with high-visibility stimulus projects", "Phase in reforms gradually"],
        resource_allocation={'primary': 'economic_stimulus', 'secondary': 'administrative_reform'},
        risk_mitigation=["Monitor economic indicators closely", "Ensure reform transparency"],
        expected_challenges=["Coordination between initiatives", "Resource allocation balance"],
        success_metrics=["Economic improvement within 3 months", "Administrative efficiency gains"],
        confidence_level=0.75
    )
    
    with patch.object(agent, 'call_llm_structured', return_value=mock_interpretation):
        result = await agent.execute_with_llm(
            decision=realistic_decision,
            province_state=province_state,
            execution_context=execution_context
        )
        
        assert result is not None
        assert result.execution_result is not None
        assert result.quality_report is not None
        assert result.execution_interpretation is not None
        
        # Validate execution result structure
        execution_data = result.execution_result
        assert 'province_id' in execution_data
        assert 'executed_behaviors' in execution_data
        assert 'generated_events' in execution_data
        assert 'total_effects' in execution_data
        
        # Validate quality assessment
        assert result.quality_report.overall_score >= 0
        assert result.quality_report.effectiveness >= 0
        assert result.quality_report.efficiency >= 0
        assert result.quality_report.impact >= 0
        assert result.quality_report.risk_management >= 0
        assert result.quality_report.adaptability >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])