#!/usr/bin/env python3
"""
Three-Agent Pipeline Demo Script

Demonstrates the complete Perception -> Decision -> Execution pipeline
using real LLM API or mock mode.

Usage:
    # Use built-in scenario
    python demo_three_agent_pipeline.py --scenario normal

    # Load from JSON file
    python demo_three_agent_pipeline.py --file data.json --output results.json

    # Verbose output
    python demo_three_agent_pipeline.py --scenario crisis --verbose

    # Use real API
    python demo_three_agent_pipeline.py --scenario prosperity --api-key YOUR_KEY
"""

import argparse
import asyncio
import json
import sys
import time
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from enum import Enum

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config_loader import get_config, init_config
from agents.province.perception_agent import PerceptionAgent
from agents.province.decision_agent_llm import EnhancedDecisionAgent
from agents.province.enhanced_execution_agent import EnhancedExecutionAgent
from agents.province.enhanced_execution_models import ExecutionContext
from agents.province.models import PerceptionContext, Decision
from tests.pipeline_mock_data import MockDataGenerator, get_scenario_description, list_scenarios
from db.database import Database


class DataSource(str, Enum):
    """Data source type"""
    MOCK_NORMAL = "mock_normal"
    MOCK_CRISIS = "mock_crisis"
    MOCK_PROSPERITY = "mock_prosperity"
    MOCK_GROWTH = "mock_growth"
    MOCK_DECLINE = "mock_decline"
    JSON_FILE = "json_file"


class PipelineResult:
    """Result of the three-agent pipeline execution"""

    def __init__(
        self,
        pipeline_id: str,
        timestamp: str,
        province_id: int,
        scenario: str,
        perception_context: PerceptionContext,
        decision: Decision,
        execution_result: Any,
        performance_stats: 'PipelinePerformanceStats',
        quality_summary: str,
        overall_success: bool
    ):
        self.pipeline_id = pipeline_id
        self.timestamp = timestamp
        self.province_id = province_id
        self.scenario = scenario
        self.perception_context = perception_context
        self.decision = decision
        self.execution_result = execution_result
        self.performance_stats = performance_stats
        self.quality_summary = quality_summary
        self.overall_success = overall_success

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "pipeline_id": self.pipeline_id,
            "timestamp": self.timestamp,
            "province_id": self.province_id,
            "scenario": self.scenario,
            "success": self.overall_success,
            "quality_summary": self.quality_summary,
            "performance": self.performance_stats.to_dict(),
            "perception_context": self.perception_context.model_dump(),
            "decision": self.decision.model_dump(),
            "execution_result": self._serialize_execution_result()
        }

    def _serialize_execution_result(self) -> Dict[str, Any]:
        """Serialize execution result to dict"""
        if hasattr(self.execution_result, 'model_dump'):
            return self.execution_result.model_dump()
        elif hasattr(self.execution_result, 'execution_result'):
            # EnhancedExecutionResult
            return {
                "execution_result": self.execution_result.execution_result,
                "quality_report": self.execution_result.quality_report.model_dump(),
                "overall_score": self.execution_result.quality_report.overall_score
            }
        else:
            return str(self.execution_result)


class PipelinePerformanceStats:
    """Performance statistics for pipeline execution"""

    def __init__(self):
        self.stage_times: Dict[str, float] = {}
        self.api_calls: Dict[str, int] = {}
        self.tokens_used: Dict[str, int] = {}
        self.errors: List[str] = []

    def add_stage_time(self, stage: str, duration: float) -> None:
        self.stage_times[stage] = duration

    def add_api_call(self, stage: str) -> None:
        self.api_calls[stage] = self.api_calls.get(stage, 0) + 1

    def add_tokens(self, stage: str, tokens: int) -> None:
        self.tokens_used[stage] = self.tokens_used.get(stage, 0) + tokens

    def add_error(self, error: str) -> None:
        self.errors.append(error)

    @property
    def total_time(self) -> float:
        return sum(self.stage_times.values())

    @property
    def total_api_calls(self) -> int:
        return sum(self.api_calls.values())

    @property
    def total_tokens(self) -> int:
        return sum(self.tokens_used.values())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_time_seconds": round(self.total_time, 2),
            "stage_times": {k: round(v, 2) for k, v in self.stage_times.items()},
            "api_calls": self.api_calls,
            "tokens_used": self.tokens_used,
            "total_api_calls": self.total_api_calls,
            "total_tokens": self.total_tokens,
            "errors": self.errors
        }


