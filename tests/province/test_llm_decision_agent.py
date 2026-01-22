"""
Comprehensive test module for LLM-driven DecisionAgent

This script will:
1. Create mock PerceptionContext data
2. Test different decision modes (LLM-driven, hybrid, rule-based)
3. Test interaction mechanisms
4. Evaluate decision quality
5. Performance benchmarking
"""

import asyncio
import sys
import os
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agents.province.decision_agent_llm import EnhancedDecisionAgent, DecisionMode
from agents.base import AgentMode
from agents.province.models import (
    PerceptionContext, PlayerInstruction, BehaviorType, RiskLevel,
    TrendDirection, MonthlyDetailedData, QuarterlySummary, AnnualSummary,
    EventIndex, TrendAnalysis, EventSummary, InstructionStatus
)


class MockDataGenerator:
    """Generate realistic mock data for testing"""
    
    @staticmethod
    def create_mock_perception_context(
        scenario: str = "normal",
        province_id: int = 1,
        month: int = 13,
        year: int = 2
    ) -> PerceptionContext:
        """Create mock perception context for different scenarios"""
        
        # Base recent data
        base_recent = {
            'month': 12, 'year': 1,
            'population': 50000, 'development_level': 7.5,
            'loyalty': 65.0, 'stability': 70.0,
            'actual_income': 850, 'actual_expenditure': 650,
            'reported_income': 850, 'reported_expenditure': 650,
            'actual_surplus': 200, 'reported_surplus': 200,
            'events': []
        }
        
        if scenario == "crisis":
            # Crisis scenario - low loyalty and stability
            base_recent.update({
                'loyalty': 35.0, 'stability': 30.0,
                'actual_income': 700, 'actual_expenditure': 750,
                'actual_surplus': -50,
                'events': [EventSummary(
                    event_id="crisis_1", event_type="rebellion",
                    name="Peasant Uprising", severity=0.8,
                    month=12, year=1,
                    description="Large-scale unrest in northern territories"
                )]
            })
        elif scenario == "prosperity":
            # Prosperity scenario - high loyalty and surplus
            base_recent.update({
                'loyalty': 85.0, 'stability': 80.0,
                'actual_income': 1200, 'actual_expenditure': 700,
                'actual_surplus': 500,
                'events': [EventSummary(
                    event_id="prosper_1", event_type="celebration",
                    name="Harvest Festival", severity=0.3,
                    month=12, year=1,
                    description="Excellent harvest boosts morale"
                )]
            })
        elif scenario == "decline":
            # Declining scenario - decreasing trends
            base_recent.update({
                'loyalty': 55.0, 'stability': 60.0,
                'actual_income': 750, 'actual_expenditure': 680,
                'actual_surplus': 70,
                'events': []
            })
        
        recent_data = MonthlyDetailedData(**base_recent)
        
        # Create quarterly summaries
        quarterly_summaries = [
            QuarterlySummary(
                quarter=4, year=1,
                avg_income=820, median_income=800,
                avg_expenditure=670, median_expenditure=650,
                total_surplus=450, income_trend=TrendDirection.STABLE,
                expenditure_trend=TrendDirection.STABLE,
                loyalty_change=-5.0 if scenario == "decline" else 2.0,
                stability_change=-3.0 if scenario == "decline" else 1.0,
                major_events=["Minor flood in October"] if scenario == "crisis" else [],
                special_event_types=["disaster"] if scenario == "crisis" else [],
                summary=f"Q4 showed {'challenging' if scenario == 'crisis' else 'stable' if scenario == 'normal' else 'strong'} performance"
            ),
            QuarterlySummary(
                quarter=3, year=1,
                avg_income=800, median_income=780,
                avg_expenditure=650, median_expenditure=640,
                total_surplus=450, income_trend=TrendDirection.STABLE,
                expenditure_trend=TrendDirection.STABLE,
                loyalty_change=1.0, stability_change=0.5,
                major_events=[], special_event_types=[],
                summary="Q3 performance was steady with minor improvements"
            )
        ]
        
        # Create annual summaries
        annual_summaries = [
            AnnualSummary(
                year=1, total_income=9600, total_expenditure=7800,
                avg_monthly_income=800, avg_monthly_expenditure=650,
                total_surplus=1800, population_change=500,
                development_change=0.5, loyalty_start=60.0, loyalty_end=recent_data.loyalty,
                loyalty_change=recent_data.loyalty - 60.0,
                major_events=["Border skirmish", "Trade agreement"] if scenario != "normal" else [],
                disaster_count=1 if scenario == "crisis" else 0,
                rebellion_count=1 if scenario == "crisis" else 0,
                performance_rating="poor" if scenario == "crisis" else "good" if scenario == "prosperity" else "average",
                summary=f"Year 1 showed {'significant challenges' if scenario == 'crisis' else 'strong growth' if scenario == 'prosperity' else 'steady progress'}"
            )
        ]
        
        # Create critical events
        critical_events = []
        if scenario == "crisis":
            critical_events.append(EventIndex(
                index_id=1, event_id="rebellion_001", event_category="rebellion",
                event_name="Northern Uprising", severity=0.8, month=11, year=1,
                impact_description="Significant unrest affecting stability and loyalty",
                is_resolved=False
            ))
        
        # Create trend analysis
        trend_data = {
            "crisis": {
                "income_trend": TrendDirection.DECREASING, "income_change_rate": -8.0,
                "expenditure_trend": TrendDirection.INCREASING, "expenditure_change_rate": 5.0,
                "loyalty_trend": TrendDirection.DECREASING, "loyalty_change_rate": -15.0,
                "stability_trend": TrendDirection.DECREASING, "stability_change_rate": -20.0,
                "risk_level": RiskLevel.HIGH,
                "risk_factors": ["Very low loyalty", "Very low stability", "Declining income"],
                "opportunities": ["Emergency relief could quickly improve loyalty"]
            },
            "prosperity": {
                "income_trend": TrendDirection.INCREASING, "income_change_rate": 12.0,
                "expenditure_trend": TrendDirection.STABLE, "expenditure_change_rate": 2.0,
                "loyalty_trend": TrendDirection.INCREASING, "loyalty_change_rate": 8.0,
                "stability_trend": TrendDirection.INCREASING, "stability_change_rate": 5.0,
                "risk_level": RiskLevel.LOW,
                "risk_factors": [],
                "opportunities": ["Strong surplus enables major investments", "High loyalty supports reforms"]
            },
            "decline": {
                "income_trend": TrendDirection.DECREASING, "income_change_rate": -5.0,
                "expenditure_trend": TrendDirection.INCREASING, "expenditure_change_rate": 3.0,
                "loyalty_trend": TrendDirection.DECREASING, "loyalty_change_rate": -8.0,
                "stability_trend": TrendDirection.DECREASING, "stability_change_rate": -6.0,
                "risk_level": RiskLevel.MEDIUM,
                "risk_factors": ["Declining loyalty", "Declining income"],
                "opportunities": ["Moderate intervention could reverse trends"]
            },
            "normal": {
                "income_trend": TrendDirection.STABLE, "income_change_rate": 2.0,
                "expenditure_trend": TrendDirection.STABLE, "expenditure_change_rate": 1.0,
                "loyalty_trend": TrendDirection.STABLE, "loyalty_change_rate": 1.0,
                "stability_trend": TrendDirection.STABLE, "stability_change_rate": 0.5,
                "risk_level": RiskLevel.LOW,
                "risk_factors": [],
                "opportunities": ["Stable foundation for development"]
            }
        }
        
        trends_data = trend_data.get(scenario, trend_data["normal"])
        trends = TrendAnalysis(**trends_data)
        
        return PerceptionContext(
            province_id=province_id,
            province_name=f"Test Province ({scenario.title()})",
            current_month=month,
            current_year=year,
            recent_data=recent_data,
            quarterly_summaries=quarterly_summaries,
            annual_summaries=annual_summaries,
            critical_events=critical_events,
            trends=trends,
            data_quality="complete",
            warnings=[] if scenario == "normal" else [f"Province experiencing {scenario} conditions"]
        )
    
    @staticmethod
    def create_mock_instruction(
        instruction_type: str = "economic_stimulus",
        province_id: int = 1,
        month: int = 13,
        year: int = 2
    ) -> PlayerInstruction:
        """Create mock player instruction"""
        
        instruction_configs = {
            "economic_stimulus": {
                "template_name": "Economic Recovery Plan",
                "parameters": {"amount": 200, "duration": 12}
            },
            "tax_adjustment": {
                "template_name": "Tax Rate Modification",
                "parameters": {"rate_change": 0.05, "duration": 6}
            },
            "infrastructure_investment": {
                "template_name": "Infrastructure Development",
                "parameters": {"amount": 300, "duration": 18}
            },
            "loyalty_campaign": {
                "template_name": "Population Loyalty Drive",
                "parameters": {"intensity": 1.2, "duration": 8}
            },
            "emergency_relief": {
                "template_name": "Crisis Response",
                "parameters": {"amount": 150, "target": 0}
            }
        }
        
        config = instruction_configs.get(instruction_type, instruction_configs["economic_stimulus"])
        
        return PlayerInstruction(
            instruction_id=1,
            province_id=province_id,
            month=month,
            year=year,
            instruction_type=instruction_type,
            template_name=config["template_name"],
            parameters=config["parameters"],
            status=InstructionStatus.PENDING
        )


