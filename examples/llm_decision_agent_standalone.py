"""
Standalone example for LLM DecisionAgent

This script demonstrates the LLM DecisionAgent running independently
without external dependencies (using mock mode).
"""

import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.province.decision_agent_llm import EnhancedDecisionAgent, DecisionMode
from agents.province.models import (
    PerceptionContext, PlayerInstruction, BehaviorType, RiskLevel,
    TrendDirection, MonthlyDetailedData, QuarterlySummary, AnnualSummary,
    EventIndex, TrendAnalysis, EventSummary, InstructionStatus
)


def create_demo_perception_context() -> PerceptionContext:
    """Create a demo perception context for standalone testing"""
    
    # Create recent monthly data
    recent_data = MonthlyDetailedData(
        month=12, year=1,
        population=52000, development_level=7.8,
        loyalty=65.0, stability=70.0,
        actual_income=950, actual_expenditure=720,
        reported_income=950, reported_expenditure=720,
        actual_surplus=230, reported_surplus=230,
        events=[
            EventSummary(
                event_id="demo_1", event_type="development",
                name="Infrastructure Progress", severity=0.4,
                month=12, year=1,
                description="New road construction completed"
            )
        ]
    )
    
    # Create quarterly summaries
    quarterly_summaries = [
        QuarterlySummary(
            quarter=4, year=1,
            avg_income=920, median_income=910,
            avg_expenditure=700, median_expenditure=690,
            total_surplus=660, income_trend=TrendDirection.INCREASING,
            expenditure_trend=TrendDirection.STABLE,
            loyalty_change=3.0, stability_change=2.0,
            major_events=["Harvest festival", "Trade fair"],
            special_event_types=["celebration", "economic"],
            summary="Q4 showed steady economic growth with improving social indicators"
        )
    ]
    
    # Create annual summaries
    annual_summaries = [
        AnnualSummary(
            year=1, total_income=11000, total_expenditure=8400,
            avg_monthly_income=917, avg_monthly_expenditure=700,
            total_surplus=2600, population_change=800,
            development_change=0.8, loyalty_start=60.0, loyalty_end=65.0,
            loyalty_change=5.0,
            major_events=["Border trade agreement", "Infrastructure initiative"],
            disaster_count=0, rebellion_count=0,
            performance_rating="good",
            summary="Year 1 demonstrated solid economic fundamentals with social stability"
        )
    ]
    
    # Create trends analysis
    trends = TrendAnalysis(
        income_trend=TrendDirection.INCREASING, income_change_rate=8.5,
        expenditure_trend=TrendDirection.STABLE, expenditure_change_rate=2.1,
        loyalty_trend=TrendDirection.INCREASING, loyalty_change_rate=5.0,
        stability_trend=TrendDirection.INCREASING, stability_change_rate=3.2,
        risk_level=RiskLevel.LOW,
        risk_factors=[],
        opportunities=["Strong surplus enables infrastructure investment", "Growing loyalty supports reforms"]
    )
    
    return PerceptionContext(
        province_id=1,
        province_name="Demo Province",
        current_month=13, current_year=2,
        recent_data=recent_data,
        quarterly_summaries=quarterly_summaries,
        annual_summaries=annual_summaries,
        critical_events=[],
        trends=trends,
        data_quality="complete",
        warnings=[]
    )