class PipelineDemo:
    """Demo class for three-agent pipeline"""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.config = self._setup_config()
        self.db = self._setup_database()
        self.stats = PipelinePerformanceStats()

    def _setup_config(self):
        """Setup configuration"""
        config_path = self.args.config or "config.yaml"

        # Override API key if provided
        if self.args.api_key:
            os.environ['ANTHROPIC_API_KEY'] = self.args.api_key

        config = init_config(config_path)

        # Enable LLM for demo if requested
        if self.args.use_llm:
            config.set('llm.enabled', True)
            config.set('llm.mock_mode', False)

        return config

    def _setup_database(self) -> Database:
        """Setup in-memory database for demo"""
        db_path = ":memory:" if self.args.use_memory_db else "demo_pipeline.db"
        return Database(db_path)

    def _get_llm_agent_config(self, agent_type: str) -> Dict[str, Any]:
        """Get LLM configuration for agents"""
        return {
            'province_id': 1,
            'llm_config': {
                'enabled': self.args.use_llm,
                'mock_mode': not self.args.use_llm,
                'provider': self.config.get('llm.provider', 'anthropic'),
                'api_key': self.config.get('llm.api_key'),
                'base_url': self.config.get('llm.base_url'),
                'model': self.config.get('llm.model', 'claude-3-5-sonnet-20241022'),
                'max_tokens': self.config.get('llm.max_tokens', 4096),
                'temperature': self.config.get('llm.temperature', 0.3)
            },
            'mode': 'llm_assisted',
            'interaction_rounds': 0,  # Disable interaction rounds for faster demo
            'execution_mode': 'llm_enhanced',
            'risk_tolerance': 'moderate'
        }

    async def run_pipeline(
        self,
        data_source: DataSource,
        scenario: Optional[str] = None,
        json_file: Optional[str] = None
    ) -> PipelineResult:
        """
        Run the complete three-agent pipeline

        Args:
            data_source: Source of input data
            scenario: Scenario type for mock data
            json_file: Path to JSON file with input data

        Returns:
            PipelineResult with all stage outputs
        """
        print("\n" + "=" * 70)
        print("THREE-AGENT PIPELINE DEMO")
        print("=" * 70)
        print(f"Data Source: {data_source.value}")
        if scenario:
            print(f"Scenario: {scenario} - {get_scenario_description(scenario)}")
        print(f"LLM Mode: {'Real API' if self.args.use_llm else 'Mock'}")
        print("=" * 70)

        # Generate pipeline ID
        pipeline_id = f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Get input data
        if json_file and data_source == DataSource.JSON_FILE:
            perception_context, province_state = await self._load_from_json(json_file)
            scenario = "json_file"
        else:
            perception_context, province_state = self._create_mock_data(scenario or 'normal')

        print(f"\nProvince: {perception_context.province_name}")
        print(f"Current Date: Month {perception_context.current_month}, Year {perception_context.current_year}")

        # Stage 1: Perception
        perception_context = await self._run_perception_stage(perception_context, province_state)
        if perception_context is None:
            return self._create_failed_result(pipeline_id, scenario or data_source.value)

        # Stage 2: Decision
        decision = await self._run_decision_stage(perception_context, province_state)
        if decision is None:
            return self._create_failed_result(pipeline_id, scenario or data_source.value)

        # Stage 3: Execution
        execution_result = await self._run_execution_stage(
            perception_context, decision, province_state
        )

        # Generate quality summary
        quality_summary = self._generate_quality_summary(
            perception_context, decision, execution_result
        )

        # Determine overall success
        overall_success = (
            perception_context is not None and
            decision is not None and
            execution_result is not None and
            len(self.stats.errors) == 0
        )

        return PipelineResult(
            pipeline_id=pipeline_id,
            timestamp=datetime.now().isoformat(),
            province_id=perception_context.province_id,
            scenario=scenario or data_source.value,
            perception_context=perception_context,
            decision=decision,
            execution_result=execution_result,
            performance_stats=self.stats,
            quality_summary=quality_summary,
            overall_success=overall_success
        )

    def _create_mock_data(self, scenario: str) -> tuple[PerceptionContext, Dict[str, Any]]:
        """Create mock data for testing"""
        perception_context = MockDataGenerator.create_perception_context(
            scenario=scenario,
            province_id=1,
            month=1,
            year=1
        )
        province_state = MockDataGenerator.create_province_state(scenario)
        return perception_context, province_state

    async def _load_from_json(self, json_file: str) -> tuple[PerceptionContext, Dict[str, Any]]:
        """Load data from JSON file"""
        with open(json_file, 'r') as f:
            data = json.load(f)

        perception_context = PerceptionContext(**data['perception_context'])
        province_state = data['province_state']
        return perception_context, province_state

    async def _run_perception_stage(
        self,
        perception_context: PerceptionContext,
        province_state: Dict[str, Any]
    ) -> Optional[PerceptionContext]:
        """Run Stage 1: Perception"""
        print("\n" + "=" * 70)
        print("STAGE 1: PERCEPTION")
        print("=" * 70)

        start_time = time.time()

        try:
            # Initialize PerceptionAgent
            agent = PerceptionAgent(
                agent_id="demo_perception",
                config=self._get_llm_agent_config('perception'),
                db=self.db
            )

            # Run perception (use the mock context directly for demo)
            # In production, this would analyze database data
            duration = time.time() - start_time
            self.stats.add_stage_time('perception', duration)

            # Print perception results
            self._print_perception_results(perception_context)

            # Estimate API calls and tokens (mock values for demo)
            if self.args.use_llm:
                self.stats.add_api_call('perception')
                self.stats.add_tokens('perception', 800)

            return perception_context

        except Exception as e:
            error_msg = f"Perception stage failed: {str(e)}"
            print(f"\n❌ {error_msg}")
            self.stats.add_error(error_msg)
            return None

    def _print_perception_results(self, context: PerceptionContext) -> None:
        """Print perception stage results"""
        recent = context.recent_data

        print(f"\nProvince: {context.province_name} ({context.scenario if hasattr(context, 'scenario') else 'loaded'})")
        print(f"Data Quality: {context.data_quality}")

        print(f"\nCurrent Metrics:")
        print(f"  Population: {recent.population:,}")
        print(f"  Development: {recent.development_level}/10")
        print(f"  Loyalty: {recent.loyalty:.1f}/100")
        print(f"  Stability: {recent.stability:.1f}/100")
        print(f"  Monthly Income: {recent.actual_income:.0f}")
        print(f"  Monthly Expenditure: {recent.actual_expenditure:.0f}")
        print(f"  Surplus: {recent.actual_surplus:+.0f}")

        print(f"\nTrends:")
        print(f"  Income: {context.trends.income_trend.value} ({context.trends.income_change_rate:+.1f}%)")
        print(f"  Loyalty: {context.trends.loyalty_trend.value} ({context.trends.loyalty_change_rate:+.1f})")
        print(f"  Stability: {context.trends.stability_trend.value} ({context.trends.stability_change_rate:+.1f})")
        print(f"  Risk Level: {context.trends.risk_level.value}")

        if context.trends.risk_factors:
            print(f"\nRisk Factors:")
            for factor in context.trends.risk_factors[:3]:
                print(f"  ⚠️  {factor}")

        if context.trends.opportunities:
            print(f"\nOpportunities:")
            for opp in context.trends.opportunities[:3]:
                print(f"  ✓ {opp}")

        if context.warnings:
            print(f"\nWarnings:")
            for warning in context.warnings:
                print(f"  ⚠️  {warning}")

    async def _run_decision_stage(
        self,
        perception: PerceptionContext,
        province_state: Dict[str, Any]
    ) -> Optional[Decision]:
        """Run Stage 2: Decision"""
        print("\n" + "=" * 70)
        print("STAGE 2: DECISION")
        print("=" * 70)

        start_time = time.time()

        try:
            # Initialize EnhancedDecisionAgent
            agent = EnhancedDecisionAgent(
                agent_id="demo_decision",
                config=self._get_llm_agent_config('decision')
            )

            # Make decision
            decision = await agent.make_decision(
                perception=perception,
                instruction=None,  # No player instruction
                province_state=province_state
            )

            duration = time.time() - start_time
            self.stats.add_stage_time('decision', duration)

            # Print decision results
            self._print_decision_results(decision)

            # Estimate API calls and tokens
            if self.args.use_llm:
                api_calls = 1 + agent.interaction_rounds
                for _ in range(api_calls):
                    self.stats.add_api_call('decision')
                    self.stats.add_tokens('decision', 1600)

            return decision

        except Exception as e:
            error_msg = f"Decision stage failed: {str(e)}"
            print(f"\n❌ {error_msg}")
            self.stats.add_error(error_msg)
            return None

    def _print_decision_results(self, decision: Decision) -> None:
        """Print decision stage results"""
        print(f"\nBehaviors Selected: {len(decision.behaviors)}")

        for i, behavior in enumerate(decision.behaviors, 1):
            print(f"\n  {i}. {behavior.behavior_name}")
            print(f"     Type: {behavior.behavior_type.value}")
            if behavior.parameters:
                print(f"     Parameters: {json.dumps(behavior.parameters, indent=6)}")
            if behavior.reasoning:
                # Truncate long reasoning
                reasoning = behavior.reasoning[:200] + "..." if len(behavior.reasoning) > 200 else behavior.reasoning
                print(f"     Reasoning: {reasoning}")

        print(f"\nRisk Level: {decision.risk_level.value}")

        if decision.reasoning:
            reasoning = decision.reasoning[:400] + "..." if len(decision.reasoning) > 400 else decision.reasoning
            print(f"\nOverall Reasoning:")
            print(f"  {reasoning}")

        if decision.estimated_effects:
            print(f"\nEstimated Effects:")
            effects = decision.estimated_effects
            if 'income_change' in effects:
                print(f"  Income: {effects['income_change']:+.0f}")
            if 'loyalty_change' in effects:
                print(f"  Loyalty: {effects['loyalty_change']:+.1f}")
            if 'stability_change' in effects:
                print(f"  Stability: {effects['stability_change']:+.1f}")

    async def _run_execution_stage(
        self,
        perception: PerceptionContext,
        decision: Decision,
        province_state: Dict[str, Any]
    ):
        """Run Stage 3: Execution"""
        print("\n" + "=" * 70)
        print("STAGE 3: EXECUTION")
        print("=" * 70)

        start_time = time.time()

        try:
            # Initialize EnhancedExecutionAgent
            agent = EnhancedExecutionAgent(
                agent_id="demo_execution",
                config=self._get_llm_agent_config('execution')
            )

            # Build execution context
            execution_context = self._build_execution_context(perception, province_state)

            # Execute with LLM
            result = await agent.execute_with_llm(
                decision=decision,
                province_state=province_state.copy(),  # Don't modify original
                execution_context=execution_context
            )

            duration = time.time() - start_time
            self.stats.add_stage_time('execution', duration)

            # Print execution results
            self._print_execution_results(result)

            # Estimate API calls and tokens
            if self.args.use_llm:
                # Interpretation + quality assessment + creative events
                for _ in range(3):
                    self.stats.add_api_call('execution')
                    self.stats.add_tokens('execution', 1400)

            return result

        except Exception as e:
            error_msg = f"Execution stage failed: {str(e)}"
            print(f"\n❌ {error_msg}")
            self.stats.add_error(error_msg)
            return None

    def _build_execution_context(self, perception: PerceptionContext, province_state: Dict[str, Any]) -> ExecutionContext:
        """Build execution context"""
        # Determine season from month
        month = perception.current_month
        if month in [12, 1, 2]:
            season = "winter"
        elif month in [3, 4, 5]:
            season = "spring"
        elif month in [6, 7, 8]:
            season = "summer"
        else:
            season = "autumn"

        # Determine population mood
        loyalty = province_state.get('loyalty', 50)
        if loyalty > 70:
            mood = "positive"
        elif loyalty < 30:
            mood = "negative"
        else:
            mood = "neutral"

        # Determine economic conditions
        income = province_state.get('actual_income', 0)
        if income > 1000:
            economic = "booming"
        elif income > 500:
            economic = "stable"
        elif income > 200:
            economic = "struggling"
        else:
            economic = "crisis"

        return ExecutionContext(
            season=season,
            recent_events=[e.event_name for e in perception.critical_events[:3]],
            population_mood=mood,
            economic_conditions=economic,
            political_stability="stable" if province_state.get('stability', 50) > 50 else "unstable"
        )

    def _print_execution_results(self, result) -> None:
        """Print execution stage results"""
        # Get execution data from enhanced result
        if hasattr(result, 'execution_result'):
            execution_data = result.execution_result
            quality_report = result.quality_report
        else:
            execution_data = result
            quality_report = None

        executed_behaviors = execution_data.get('executed_behaviors', [])
        generated_events = execution_data.get('generated_events', [])
        total_effects = execution_data.get('total_effects', {})

        if quality_report:
            print(f"\nQuality Score: {quality_report.overall_score * 100:.1f}%")
            print(f"\nQuality Breakdown:")
            print(f"  Effectiveness: {quality_report.effectiveness * 100:.0f}%")
            print(f"  Efficiency: {quality_report.efficiency * 100:.0f}%")
            print(f"  Impact: {quality_report.impact * 100:.0f}%")
            print(f"  Risk Management: {quality_report.risk_management * 100:.0f}%")
            print(f"  Adaptability: {quality_report.adaptability * 100:.0f}%")

        print(f"\nExecuted Behaviors: {len(executed_behaviors)}")
        for behavior in executed_behaviors:
            print(f"  ✓ {behavior.get('behavior_name', 'Unknown')}")

        print(f"\nGenerated Events: {len(generated_events)}")
        for event in generated_events:
            print(f"  • {event.get('name', 'Unknown')} ({event.get('severity', 0):.1f} severity)")

        if total_effects:
            print(f"\nTotal Effects:")
            if total_effects.get('income_change', 0) != 0:
                print(f"  Income: {total_effects['income_change']:+.0f}")
            if total_effects.get('expenditure_change', 0) != 0:
                print(f"  Expenditure: {total_effects['expenditure_change']:+.0f}")
            if total_effects.get('loyalty_change', 0) != 0:
                print(f"  Loyalty: {total_effects['loyalty_change']:+.1f}")
            if total_effects.get('stability_change', 0) != 0:
                print(f"  Stability: {total_effects['stability_change']:+.1f}")

        if quality_report and quality_report.success_factors:
            print(f"\nSuccess Factors:")
            for factor in quality_report.success_factors[:3]:
                print(f"  ✓ {factor}")

        if quality_report and quality_report.improvement_recommendations:
            print(f"\nRecommendations:")
            for rec in quality_report.improvement_recommendations[:2]:
                print(f"  → {rec}")

    def _generate_quality_summary(
        self,
        perception: PerceptionContext,
        decision: Decision,
        execution_result
    ) -> str:
        """Generate quality summary"""
        summary_parts = []

        # Data quality
        if perception.data_quality == "complete":
            summary_parts.append("✓ Complete data quality")
        else:
            summary_parts.append(f"⚠ {perception.data_quality} data quality")

        # Decision quality
        behaviors_count = len(decision.behaviors)
        summary_parts.append(f"✓ {behaviors_count} behaviors selected")

        # Execution quality
        if execution_result:
            if hasattr(execution_result, 'quality_report'):
                score = execution_result.quality_report.overall_score
                if score > 0.8:
                    summary_parts.append("✓ Excellent execution")
                elif score > 0.6:
                    summary_parts.append("✓ Good execution")
                else:
                    summary_parts.append("⚠ Execution challenges")
            else:
                summary_parts.append("✓ Execution completed")

        return " | ".join(summary_parts)

    def _create_failed_result(self, pipeline_id: str, scenario: str) -> PipelineResult:
        """Create failed result"""
        return PipelineResult(
            pipeline_id=pipeline_id,
            timestamp=datetime.now().isoformat(),
            province_id=1,
            scenario=scenario,
            perception_context=None,
            decision=None,
            execution_result=None,
            performance_stats=self.stats,
            quality_summary="❌ Pipeline failed",
            overall_success=False
        )

    def _print_performance_summary(self) -> None:
        """Print performance summary"""
        print("\n" + "=" * 70)
        print("PIPELINE PERFORMANCE")
        print("=" * 70)

        print(f"\nTotal Time: {self.stats.total_time:.1f}s")

        if self.stats.stage_times:
            print("\nStage Breakdown:")
            for stage, duration in self.stats.stage_times.items():
                api_info = ""
                if stage in self.stats.api_calls:
                    api_info = f" ({self.stats.api_calls[stage]} API calls"
                    if stage in self.stats.tokens_used:
                        api_info += f", ~{self.stats.tokens_used[stage]} tokens"
                    api_info += ")"
                print(f"  {stage.title()}: {duration:.1f}s{api_info}")

        if self.stats.total_api_calls > 0:
            print(f"\nTotal API Calls: {self.stats.total_api_calls}")
            print(f"Total Tokens Used: ~{self.stats.total_tokens}")

        if self.stats.errors:
            print(f"\nErrors ({len(self.stats.errors)}):")
            for error in self.stats.errors:
                print(f"  ❌ {error}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Three-Agent Pipeline Demo - Perception, Decision, Execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use built-in scenario
  python demo_three_agent_pipeline.py --scenario normal

  # Crisis scenario with verbose output
  python demo_three_agent_pipeline.py --scenario crisis --verbose

  # Load from JSON file
  python demo_three_agent_pipeline.py --file data.json --output results.json

  # Use real LLM API
  python demo_three_agent_pipeline.py --scenario prosperity --api-key YOUR_KEY

  # Mock mode (default)
  python demo_three_agent_pipeline.py --scenario growth

Available scenarios: normal, crisis, prosperity, growth, decline
        """
    )

    parser.add_argument(
        '--scenario', '-s',
        type=str,
        choices=list_scenarios(),
        help='Test scenario to use (default: normal)'
    )

    parser.add_argument(
        '--file', '-f',
        type=str,
        help='Load perception context from JSON file'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Save results to JSON file'
    )

    parser.add_argument(
        '--config', '-c',
        type=str,
        default='config.yaml',
        help='Config file path (default: config.yaml)'
    )

    parser.add_argument(
        '--api-key',
        type=str,
        help='LLM API key (overrides config and environment)'
    )

    parser.add_argument(
        '--use-llm',
        action='store_true',
        help='Use real LLM API instead of mock mode'
    )

    parser.add_argument(
        '--use-memory-db',
        action='store_true',
        default=True,
        help='Use in-memory database (default: True)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    # Default to normal scenario if no file specified
    if not args.file and not args.scenario:
        args.scenario = 'normal'

    # Run demo
    demo = PipelineDemo(args)

    async def run():
        # Determine data source
        if args.file:
            result = await demo.run_pipeline(DataSource.JSON_FILE, json_file=args.file)
        else:
            result = await demo.run_pipeline(
                DataSource[f"MOCK_{args.scenario.upper()}"],
                scenario=args.scenario
            )

        # Print performance summary
        demo._print_performance_summary()

        # Save results if requested
        if args.output and result:
            with open(args.output, 'w') as f:
                json.dump(result.to_dict(), f, indent=2, default=str)
            print(f"\n✓ Results saved to {args.output}")

        # Return success status
        return 0 if result.overall_success else 1

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