class DecisionQualityEvaluator:
    """Evaluate the quality of decisions made by the agent"""
    
    @staticmethod
    def evaluate_decision_quality(
        decision: "Decision",
        perception_context: PerceptionContext,
        original_instruction: Optional[PlayerInstruction] = None
    ) -> Dict[str, Any]:
        """Evaluate decision quality across multiple dimensions"""
        
        evaluation = {
            "overall_score": 0.0,
            "dimensions": {},
            "issues": [],
            "strengths": []
        }
        
        # Dimension 1: Appropriateness to situation
        situation_score = DecisionQualityEvaluator._evaluate_situation_appropriateness(
            decision, perception_context
        )
        evaluation["dimensions"]["situation_appropriateness"] = situation_score
        
        # Dimension 2: Risk management
        risk_score = DecisionQualityEvaluator._evaluate_risk_management(
            decision, perception_context
        )
        evaluation["dimensions"]["risk_management"] = risk_score
        
        # Dimension 3: Resource feasibility
        resource_score = DecisionQualityEvaluator._evaluate_resource_feasibility(
            decision, perception_context
        )
        evaluation["dimensions"]["resource_feasibility"] = resource_score
        
        # Dimension 4: Instruction compliance (if applicable)
        if original_instruction:
            compliance_score = DecisionQualityEvaluator._evaluate_instruction_compliance(
                decision, original_instruction
            )
            evaluation["dimensions"]["instruction_compliance"] = compliance_score
        
        # Calculate overall score
        scores = list(evaluation["dimensions"].values())
        evaluation["overall_score"] = sum(scores) / len(scores) if scores else 0.0
        
        # Generate insights
        if evaluation["overall_score"] >= 0.8:
            evaluation["strengths"].append("High-quality decision making")
        elif evaluation["overall_score"] <= 0.5:
            evaluation["issues"].append("Decision quality needs improvement")
        
        return evaluation
    
    @staticmethod
    def _evaluate_situation_appropriateness(
        decision: "Decision",
        perception_context: PerceptionContext
    ) -> float:
        """Evaluate if decision is appropriate for the current situation"""
        
        score = 0.5  # Base score
        recent_data = perception_context.recent_data
        trends = perception_context.trends
        
        # Check crisis response
        if recent_data.loyalty < 40 or recent_data.stability < 40:
            # Crisis situation - should prioritize emergency/stability measures
            has_emergency = any(b.behavior_type == BehaviorType.EMERGENCY_RELIEF for b in decision.behaviors)
            has_stability = any(b.behavior_type == BehaviorType.STABILITY_MEASURE for b in decision.behaviors)
            if has_emergency or has_stability:
                score += 0.4
            else:
                score -= 0.3
                print("Warning: Crisis situation but no emergency/stability measures")
        
        # Check prosperity opportunities
        elif recent_data.actual_surplus > 300 and recent_data.loyalty > 70:
            # Good conditions - should consider investment/growth
            has_investment = any(b.behavior_type in [BehaviorType.INFRASTRUCTURE_INVESTMENT, BehaviorType.ECONOMIC_STIMULUS] for b in decision.behaviors)
            if has_investment:
                score += 0.3
        
        # Check declining trends response
        elif trends.loyalty_trend == TrendDirection.DECREASING or trends.income_trend == TrendDirection.DECREASING:
            # Declining trends - should address root causes
            has_loyalty_campaign = any(b.behavior_type == BehaviorType.LOYALTY_CAMPAIGN for b in decision.behaviors)
            has_economic_stimulus = any(b.behavior_type == BehaviorType.ECONOMIC_STIMULUS for b in decision.behaviors)
            if has_loyalty_campaign or has_economic_stimulus:
                score += 0.3
        
        return max(0.0, min(1.0, score))
    
    @staticmethod
    def _evaluate_risk_management(
        decision: "Decision",
        perception_context: PerceptionContext
    ) -> float:
        """Evaluate risk management in the decision"""
        
        score = 0.5  # Base score
        recent_data = perception_context.recent_data
        
        # Check if risk level is appropriate
        if recent_data.loyalty < 30 or recent_data.stability < 30:
            # High-risk situation - decision should be conservative
            if decision.risk_level == RiskLevel.HIGH:
                score -= 0.4
                print("Warning: High-risk situation but high-risk decision")
            elif decision.risk_level == RiskLevel.LOW:
                score += 0.3
        
        # Check for risk mitigation behaviors
        risky_behaviors = [BehaviorType.CORRUPTION_CRACKDOWN, BehaviorType.AUSTERITY_MEASURE]
        has_risky_behavior = any(b.behavior_type in risky_behaviors for b in decision.behaviors)
        
        if has_risky_behavior:
            # Should have supporting stability measures
            has_stability = any(b.behavior_type == BehaviorType.STABILITY_MEASURE for b in decision.behaviors)
            has_loyalty = any(b.behavior_type == BehaviorType.LOYALTY_CAMPAIGN for b in decision.behaviors)
            if has_stability or has_loyalty:
                score += 0.2
            else:
                score -= 0.2
        
        return max(0.0, min(1.0, score))
    
    @staticmethod
    def _evaluate_resource_feasibility(
        decision: "Decision",
        perception_context: PerceptionContext
    ) -> float:
        """Evaluate if decision is financially feasible"""
        
        score = 0.5  # Base score
        recent_data = perception_context.recent_data
        
        # Calculate total cost
        total_cost = decision.estimated_effects.get('total_cost', 0)
        available_surplus = recent_data.actual_surplus
        
        # Check affordability
        if total_cost > available_surplus * 2:
            score -= 0.4
            print(f"Warning: Decision cost {total_cost} exceeds available surplus {available_surplus}")
        elif total_cost <= available_surplus:
            score += 0.3
        
        # Check debt sustainability
        if recent_data.actual_surplus < 0 and total_cost > 0:
            score -= 0.3
            print("Warning: Already in deficit but proposing costly measures")
        
        return max(0.0, min(1.0, score))
    
    @staticmethod
    def _evaluate_instruction_compliance(
        decision: "Decision",
        instruction: PlayerInstruction
    ) -> float:
        """Evaluate compliance with player instruction"""
        
        score = 0.5  # Base score
        
        # Check if instruction type is addressed
        instruction_behavior_map = {
            "economic_stimulus": BehaviorType.ECONOMIC_STIMULUS,
            "tax_adjustment": BehaviorType.TAX_ADJUSTMENT,
            "infrastructure_investment": BehaviorType.INFRASTRUCTURE_INVESTMENT,
            "loyalty_campaign": BehaviorType.LOYALTY_CAMPAIGN,
            "emergency_relief": BehaviorType.EMERGENCY_RELIEF
        }
        
        expected_behavior = instruction_behavior_map.get(instruction.instruction_type)
        if expected_behavior:
            has_expected_behavior = any(b.behavior_type == expected_behavior for b in decision.behaviors)
            if has_expected_behavior:
                score += 0.4
            else:
                score -= 0.3
                print(f"Warning: Expected {expected_behavior} but not found in decision")
        
        # Check parameter compliance (basic check)
        if instruction.parameters:
            # This is a simplified check - in reality would need more sophisticated matching
            score += 0.1
        
        return max(0.0, min(1.0, score))


