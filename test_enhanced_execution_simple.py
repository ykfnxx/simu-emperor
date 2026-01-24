#!/usr/bin/env python3
"""
Simple test script for Enhanced ExecutionAgent
Tests basic functionality and LLM enhancement capabilities
"""

import asyncio
import sys
from typing import Dict, Any

from agents.province.enhanced_execution_agent import EnhancedExecutionAgent
from agents.province.enhanced_execution_models import ExecutionMode, ExecutionContext
from agents.province.models import Decision, BehaviorDefinition, BehaviorType, RiskLevel, BehaviorEffect, ExecutedBehavior, ExecutionResult


async def test_basic_functionality():
    """Test basic agent functionality"""
    print("🧪 Testing Basic EnhancedExecutionAgent Functionality")
    print("=" * 60)
    
    # Test 1: Agent Creation
    print("1. Testing agent creation...")
    config = {
        'province_id': 1,
        'execution_mode': 'standard',
        'mode': 'standard'
    }
    
    try:
        agent = EnhancedExecutionAgent("test_agent", config)
        print("   ✅ Agent created successfully")
        print(f"   📋 Agent ID: {agent.agent_id}")
        print(f"   🏛️  Province ID: {agent.province_id}")
        print(f"   ⚙️  Execution Mode: {agent.execution_mode}")
    except Exception as e:
        print(f"   ❌ Agent creation failed: {e}")
        return False
    
    # Test 2: State Management
    print("\n2. Testing state management...")
    try:
        state = agent.get_state()
        print("   ✅ State retrieval successful")
        print(f"   📊 State keys: {list(state.keys())}")
    except Exception as e:
        print(f"   ❌ State retrieval failed: {e}")
        return False
    
    # Test 3: Basic Execution (Backward Compatibility)
    print("\n3. Testing basic execution (backward compatibility)...")
    try:
        decision = Decision(
            province_id=1,
            month=6,
            year=2024,
            behaviors=[
                BehaviorDefinition(
                    behavior_type=BehaviorType.TAX_ADJUSTMENT,
                    behavior_name="Test Tax Reduction",
                    parameters={'rate_change': -0.1}
                )
            ],
            reasoning="Test basic execution",
            risk_level=RiskLevel.LOW
        )
        
        province_state = {
            'population': 10000,
            'loyalty': 60,
            'stability': 70,
            'development_level': 5,
            'actual_income': 800,
            'actual_expenditure': 600,
            'actual_surplus': 200
        }
        
        result = await agent.execute(decision, province_state.copy(), 6, 2024)
        print("   ✅ Basic execution successful")
        print(f"   📈 Behaviors executed: {len(result.executed_behaviors)}")
        print(f"   🎭 Events generated: {len(result.generated_events)}")
        print(f"   📊 Final loyalty: {province_state['loyalty']:.1f}")
    except Exception as e:
        print(f"   ❌ Basic execution failed: {e}")
        return False
    
    return True


async def test_llm_enhanced_functionality():
    """Test LLM-enhanced functionality"""
    print("\n🤖 Testing LLM-Enhanced Functionality")
    print("=" * 60)
    
    # Test 1: LLM-Enhanced Agent Creation
    print("1. Testing LLM-enhanced agent creation...")
    config = {
        'province_id': 1,
        'execution_mode': 'llm_enhanced',
        'mode': 'llm_assisted',
        'llm_config': {
            'enabled': True,
            'mock_mode': True,  # Use mock mode for testing
            'model': 'claude-3-haiku-20240307',
            'temperature': 0.7,
            'max_tokens': 1000
        }
    }
    
    try:
        agent = EnhancedExecutionAgent("llm_test_agent", config)
        print("   ✅ LLM-enhanced agent created successfully")
        print(f"   🔧 Mock Mode: {agent.llm_config.get('mock_mode', False)} (from config)")
        print(f"   🔧 LLM Enabled: {agent.llm_config.get('enabled', False)}")
    except Exception as e:
        print(f"   ❌ LLM-enhanced agent creation failed: {e}")
        return False
    
    # Test 2: Execution Interpretation
    print("\n2. Testing execution interpretation...")
    try:
        decision = Decision(
            province_id=1,
            month=7,
            year=2024,
            behaviors=[
                BehaviorDefinition(
                    behavior_type=BehaviorType.ECONOMIC_STIMULUS,
                    behavior_name="Economic Support Package",
                    parameters={'amount': 300, 'target_sectors': ['agriculture']}
                )
            ],
            reasoning="Support economic recovery",
            risk_level=RiskLevel.MEDIUM
        )
        
        province_state = {
            'population': 12000,
            'loyalty': 55,
            'stability': 65,
            'development_level': 6,
            'actual_income': 700,
            'actual_expenditure': 550,
            'actual_surplus': 150
        }
        
        execution_context = ExecutionContext(
            season='summer',
            recent_events=['Economic downturn', 'Trade disruption'],
            population_mood='concerned',
            economic_conditions='struggling',
            political_stability='tense'
        )
        
        interpretation = await agent._interpret_execution_with_llm(
            decision, province_state, execution_context
        )
        
        print("   ✅ Execution interpretation successful")
        print(f"   🧠 Strategy: {interpretation.execution_strategy}")
        print(f"   📈 Confidence: {interpretation.confidence_level:.1f}")
        print(f"   ⏰ Recommendations: {len(interpretation.timing_recommendations)}")
    except Exception as e:
        print(f"   ❌ Execution interpretation failed: {e}")
        return False
    
    # Test 3: Enhanced Execution
    print("\n3. Testing enhanced execution...")
    try:
        result = await agent.execute_with_llm(
            decision, province_state.copy(), execution_context
        )
        
        print("   ✅ Enhanced execution successful")
        print(f"   📊 Quality Score: {result.quality_report.overall_score:.2f}/1.0")
        print(f"   🎯 Effectiveness: {result.quality_report.effectiveness:.2f}")
        print(f"   💡 Efficiency: {result.quality_report.efficiency:.2f}")
        print(f"   📈 Impact: {result.quality_report.impact:.2f}")
        print(f"   🛡️  Risk Management: {result.quality_report.risk_management:.2f}")
        print(f"   🔧 Adaptability: {result.quality_report.adaptability:.2f}")
    except Exception as e:
        print(f"   ❌ Enhanced execution failed: {e}")
        return False
    
    return True


