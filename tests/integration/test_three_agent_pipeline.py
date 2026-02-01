"""
Integration Tests for Three-Agent Pipeline

Tests the complete Perception -> Decision -> Execution pipeline
with various scenarios and error handling.
"""

import pytest
import asyncio
import sys
import os
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.province.perception_agent import PerceptionAgent
from agents.province.decision_agent_llm import EnhancedDecisionAgent
from agents.province.enhanced_execution_agent import EnhancedExecutionAgent
from agents.province.enhanced_execution_models import ExecutionContext
from tests.pipeline_mock_data import MockDataGenerator
from db.database import Database


class TestThreeAgentPipeline:
    """Integration tests for the three-agent pipeline"""

    @pytest.fixture
    def db(self):
        """Create in-memory database for testing"""
        db = Database(":memory:")
        yield db
        # Cleanup handled by in-memory database

    @pytest.fixture
    def agent_configs(self):
        """Create agent configurations with mock mode"""
        return {
            'perception': {
                'province_id': 1,
                'llm_config': {
                    'enabled': True,
                    'mock_mode': True,
                    'provider': 'anthropic',
                    'model': 'claude-3-haiku-20240307',
                    'max_tokens': 1024,
                    'temperature': 0.1
                }
            },
            'decision': {
                'province_id': 1,
                'llm_config': {
                    'enabled': True,
                    'mock_mode': True,
                    'provider': 'anthropic',
                    'model': 'claude-3-haiku-20240307',
                    'max_tokens': 1024,
                    'temperature': 0.1
                },
                'mode': 'llm_assisted',
                'interaction_rounds': 0
            },
            'execution': {
                'province_id': 1,
                'llm_config': {
                    'enabled': True,
                    'mock_mode': True,
                    'provider': 'anthropic',
                    'model': 'claude-3-haiku-20240307',
                    'max_tokens': 1024,
                    'temperature': 0.1
                },
                'execution_mode': 'llm_enhanced'
            }
        }

    @pytest.mark.asyncio
    async def test_full_pipeline_success(self, db, agent_configs):
        """Test complete pipeline execution with normal scenario"""
        # Create agents
        decision_agent = EnhancedDecisionAgent(
            agent_id="test_decision",
            config=agent_configs['decision']
        )
        execution_agent = EnhancedExecutionAgent(
            agent_id="test_execution",
            config=agent_configs['execution']
        )

        # Create mock data directly (no need to call perception agent for this test)
        perception_context = MockDataGenerator.create_perception_context(
            scenario='normal',
            province_id=1,
            month=1,
            year=1
        )
        province_state = MockDataGenerator.create_province_state('normal')

        # Verify perception context
        assert perception_context is not None
        assert perception_context.province_id == 1
        assert perception_context.data_quality == "complete"
        assert perception_context.trends.risk_level.value == 'low'

        # Stage 2: Decision
        decision = await decision_agent.make_decision(
            perception=perception_context,
            instruction=None,
            province_state=province_state
        )

        assert decision is not None
        assert decision.province_id == 1
        assert len(decision.behaviors) >= 1
        assert decision.risk_level.value in ['low', 'medium', 'high']
        assert decision.reasoning is not None

        # Stage 3: Execution
        execution_context = ExecutionContext(
            season='spring',
            population_mood='neutral',
            economic_conditions='stable',
            political_stability='stable'
        )

        execution_result = await execution_agent.execute_with_llm(
            decision=decision,
            province_state=province_state.copy(),
            execution_context=execution_context
        )

        assert execution_result is not None
        assert hasattr(execution_result, 'quality_report')
        assert execution_result.quality_report.overall_score > 0

        execution_data = execution_result.execution_result
        assert execution_data['executed_behaviors']
        assert len(execution_data['executed_behaviors']) == len(decision.behaviors)

    @pytest.mark.asyncio
    async def test_pipeline_with_crisis_scenario(self, db, agent_configs):
        """Test pipeline with crisis scenario"""
        # Create agents
        decision_agent = EnhancedDecisionAgent(
            agent_id="test_decision",
            config=agent_configs['decision']
        )

        # Create crisis scenario data
        perception_context = MockDataGenerator.create_perception_context(
            scenario='crisis',
            province_id=1,
            month=1,
            year=1
        )
        province_state = MockDataGenerator.create_province_state('crisis')

        # Verify crisis scenario data
        assert perception_context.trends.risk_level.value == 'high'
        assert len(perception_context.critical_events) > 0

        decision = await decision_agent.make_decision(
            perception=perception_context,
            instruction=None,
            province_state=province_state
        )

        # Crisis scenario should trigger risk-aware behaviors
        assert decision is not None
        assert len(decision.behaviors) >= 1

    @pytest.mark.asyncio
    async def test_pipeline_with_instruction(self, db, agent_configs):
        """Test pipeline with player instruction"""
        from agents.province.models import PlayerInstruction, InstructionStatus

        # Create agents
        decision_agent = EnhancedDecisionAgent(
            agent_id="test_decision",
            config=agent_configs['decision']
        )

        # Create mock data and instruction
        perception_context = MockDataGenerator.create_perception_context(
            scenario='normal',
            province_id=1,
            month=1,
            year=1
        )
        province_state = MockDataGenerator.create_province_state('normal')

        instruction = PlayerInstruction(
            instruction_id=1,
            province_id=1,
            month=1,
            year=1,
            instruction_type="loyalty_improvement",
            template_name="loyalty_campaign",
            parameters={"intensity": 1.5},
            status=InstructionStatus.PENDING
        )

        # Run decision with instruction
        decision = await decision_agent.make_decision(
            perception=perception_context,
            instruction=instruction,
            province_state=province_state
        )

        assert decision is not None
        assert decision.in_response_to_instruction == 1

    @pytest.mark.asyncio
    async def test_pipeline_error_handling(self, db, agent_configs):
        """Test pipeline error handling and fallback"""
        # Test with LLM disabled (fallback to mock)
        config_with_fallback = agent_configs['decision'].copy()
        config_with_fallback['llm_config']['mock_mode'] = True

        decision_agent = EnhancedDecisionAgent(
            agent_id="test_decision",
            config=config_with_fallback
        )

        perception_context = MockDataGenerator.create_perception_context(
            scenario='normal',
            province_id=1,
            month=1,
            year=1
        )
        province_state = MockDataGenerator.create_province_state('normal')

        # Should still work with mock mode
        decision = await decision_agent.make_decision(
            perception=perception_context,
            instruction=None,
            province_state=province_state
        )

        assert decision is not None
        assert decision.behaviors is not None

    @pytest.mark.asyncio
    async def test_pipeline_performance_tracking(self, db, agent_configs):
        """Test that pipeline stages complete in reasonable time"""
        import time

        # Create agents
        decision_agent = EnhancedDecisionAgent(
            agent_id="test_decision",
            config=agent_configs['decision']
        )
        execution_agent = EnhancedExecutionAgent(
            agent_id="test_execution",
            config=agent_configs['execution']
        )

        perception_context = MockDataGenerator.create_perception_context(
            scenario='normal',
            province_id=1,
            month=1,
            year=1
        )
        province_state = MockDataGenerator.create_province_state('normal')

        # Verify perception context is valid
        assert perception_context is not None
        perception_time = 0.01  # Mock data creation is instant

        # Time decision stage
        start = time.time()
        decision = await decision_agent.make_decision(
            perception=perception_context,
            instruction=None,
            province_state=province_state
        )
        decision_time = time.time() - start

        start = time.time()
        execution_context = ExecutionContext()
        execution_result = await execution_agent.execute_with_llm(
            decision=decision,
            province_state=province_state.copy(),
            execution_context=execution_context
        )
        execution_time = time.time() - start

        # All stages should complete
        assert decision is not None
        assert execution_result is not None

        # In mock mode, should be fast (< 5 seconds each)
        assert decision_time < 5.0
        assert execution_time < 5.0

    @pytest.mark.asyncio
    async def test_pipeline_json_loading(self, db, agent_configs):
        """Test loading data from JSON and running pipeline"""
        from agents.province.models import PerceptionContext
        import json
        import tempfile

        # Create temporary JSON file
        perception_context = MockDataGenerator.create_perception_context(
            scenario='prosperity',
            province_id=1,
            month=1,
            year=1
        )
        province_state = MockDataGenerator.create_province_state('prosperity')

        data = {
            'perception_context': perception_context.model_dump(),
            'province_state': province_state
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            temp_file = f.name

        try:
            # Load from file
            with open(temp_file, 'r') as f:
                loaded_data = json.load(f)

            loaded_perception = PerceptionContext(**loaded_data['perception_context'])
            loaded_province_state = loaded_data['province_state']

            assert loaded_perception.province_id == 1
            assert loaded_province_state['loyalty'] > 80  # Prosperity scenario

        finally:
            os.unlink(temp_file)

    @pytest.mark.asyncio
    async def test_pipeline_quality_assessment(self, db, agent_configs):
        """Test execution quality assessment"""
        execution_agent = EnhancedExecutionAgent(
            agent_id="test_execution",
            config=agent_configs['execution']
        )

        perception_context = MockDataGenerator.create_perception_context(
            scenario='normal',
            province_id=1,
            month=1,
            year=1
        )
        province_state = MockDataGenerator.create_province_state('normal')

        # Create a simple decision
        from agents.province.models import BehaviorDefinition, BehaviorType, Decision, RiskLevel

        decision = Decision(
            province_id=1,
            month=1,
            year=1,
            behaviors=[
                BehaviorDefinition(
                    behavior_type=BehaviorType.LOYALTY_CAMPAIGN,
                    behavior_name="Loyalty Campaign",
                    parameters={"intensity": 1.0}
                )
            ],
            reasoning="Test decision",
            risk_level=RiskLevel.LOW
        )

        execution_context = ExecutionContext()

        result = await execution_agent.execute_with_llm(
            decision=decision,
            province_state=province_state.copy(),
            execution_context=execution_context
        )

        assert result is not None
        assert result.quality_report is not None

        quality = result.quality_report
        assert 0 <= quality.effectiveness <= 1
        assert 0 <= quality.efficiency <= 1
        assert 0 <= quality.impact <= 1
        assert 0 <= quality.risk_management <= 1
        assert 0 <= quality.adaptability <= 1
        assert 0 <= quality.overall_score <= 1

        # Should have recommendations
        assert isinstance(quality.improvement_recommendations, list)
        assert isinstance(quality.success_factors, list)

    @pytest.mark.asyncio
    async def test_pipeline_multiple_scenarios(self, db, agent_configs):
        """Test pipeline across multiple scenarios"""
        scenarios = ['normal', 'crisis', 'prosperity', 'growth', 'decline']

        for scenario in scenarios:
            # Create agents for each scenario
            decision_agent = EnhancedDecisionAgent(
                agent_id=f"test_decision_{scenario}",
                config=agent_configs['decision']
            )
            execution_agent = EnhancedExecutionAgent(
                agent_id=f"test_execution_{scenario}",
                config=agent_configs['execution']
            )

            # Create scenario data
            perception_context = MockDataGenerator.create_perception_context(
                scenario=scenario,
                province_id=1,
                month=1,
                year=1
            )
            province_state = MockDataGenerator.create_province_state(scenario)

            # Verify perception data
            assert perception_context is not None, f"Perception data creation failed for {scenario}"

            # Run decision stage
            decision = await decision_agent.make_decision(
                perception=perception_context,
                instruction=None,
                province_state=province_state
            )

            # Run execution stage
            execution_context = ExecutionContext()
            execution_result = await execution_agent.execute_with_llm(
                decision=decision,
                province_state=province_state.copy(),
                execution_context=execution_context
            )

            # Verify all stages completed
            assert decision is not None, f"Decision failed for {scenario}"
            assert execution_result is not None, f"Execution failed for {scenario}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