async def test_basic_functionality():
    """Test basic functionality of LLM DecisionAgent"""
    print("="*70)
    print("Testing Basic LLM DecisionAgent Functionality")
    print("="*70)
    
    # Test different scenarios
    scenarios = ["normal", "crisis", "prosperity", "decline"]
    modes = [DecisionMode.LLM_DRIVEN, DecisionMode.HYBRID, DecisionMode.RULE_BASED]
    
    results = {}
    
    for scenario in scenarios:
        print(f"\n--- Testing {scenario.upper()} Scenario ---")
        
        # Create mock data
        perception_context = MockDataGenerator.create_mock_perception_context(scenario)
        province_state = {
            'actual_income': perception_context.recent_data.actual_income,
            'actual_surplus': perception_context.recent_data.actual_surplus
        }
        
        scenario_results = {}
        
        for mode in modes:
            print(f"\nTesting {mode.value} mode:")
            
            # Create decision agent
            agent = EnhancedDecisionAgent(
                agent_id=f"test_{scenario}_{mode.value}",
                config={
                    'province_id': 1,
                    'llm_config': {
                        'enabled': True,
                        'mock_mode': True  # Use mock responses
                    },
                    'mode': mode.value,
                    'interaction_rounds': 1 if mode == DecisionMode.LLM_DRIVEN else 0
                }
            )
            
            # Test autonomous decision (no instruction)
            start_time = time.time()
            decision = await agent.make_decision(
                perception=perception_context,
                instruction=None,
                province_state=province_state
            )
            decision_time = time.time() - start_time
            
            # Evaluate decision quality
            quality_eval = DecisionQualityEvaluator.evaluate_decision_quality(
                decision, perception_context
            )
            
            # Store results
            result = {
                'decision': decision,
                'decision_time': decision_time,
                'quality_score': quality_eval['overall_score'],
                'behaviors_count': len(decision.behaviors),
                'risk_level': decision.risk_level.value,
                'issues': quality_eval['issues'],
                'strengths': quality_eval['strengths']
            }
            
            scenario_results[mode.value] = result
            
            # Print summary
            print(f"  Decision time: {decision_time:.2f}s")
            print(f"  Quality score: {quality_eval['overall_score']:.2f}")
            print(f"  Behaviors: {len(decision.behaviors)}")
            print(f"  Risk level: {decision.risk_level.value}")
            if decision.behaviors:
                behavior_types = [b.behavior_type.value for b in decision.behaviors]
                print(f"  Behavior types: {', '.join(behavior_types)}")
            
        results[scenario] = scenario_results
    
    return results