async def test_quality_assessment():
    """Test quality assessment functionality"""
    print("\n📊 Testing Quality Assessment")
    print("=" * 60)
    
    config = {
        'province_id': 1,
        'execution_mode': 'standard',
        'mode': 'standard'
    }
    
    try:
        agent = EnhancedExecutionAgent("quality_test_agent", config)
        
        # Create mock execution result
        from agents.province.models import ExecutedBehavior, ExecutionResult
        
        executed_behavior = ExecutedBehavior(
            behavior_type=BehaviorType.INFRASTRUCTURE_INVESTMENT,
            behavior_name="Road Improvement",
            parameters={'amount': 200},
            effects=BehaviorEffect(
                behavior_type=BehaviorType.INFRASTRUCTURE_INVESTMENT,
                behavior_name="Road Improvement",
                expenditure_change=200,
                development_change=1.5,
                loyalty_change=3
            ),
            execution_success=True,
            execution_message="Successfully completed road improvement project"
        )
        
        execution_result = ExecutionResult(
            province_id=1,
            month=8,
            year=2024,
            executed_behaviors=[executed_behavior],
            generated_events=[],
            total_effects=executed_behavior.effects,
            province_state_after={'loyalty': 63, 'stability': 72},
            execution_summary="Infrastructure project completed successfully"
        )
        
        decision = Decision(
            province_id=1,
            month=8,
            year=2024,
            behaviors=[
                BehaviorDefinition(
                    behavior_type=BehaviorType.INFRASTRUCTURE_INVESTMENT,
                    behavior_name="Road Improvement",
                    parameters={'amount': 200}
                )
            ],
            reasoning="Improve transportation infrastructure",
            risk_level=RiskLevel.LOW
        )
        
        province_state = {'loyalty': 60, 'stability': 70}
        
        quality_report = await agent._assess_execution_quality(
            execution_result, decision, province_state
        )
        
        print("   ✅ Quality assessment successful")
        print(f"   📈 Overall Score: {quality_report.overall_score:.2f}/1.0")
        print(f"   🎯 Effectiveness: {quality_report.effectiveness:.2f}")
        print(f"   💡 Efficiency: {quality_report.efficiency:.2f}")
        print(f"   📊 Impact: {quality_report.impact:.2f}")
        print(f"   🛡️  Risk Management: {quality_report.risk_management:.2f}")
        print(f"   🔧 Adaptability: {quality_report.adaptability:.2f}")
        print(f"   📋 Success Factors: {len(quality_report.success_factors)}")
        print(f"   ⚠️  Improvement Areas: {len(quality_report.improvement_recommendations)}")
        
    except Exception as e:
        print(f"   ❌ Quality assessment failed: {e}")
        return False
    
    return True


async def run_all_tests():
    """Run all tests and report results"""
    print("🚀 Enhanced ExecutionAgent Test Suite")
    print("=" * 80)
    
    test_results = []
    
    # Run tests
    test_results.append(await test_basic_functionality())
    test_results.append(await test_llm_enhanced_functionality())
    test_results.append(await test_quality_assessment())
    
    # Summary
    print("\n" + "=" * 80)
    print("📋 TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"Tests Passed: {passed}/{total}")
    print(f"Success Rate: {passed/total:.1%}")
    
    if passed == total:
        print("🎉 All tests passed! Enhanced ExecutionAgent is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
        return False


async def main():
    """Main test function"""
    try:
        success = await run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error during testing: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())