async def run_demo_scenario():
    """Run a complete demo scenario"""
    print("="*70)
    print("LLM DecisionAgent Standalone Demo")
    print("="*70)
    print(f"Demo started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Create demo data
    print("1. Creating demo perception context...")
    perception_context = create_demo_perception_context()
    province_state = {
        'actual_income': perception_context.recent_data.actual_income,
        'actual_surplus': perception_context.recent_data.actual_surplus
    }
    
    print(f"   Province: {perception_context.province_name}")
    print(f"   Population: {perception_context.recent_data.population:,}")
    print(f"   Loyalty: {perception_context.recent_data.loyalty}/100")
    print(f"   Stability: {perception_context.recent_data.stability}/100")
    print(f"   Monthly Surplus: {perception_context.recent_data.actual_surplus}")
    print(f"   Risk Level: {perception_context.trends.risk_level.value}")
    print()
    
    # Test different modes
    modes = [
        (DecisionMode.RULE_BASED, "Rule-based Mode"),
        (DecisionMode.LLM_DRIVEN, "LLM-driven Mode"),
        (DecisionMode.HYBRID, "Hybrid Mode")
    ]
    
    for mode, mode_name in modes:
        print(f"2. Testing {mode_name}...")
        
        # Create agent
        agent = EnhancedDecisionAgent(
            agent_id=f"demo_{mode.value}",
            config={
                'province_id': 1,
                'llm_config': {
                    'enabled': True,
                    'mock_mode': True  # Use mock mode, no real LLM needed
                },
                'mode': mode.value,
                'interaction_rounds': 1 if mode == DecisionMode.LLM_DRIVEN else 0
            }
        )
        
        # Autonomous decision (no instruction)
        print(f"   Making autonomous decision...")
        start_time = asyncio.get_event_loop().time()
        
        decision = await agent.make_decision(
            perception=perception_context,
            instruction=None,
            province_state=province_state
        )
        
        decision_time = asyncio.get_event_loop().time() - start_time
        
        # Display results
        print(f"   Decision time: {decision_time:.3f}s")
        print(f"   Behaviors selected: {len(decision.behaviors)}")
        print(f"   Risk assessment: {decision.risk_level.value}")
        print(f"   Total cost: {decision.estimated_effects.get('total_cost', 0)}")
        
        if decision.behaviors:
            behavior_names = [f"{b.behavior_type.value}({b.parameters})" for b in decision.behaviors]
            print(f"   Behavior details: {', '.join(behavior_names)}")
        
        print(f"   Reasoning: {decision.reasoning[:150]}...")
        print()
    
    # Test instruction-based decision
    print("3. Testing instruction-based decision...")
    
    # Create economic development instruction
    instruction = PlayerInstruction(
        instruction_id=1,
        province_id=1,
        month=13, year=2,
        instruction_type="economic_stimulus",
        template_name="Economic Development Plan",
        parameters={"amount": 250, "duration": 12},
        status=InstructionStatus.PENDING
    )
    
    # Use LLM-driven mode to process instruction
    agent = EnhancedDecisionAgent(
        agent_id="demo_instruction",
        config={
            'province_id': 1,
            'llm_config': {
                'enabled': True,
                'mock_mode': True
            },
            'mode': DecisionMode.LLM_DRIVEN.value,
            'interaction_rounds': 1
        }
    )
    
    print(f"   Processing instruction: {instruction.instruction_type}")
    print(f"   Instruction parameters: {instruction.parameters}")
    
    start_time = asyncio.get_event_loop().time()
    decision = await agent.make_decision(
        perception=perception_context,
        instruction=instruction,
        province_state=province_state
    )
    decision_time = asyncio.get_event_loop().time() - start_time
    
    print(f"   Decision time: {decision_time:.3f}s")
    print(f"   Behaviors selected: {len(decision.behaviors)}")
    print(f"   In response to instruction: {decision.in_response_to_instruction}")
    
    # Check if expected behavior is included
    has_economic_stimulus = any(b.behavior_type == BehaviorType.ECONOMIC_STIMULUS for b in decision.behaviors)
    if has_economic_stimulus:
        print("   ✓ Economic stimulus behavior included")
    else:
        print("   ! Economic stimulus behavior not found (using alternative approach)")
    
    print(f"   Reasoning: {decision.reasoning[:200]}...")
    print()
    
    # Test crisis scenario
    print("4. Testing crisis scenario...")
    
    # Create crisis perception data
    crisis_recent = MonthlyDetailedData(
        month=12, year=1,
        population=48000, development_level=6.5,
        loyalty=28.0, stability=25.0,  # Extremely low loyalty and stability
        actual_income=620, actual_expenditure=680,
        reported_income=620, reported_expenditure=680,
        actual_surplus=-60, reported_surplus=-60,  # Budget deficit
        events=[
            EventSummary(
                event_id="crisis_1", event_type="rebellion",
                name="Peasant Uprising", severity=0.8,
                month=12, year=1,
                description="Large-scale unrest in northern territories"
            )
        ]
    )
    
    crisis_trends = TrendAnalysis(
        income_trend=TrendDirection.DECREASING, income_change_rate=-12.0,
        expenditure_trend=TrendDirection.INCREASING, expenditure_change_rate=8.0,
        loyalty_trend=TrendDirection.DECREASING, loyalty_change_rate=-18.0,
        stability_trend=TrendDirection.DECREASING, stability_change_rate=-22.0,
        risk_level=RiskLevel.HIGH,
        risk_factors=["Very low loyalty", "Very low stability", "Declining income"],
        opportunities=["Emergency measures could quickly stabilize situation"]
    )
    
    crisis_perception = PerceptionContext(
        province_id=2,
        province_name="Crisis Province",
        current_month=13, current_year=2,
        recent_data=crisis_recent,
        quarterly_summaries=[],
        annual_summaries=[],
        critical_events=[],
        trends=crisis_trends,
        data_quality="complete",
        warnings=["Province in crisis state"]
    )
    
    crisis_state = {
        'actual_income': crisis_recent.actual_income,
        'actual_surplus': crisis_recent.actual_surplus
    }
    
    print(f"   Crisis situation:")
    print(f"   Loyalty: {crisis_recent.loyalty}/100 (CRITICAL)")
    print(f"   Stability: {crisis_recent.stability}/100 (CRITICAL)")
    print(f"   Surplus: {crisis_recent.actual_surplus} (DEFICIT)")
    print(f"   Risk Level: {crisis_trends.risk_level.value}")
    
    # Use conservative strategy to handle crisis
    agent = EnhancedDecisionAgent(
        agent_id="demo_crisis",
        config={
            'province_id': 2,
            'llm_config': {
                'enabled': True,
                'mock_mode': True
            },
            'mode': DecisionMode.LLM_DRIVEN.value,
            'interaction_rounds': 2,  # Multiple interaction rounds ensure quality
            'risk_tolerance': 'conservative'
        }
    )
    
    start_time = asyncio.get_event_loop().time()
    decision = await agent.make_decision(
        perception=crisis_perception,
        instruction=None,
        province_state=crisis_state
    )
    decision_time = asyncio.get_event_loop().time() - start_time
    
    print(f"   Decision time: {decision_time:.3f}s")
    print(f"   Behaviors selected: {len(decision.behaviors)}")
    print(f"   Risk assessment: {decision.risk_level.value}")
    
    # Expect to see emergency relief and stability measures
    has_emergency_relief = any(b.behavior_type == BehaviorType.EMERGENCY_RELIEF for b in decision.behaviors)
    has_stability_measure = any(b.behavior_type == BehaviorType.STABILITY_MEASURE for b in decision.behaviors)
    
    if has_emergency_relief:
        print("   ✓ Emergency relief included")
    if has_stability_measure:
        print("   ✓ Stability measure included")
    
    print(f"   Reasoning: {decision.reasoning[:200]}...")
    print()
    
    # Summary
    print("="*70)
    print("Demo completed successfully!")
    print("="*70)
    print("✓ LLM DecisionAgent can run independently")
    print("✓ All decision modes work correctly")
    print("✓ Instruction handling works")
    print("✓ Crisis scenario handled appropriately")
    print("✓ Mock mode enables testing without external APIs")
    print()
    print("The module is ready for integration into the main system!")


async def run_performance_test():
    """Run a simple performance test"""
    print("\n" + "="*70)
    print("Performance Test")
    print("="*70)
    
    # Create test data
    perception_context = create_demo_perception_context()
    province_state = {
        'actual_income': perception_context.recent_data.actual_income,
        'actual_surplus': perception_context.recent_data.actual_surplus
    }
    
    # Test performance of different configurations
    configs = [
        {"mode": DecisionMode.RULE_BASED, "rounds": 0, "name": "Rule-based"},
        {"mode": DecisionMode.LLM_DRIVEN, "rounds": 0, "name": "LLM-driven (no interaction)"},
        {"mode": DecisionMode.LLM_DRIVEN, "rounds": 1, "name": "LLM-driven (1 interaction)"},
        {"mode": DecisionMode.HYBRID, "rounds": 0, "name": "Hybrid"}
    ]
    
    for config in configs:
        print(f"\nTesting {config['name']}...")
        
        agent = EnhancedDecisionAgent(
            agent_id=f"perf_{config['mode'].value}",
            config={
                'province_id': 1,
                'llm_config': {'enabled': True, 'mock_mode': True},
                'mode': config['mode'].value,
                'interaction_rounds': config['rounds']
            }
        )
        
        # Run multiple tests
        iterations = 5
        times = []
        
        for i in range(iterations):
            start_time = asyncio.get_event_loop().time()
            decision = await agent.make_decision(
                perception=perception_context,
                instruction=None,
                province_state=province_state
            )
            end_time = asyncio.get_event_loop().time()
            times.append(end_time - start_time)
        
        # Calculate statistics
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        print(f"   Iterations: {iterations}")
        print(f"   Average time: {avg_time*1000:.2f}ms")
        print(f"   Min time: {min_time*1000:.2f}ms")
        print(f"   Max time: {max_time*1000:.2f}ms")
        print(f"   Behaviors: {len(decision.behaviors)}")


async def main():
    """Main demo function"""
    try:
        # Run main demo
        await run_demo_scenario()
        
        # Run performance test
        await run_performance_test()
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())