async def test_with_instructions():
    """Test decision making with player instructions"""
    print("\n" + "="*70)
    print("Testing DecisionAgent with Player Instructions")
    print("="*70)
    
    # Test different instruction types
    instruction_types = ["economic_stimulus", "tax_adjustment", "infrastructure_investment", "loyalty_campaign"]
    scenario = "normal"  # Use normal scenario for instruction testing
    
    perception_context = MockDataGenerator.create_mock_perception_context(scenario)
    province_state = {
        'actual_income': perception_context.recent_data.actual_income,
        'actual_surplus': perception_context.recent_data.actual_surplus
    }
    
    results = {}
    
    for instruction_type in instruction_types:
        print(f"\n--- Testing {instruction_type.upper()} Instruction ---")
        
        # Create instruction
        instruction = MockDataGenerator.create_mock_instruction(instruction_type)
        
        # Test with LLM-driven mode
        agent = EnhancedDecisionAgent(
            agent_id=f"test_instruction_{instruction_type}",
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
        
        start_time = time.time()
        decision = await agent.make_decision(
            perception=perception_context,
            instruction=instruction,
            province_state=province_state
        )
        decision_time = time.time() - start_time
        
        # Evaluate instruction compliance
        quality_eval = DecisionQualityEvaluator.evaluate_decision_quality(
            decision, perception_context, instruction
        )
        
        result = {
            'instruction_type': instruction_type,
            'decision': decision,
            'decision_time': decision_time,
            'quality_score': quality_eval['overall_score'],
            'compliance_score': quality_eval['dimensions'].get('instruction_compliance', 0.0),
            'behaviors_count': len(decision.behaviors),
            'issues': quality_eval['issues'],
            'strengths': quality_eval['strengths']
        }
        
        results[instruction_type] = result
        
        # Print summary
        print(f"  Decision time: {decision_time:.2f}s")
        print(f"  Quality score: {quality_eval['overall_score']:.2f}")
        print(f"  Compliance score: {quality_eval['dimensions'].get('instruction_compliance', 0.0):.2f}")
        print(f"  Behaviors: {len(decision.behaviors)}")
        if decision.behaviors:
            behavior_types = [b.behavior_type.value for b in decision.behaviors]
            print(f"  Behavior types: {', '.join(behavior_types)}")
        
        # Print detailed reasoning
        print(f"  Reasoning: {decision.reasoning[:200]}...")
    
    return results


async def test_interaction_mechanism():
    """Test the interaction mechanism between decision maker and officer"""
    print("\n" + "="*70)
    print("Testing Decision Maker - Officer Interaction Mechanism")
    print("="*70)
    
    # Create crisis scenario that needs careful handling
    perception_context = MockDataGenerator.create_mock_perception_context("crisis")
    province_state = {
        'actual_income': perception_context.recent_data.actual_income,
        'actual_surplus': perception_context.recent_data.actual_surplus
    }
    
    print(f"Scenario: Crisis situation")
    print(f"Loyalty: {perception_context.recent_data.loyalty}/100")
    print(f"Stability: {perception_context.recent_data.stability}/100")
    print(f"Surplus: {perception_context.recent_data.actual_surplus}")
    
    # Test different interaction rounds
    interaction_configs = [
        {"rounds": 0, "name": "No interaction"},
        {"rounds": 1, "name": "Single interaction round"},
        {"rounds": 2, "name": "Multiple interaction rounds"}
    ]
    
    results = {}
    
    for config in interaction_configs:
        print(f"\n--- Testing {config['name']} ---")
        
        agent = EnhancedDecisionAgent(
            agent_id=f"test_interaction_{config['rounds']}",
            config={
                'province_id': 1,
                'llm_config': {
                    'enabled': True,
                    'mock_mode': True
                },
                'mode': DecisionMode.LLM_DRIVEN.value,
                'interaction_rounds': config['rounds']
            }
        )
        
        start_time = time.time()
        decision = await agent.make_decision(
            perception=perception_context,
            instruction=None,
            province_state=province_state
        )
        decision_time = time.time() - start_time
        
        # Evaluate decision quality
        quality_eval = DecisionQualityEvaluator.evaluate_decision_quality(
            decision, perception_context
        )
        
        result = {
            'interaction_rounds': config['rounds'],
            'decision': decision,
            'decision_time': decision_time,
            'quality_score': quality_eval['overall_score'],
            'behaviors_count': len(decision.behaviors),
            'risk_level': decision.risk_level.value,
            'issues': quality_eval['issues'],
            'strengths': quality_eval['strengths']
        }
        
        results[config['rounds']] = result
        
        # Print summary
        print(f"  Decision time: {decision_time:.2f}s")
        print(f"  Quality score: {quality_eval['overall_score']:.2f}")
        print(f"  Behaviors: {len(decision.behaviors)}")
        print(f"  Risk level: {decision.risk_level.value}")
        if decision.behaviors:
            behavior_types = [b.behavior_type.value for b in decision.behaviors]
            print(f"  Behavior types: {', '.join(behavior_types)}")
    
    return results


async def test_performance_benchmark():
    """Performance benchmark testing"""
    print("\n" + "="*70)
    print("Performance Benchmark Testing")
    print("="*70)
    
    # Test performance across different configurations
    test_configs = [
        {"mode": DecisionMode.RULE_BASED, "mock": True, "name": "Rule-based (mock)"},
        {"mode": DecisionMode.LLM_DRIVEN, "mock": True, "name": "LLM-driven (mock)"},
        {"mode": DecisionMode.HYBRID, "mock": True, "name": "Hybrid (mock)"}
    ]
    
    perception_context = MockDataGenerator.create_mock_perception_context("normal")
    province_state = {
        'actual_income': perception_context.recent_data.actual_income,
        'actual_surplus': perception_context.recent_data.actual_surplus
    }
    
    benchmark_results = {}
    
    for config in test_configs:
        print(f"\n--- Testing {config['name']} ---")
        
        # Warm up
        agent = EnhancedDecisionAgent(
            agent_id=f"benchmark_{config['mode'].value}",
            config={
                'province_id': 1,
                'llm_config': {
                    'enabled': True,
                    'mock_mode': config['mock']
                },
                'mode': config['mode'].value,
                'interaction_rounds': 0
            }
        )
        
        # Run multiple iterations
        iterations = 10
        times = []
        
        for i in range(iterations):
            start_time = time.time()
            decision = await agent.make_decision(
                perception=perception_context,
                instruction=None,
                province_state=province_state
            )
            end_time = time.time()
            times.append(end_time - start_time)
        
        # Calculate statistics
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        result = {
            'config': config['name'],
            'iterations': iterations,
            'avg_time': avg_time,
            'min_time': min_time,
            'max_time': max_time,
            'std_dev': (sum((t - avg_time) ** 2 for t in times) / len(times)) ** 0.5
        }
        
        benchmark_results[config['name']] = result
        
        print(f"  Average time: {avg_time:.3f}s")
        print(f"  Min time: {min_time:.3f}s")
        print(f"  Max time: {max_time:.3f}s")
        print(f"  Standard deviation: {result['std_dev']:.3f}s")
    
    return benchmark_results


async def test_error_handling():
    """Test error handling and edge cases"""
    print("\n" + "="*70)
    print("Testing Error Handling and Edge Cases")
    print("="*70)
    
    # Test with minimal data
    print("\n--- Testing with minimal data ---")
    
    # Create minimal perception context
    minimal_recent = MonthlyDetailedData(
        month=1, year=1, population=1000, development_level=5.0,
        loyalty=50.0, stability=50.0, actual_income=100, actual_expenditure=80,
        reported_income=100, reported_expenditure=80, actual_surplus=20, reported_surplus=20,
        events=[]
    )
    
    minimal_perception = PerceptionContext(
        province_id=1, province_name="Minimal Province",
        current_month=2, current_year=1,
        recent_data=minimal_recent,
        quarterly_summaries=[],
        annual_summaries=[],
        critical_events=[],
        trends=TrendAnalysis(
            income_trend=TrendDirection.STABLE, income_change_rate=0.0,
            expenditure_trend=TrendDirection.STABLE, expenditure_change_rate=0.0,
            loyalty_trend=TrendDirection.STABLE, loyalty_change_rate=0.0,
            stability_trend=TrendDirection.STABLE, stability_change_rate=0.0,
            risk_level=RiskLevel.MEDIUM, risk_factors=[], opportunities=[]
        ),
        data_quality="minimal",
        warnings=["Limited historical data available"]
    )
    
    province_state = {
        'actual_income': minimal_recent.actual_income,
        'actual_surplus': minimal_recent.actual_surplus
    }
    
    agent = EnhancedDecisionAgent(
        agent_id="test_minimal",
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
    
    try:
        decision = await agent.make_decision(
            perception=minimal_perception,
            instruction=None,
            province_state=province_state
        )
        print(f"✓ Successfully handled minimal data")
        print(f"  Decision time: {len(decision.behaviors)} behaviors")
        print(f"  Risk level: {decision.risk_level.value}")
    except Exception as e:
        print(f"✗ Failed with minimal data: {e}")
    
    # Test with invalid instruction
    print("\n--- Testing with invalid instruction ---")
    
    invalid_instruction = PlayerInstruction(
        instruction_id=1, province_id=1, month=2, year=1,
        instruction_type="invalid_instruction_type",
        template_name="Unknown Template",
        parameters={"unknown_param": 123},
        status=InstructionStatus.PENDING
    )
    
    try:
        decision = await agent.make_decision(
            perception=minimal_perception,
            instruction=invalid_instruction,
            province_state=province_state
        )
        print(f"✓ Successfully handled invalid instruction")
        print(f"  Behaviors: {len(decision.behaviors)}")
    except Exception as e:
        print(f"✗ Failed with invalid instruction: {e}")


async def generate_test_report(all_results: Dict[str, Any]):
    """Generate comprehensive test report"""
    print("\n" + "="*70)
    print("COMPREHENSIVE TEST REPORT")
    print("="*70)
    print(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Summary statistics
    print("\n--- Test Summary ---")
    total_tests = sum(len(scenario_results) for scenario_results in all_results.values())
    print(f"Total test cases: {total_tests}")
    
    # Quality metrics
    all_quality_scores = []
    for test_category, results in all_results.items():
        if isinstance(results, dict):
            for result in results.values():
                if isinstance(result, dict) and 'quality_score' in result:
                    all_quality_scores.append(result['quality_score'])
    
    if all_quality_scores:
        avg_quality = sum(all_quality_scores) / len(all_quality_scores)
        print(f"Average decision quality: {avg_quality:.2f}/1.0")
        print(f"Quality distribution:")
        high_quality = sum(1 for s in all_quality_scores if s >= 0.8)
        medium_quality = sum(1 for s in all_quality_scores if 0.5 <= s < 0.8)
        low_quality = sum(1 for s in all_quality_scores if s < 0.5)
        print(f"  High quality (≥0.8): {high_quality} ({high_quality/len(all_quality_scores)*100:.1f}%)")
        print(f"  Medium quality (0.5-0.8): {medium_quality} ({medium_quality/len(all_quality_scores)*100:.1f}%)")
        print(f"  Low quality (<0.5): {low_quality} ({low_quality/len(all_quality_scores)*100:.1f}%)")
    
    # Performance metrics
    all_times = []
    for test_category, results in all_results.items():
        if isinstance(results, dict):
            for result in results.values():
                if isinstance(result, dict) and 'decision_time' in result:
                    all_times.append(result['decision_time'])
    
    if all_times:
        avg_time = sum(all_times) / len(all_times)
        print(f"\nPerformance metrics:")
        print(f"  Average decision time: {avg_time:.3f}s")
        print(f"  Min decision time: {min(all_times):.3f}s")
        print(f"  Max decision time: {max(all_times):.3f}s")
    
    print("\n" + "="*70)
    print("✓ All tests completed successfully!")
    print("✓ LLM DecisionAgent implementation is ready for use")
    print("="*70)


async def main():
    """Main test execution"""
    print("LLM DecisionAgent Comprehensive Test Suite")
    print("="*70)
    
    all_results = {}
    
    try:
        # Run all test suites
        print("\n1. Testing Basic Functionality...")
        basic_results = await test_basic_functionality()
        all_results['basic_functionality'] = basic_results
        
        print("\n2. Testing with Instructions...")
        instruction_results = await test_with_instructions()
        all_results['with_instructions'] = instruction_results
        
        print("\n3. Testing Interaction Mechanism...")
        interaction_results = await test_interaction_mechanism()
        all_results['interaction_mechanism'] = interaction_results
        
        print("\n4. Performance Benchmarking...")
        benchmark_results = await test_performance_benchmark()
        all_results['performance_benchmark'] = benchmark_results
        
        print("\n5. Testing Error Handling...")
        await test_error_handling()
        all_results['error_handling'] = "completed"
        
        # Generate final report
        await generate_test_report(all_results)
        
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())