"""
Main game loop module - Responsible only for orchestration, not decision-making
"""

import asyncio
import random
from typing import List, Dict, Any, Optional
from .province import Province
from .project import Project
from .calculations import (
    calculate_province_income,
    calculate_province_expenditure,
    calculate_treasury_change,
    generate_random_factor
)
from db.database import Database
from agents.governor_agent import GovernorAgent
from agents.central_advisor import CentralAdvisorAgent
from events.event_manager import EventManager
from events.event_generator import EventGenerator
from events.agent_event_generator import AgentEventGenerator
from events.event_effects import calculate_event_modifiers
from agents.personality import GovernorPersonality, AgentCapability, PERSONALITY_PRESETS


class Game:
    """Main game class - Coordinates Agents and calculation logic"""

    def __init__(self, db_path: str = "game.db", enable_central_advisor: bool = False):
        """Initialize game

        Args:
            db_path: Database path
            enable_central_advisor: Whether to enable central advisor Agent
        """
        self.db = Database(db_path)
        self.state = self.db.load_game_state()
        self.provinces = self._load_provinces()
        self.active_projects = []
        self.agents: Dict[str, GovernorAgent] = {}
        self.central_advisor: Optional[CentralAdvisorAgent] = None

        # Initialize event system
        self.event_manager = EventManager(self.db)
        self.base_event_generator = EventGenerator({'event_probability': 0.3})
        self.agent_event_generator = AgentEventGenerator()

        # Initialize budget system
        from .budget_system import BudgetSystem
        from .treasury_system import TreasurySystem
        from .budget_execution import BudgetExecutor
        self.budget_system = BudgetSystem(self.db)
        self.treasury_system = TreasurySystem(self.db)
        self.budget_executor = BudgetExecutor(self.budget_system, self.treasury_system, self.event_manager)

        # Initialize Governor Agents (with personality system)
        self._initialize_governor_agents()

        # Initialize Province Agents (Perception, Decision, Execution)
        self._initialize_province_agents()

        # Initialize Central Advisor (if needed)
        if enable_central_advisor:
            self._initialize_central_advisor()

    def _initialize_governor_agents(self) -> None:
        """Initialize Governor Agent for each province"""
        print("Initializing Governor Agents...")

        for province in self.provinces:
            agent_id = f"governor_{province.province_id}"

            # Randomly assign personality type
            trait_types = ['honest', 'corrupt', 'pragmatic', 'ambitious', 'cautious', 'deceptive']
            selected_trait = random.choice(trait_types)
            preset_name = f"{selected_trait}_governor"
            personality = PERSONALITY_PRESETS[preset_name]

            print(f"  {province.name}: {personality.primary_trait} type")

            config = {
                'province_id': province.province_id,
                'province_name': province.name,
                'corruption_tendency': province.corruption_tendency,
                'loyalty': province.loyalty,
                'stability': province.stability,
                'development_level': province.development_level,
                'personality': personality,  # Add personality system
                'llm_config': {
                    'enabled': False,  # Governor doesn't use LLM by default
                    'mock_mode': True
                }
            }

            agent = GovernorAgent(agent_id, config)
            self.agents[agent_id] = agent

            # Initialize provincial treasury balance (random <1000)
            initial_treasury = random.uniform(100, 999)
            self.treasury_system.initialize_provincial_treasury(province.province_id, initial_treasury)
            print(f"    - Provincial treasury balance: {initial_treasury:.2f} gold coins")

            # Set default surplus allocation ratio to 0.5
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO surplus_allocation_ratios (province_id, ratio)
                VALUES (?, 0.5)
            """, (province.province_id,))
            conn.commit()
            conn.close()
            print(f"    - Allocation ratio: 50% to central, 50% local retention")

        print(f"✓ Initialized {len(self.agents)} Governor Agents")

    def _initialize_province_agents(self) -> None:
        """Initialize Province Agents (Perception, Decision, Execution) for each province"""
        from agents.province.perception_agent import PerceptionAgent
        from agents.province.decision_agent import DecisionAgent
        from agents.province.execution_agent import ExecutionAgent
        from agents.province.decision_agent_llm import EnhancedDecisionAgent
        from agents.province.enhanced_execution_agent import EnhancedExecutionAgent
        from config_loader import get_config

        print("Initializing Province Agents...")

        config = get_config()
        use_enhanced_pipeline = config.get('province_agent.use_enhanced_pipeline', False)

        self.province_agents = {}
        self.use_enhanced_pipeline = use_enhanced_pipeline

        for province in self.provinces:
            # Get LLM configuration
            llm_config = config.get_llm_config()

            # Create Perception Agent
            perception_agent = PerceptionAgent(
                agent_id=f"perception_{province.province_id}",
                config={
                    'province_id': province.province_id,
                    'llm_config': llm_config
                },
                db=self.db
            )

            # Create Decision Agent (enhanced or standard)
            if use_enhanced_pipeline:
                decision_config = {
                    'province_id': province.province_id,
                    'llm_config': llm_config,
                    'mode': config.get('province_agent.mode', 'llm_assisted'),
                    'interaction_rounds': config.get('province_agent.interaction_rounds', 0),
                    'risk_tolerance': config.get('province_agent.risk_tolerance', 'moderate')
                }
                decision_agent = EnhancedDecisionAgent(
                    agent_id=f"decision_{province.province_id}",
                    config=decision_config
                )
            else:
                decision_agent = DecisionAgent(
                    agent_id=f"decision_{province.province_id}",
                    config={
                        'province_id': province.province_id,
                        'llm_config': llm_config
                    }
                )

            # Create Execution Agent (enhanced or standard)
            if use_enhanced_pipeline:
                execution_config = {
                    'province_id': province.province_id,
                    'llm_config': llm_config,
                    'execution_mode': config.get('province_agent.execution_mode', 'llm_enhanced'),
                    'quality_threshold': config.get('province_agent.quality_threshold', 0.7)
                }
                execution_agent = EnhancedExecutionAgent(
                    agent_id=f"execution_{province.province_id}",
                    config=execution_config
                )
            else:
                execution_agent = ExecutionAgent(
                    agent_id=f"execution_{province.province_id}",
                    config={'province_id': province.province_id}
                )

            self.province_agents[province.province_id] = {
                'perception': perception_agent,
                'decision': decision_agent,
                'execution': execution_agent
            }

        pipeline_mode = "enhanced" if use_enhanced_pipeline else "standard"
        print(f"✓ Initialized {len(self.province_agents)} Province Agent sets ({pipeline_mode} mode)")

    def _initialize_central_advisor(self) -> None:
        """Initialize Central Advisor Agent"""
        print("Initializing Central Advisor Agent...")

        config = {
            'llm_config': {
                'enabled': True,
                'mock_mode': True,  # Use mock by default to avoid API dependency
                'model': 'claude-3-haiku-20240307'
            },
            'mode': 'llm_assisted'  # Central advisor uses LLM by default
        }

        self.central_advisor = CentralAdvisorAgent("central_advisor", config)
        print("✓ Central Advisor Agent initialized")

    def _load_provinces(self) -> List[Province]:
        """Load provinces from database"""
        province_data = self.db.load_provinces()
        return [Province(data) for data in province_data]

    def _save_provinces(self) -> None:
        """Save province data to database"""
        province_data = [p.to_dict() for p in self.provinces]
        self.db.save_provinces(province_data)

    async def next_month(self) -> None:
        """Advance to next month (async, because it needs to call Agents)"""
        print(f"\n{'='*60}")
        print(f"Calculating month {self.state['current_month'] + 1}...")
        print(f"{'='*60}")

        # 1. Process active projects
        self._process_active_projects()

        # === Phase 0: Agent generates events (proactive behavior) ===
        print("\n[Event Generation Phase]")
        current_month = self.state['current_month']
        current_year = (current_month - 1) // 12 + 1  # Calculate current year

        # Load last month's active events and clean up expired events
        self.event_manager.load_active_events(current_month)
        self.event_manager.cleanup_expired_events(current_month)

        # Agent generates events
        agent_generated_events = []
        for province in self.provinces:
            agent_id = f"governor_{province.province_id}"
            agent = self.agents[agent_id]

            # Prepare game context
            game_context = {
                'central_attention': 0.5,  # Central attention level (adjustable)
                'treasury': self.state['treasury'],
                'month': current_month,
                'needs_cover': province.last_month_corrupted if hasattr(province, 'last_month_corrupted') else False
            }

            # Agent decides whether to generate an event
            event = self.agent_event_generator.generate_agent_event(
                agent,
                province.to_dict(),
                game_context
            )

            if event:
                self.event_manager.add_event(event)
                agent_generated_events.append(event)
                print(f"  {province.name}: Generated event '{event.name}' {'(fabricated)' if event.is_fabricated else '(real)'}")

        # Generate base events (system events)
        base_events = self.base_event_generator.generate_events(
            self.state,
            [p.to_dict() for p in self.provinces],
            current_month
        )
        for event in base_events:
            self.event_manager.add_event(event)

        print(f"  Total {len(agent_generated_events) + len(base_events)} events generated")

        # === Phase 1: Calculate actual income/expenditure for each province (apply event effects) ===
        provinces_data = []
        for province in self.provinces:
            # Calculate event modifiers
            modifiers = calculate_event_modifiers(
                self.event_manager.active_events,
                province.province_id
            )

            # Generate random factor (for income fluctuations)
            random_factor = generate_random_factor(
                seed=province.province_id + self.state['current_month']
            )

            # Calculate base income/expenditure
            base_income = calculate_province_income(
                population=province.population,
                development_level=province.development_level,
                stability=province.stability,
                random_factor=random_factor
            )
            base_expenditure = calculate_province_expenditure(
                population=province.population,
                stability=province.stability
            )

            # Apply event modifiers
            actual_income = base_income * modifiers.get('income', 1.0)
            actual_expenditure = base_expenditure * modifiers.get('expenditure', 1.0)

            provinces_data.append({
                'province_id': province.province_id,
                'actual_income': actual_income,
                'actual_expenditure': actual_expenditure,
                'event_modifiers': modifiers
            })

        # 3. Call Governor Agents for decisions (async)
        print("\n[Governor Decision Phase]")
        agent_tasks = []
        for i, province in enumerate(self.provinces):
            agent_id = f"governor_{province.province_id}"
            agent = self.agents[agent_id]

            # Create async task
            task = asyncio.create_task(
                self._run_governor_agent(agent, province, provinces_data[i]),
                name=f"governor_{province.province_id}"
            )
            agent_tasks.append(task)

        # Wait for all Governor Agents to complete
        results = await asyncio.gather(*agent_tasks, return_exceptions=True)

        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Error: Governor Agent for province {self.provinces[i].name} failed: {result}")
            elif result:
                # Update province data
                province = self.provinces[i]
                province.update_values(
                    actual_income=result['actual_income'],
                    actual_expenditure=result['actual_expenditure'],
                    reported_income=result['reported_income'],
                    reported_expenditure=result['reported_expenditure']
                )
                province.last_month_corrupted = result['last_month_corrupted']

                # Display decision results
                if result['last_month_corrupted']:
                    print(f"  ⚠️ {province.name}: Concealing report")
                else:
                    print(f"  ✓ {province.name}: Honest reporting")

        # === Phase 2.5: Province Agent Execution ===
        print("\n[Province Agent Execution Phase]")
        await self._run_province_agents(current_month, current_year)

        # 4. Central advisor analysis (if available)
        if self.central_advisor:
            print("\n[Central Advisor Analysis Phase]")
            try:
                # Run central advisor
                await self.central_advisor.on_month_start(self.state, [p.to_dict() for p in self.provinces])
                analysis = await self.central_advisor.take_action({})

                if analysis:
                    print(f"\n[LLM Analysis] {analysis.get('summary', '')}")
                    print("Recommendations:")
                    for rec in analysis.get('recommendations', []):
                        print(f"  - {rec}")

                    # Display suspicious provinces
                    suspicious = analysis.get('suspicious_provinces', [])
                    if suspicious:
                        print(f"\nSuspicious provinces ({len(suspicious)}):")
                        for sp in suspicious:
                            severity = sp.get('severity', 'unknown')
                            mark = "🔴" if severity == 'high' else "🟡" if severity == 'medium' else "⚪"
                            print(f"  {mark} {sp['name']}: {sp.get('reason', '')}")

            except Exception as e:
                print(f"Central advisor analysis failed: {e}")

        # === Phase 4: Budget execution ===
        print("\n[Budget Execution Phase]")

        # Execute monthly budget (provincial level)
        budget_result = self.budget_executor.execute_monthly_budget(
            self.state, self.provinces, current_month, current_year
        )
        print(f"  Provincial surplus to central: {budget_result['total_central_income']:.2f} gold coins")
        print(f"  Provincial surplus retained: {budget_result['total_central_allocation']:.2f} gold coins")

        # Execute central budget
        central_result = self.budget_executor.execute_central_budget(current_month, current_year)
        print(f"  Central fixed expenditure: {central_result['fixed_expenditure']:.2f} gold coins")
        if central_result['event_expenditure'] > 0:
            print(f"  Central event expenditure: {central_result['event_expenditure']:.2f} gold coins")
        print(f"  National treasury balance change: {central_result['starting_balance']:.2f} -> {central_result['ending_balance']:.2f} gold coins")

        # 5. Update national treasury (traditional method, for compatibility)
        self.state['month_starting_treasury'] = self.state['treasury']
        treasury_change = calculate_treasury_change(provinces_data)
        self.state['treasury'] += treasury_change

        # 6. Record monthly reports
        for province in self.provinces:
            treasury_change_reported = province.reported_income - province.reported_expenditure
            self.db.add_monthly_report(
                month=current_month,
                province_id=province.province_id,
                reported_income=province.reported_income,
                reported_expenditure=province.reported_expenditure,
                actual_income=province.actual_income,
                actual_expenditure=province.actual_expenditure,
                treasury_change=treasury_change_reported
            )

        # 7. Save data
        self._save_provinces()
        self.db.save_game_state(self.state)

        # === December special handling: Annual rollover and budget generation ===
        if current_month % 12 == 0:
            print(f"\n{'='*60}")
            print(f"  December annual processing: End of year {current_year}")
            print(f"{'='*60}")

            # Annual surplus rollover
            print("\n[Annual Surplus Rollover]")
            rollover_result = self.budget_executor.rollover_annual_surplus(current_year)
            print(f"  Central surplus: {rollover_result['national_rollover']:+.2f} gold coins")
            if rollover_result['provincial_rollovers']:
                print(f"  Provincial surplus: {len(rollover_result['provincial_rollovers'])} provinces have surplus")

            # Generate next year's budget
            print("\n[Generate Next Year's Budget]")
            national_budget_id = self.budget_system.generate_national_budget(current_year + 1)
            provincial_budget_ids = self.budget_system.generate_provincial_budgets(current_year + 1)
            print(f"  Central budget generated (ID: {national_budget_id[:8]}...)")
            print(f"  Generated budgets for {len(provincial_budget_ids)} provinces")

            # Budget adjustment interface (implemented in CLI)
            print("\n[Budget Adjustment Recommendations]")
            advice = self.budget_system.generate_budget_advice(current_year + 1)
            print(f"  Central recommended budget: {advice['national']:.2f} gold coins")
            print("  Use CLI menu for budget adjustments (Option 8: View budget execution)")

        # 8. Increment month
        self.state['current_month'] += 1

        # Summary information
        total_income = sum(p.reported_income for p in self.provinces)
        total_expenditure = sum(p.reported_expenditure for p in self.provinces)

        print(f"\n{'='*60}")
        print(f"✓ Month {self.state['current_month']} completed!")
        print(f"{'='*60}")
        print(f"National treasury: {self.state['treasury']:.2f} gold coins (change: {treasury_change:+.2f})")
        print(f"Total reported income: {total_income:.2f} gold coins, Total expenditure: {total_expenditure:.2f} gold coins")

    async def _run_governor_agent(self, agent: GovernorAgent, province: Province,
                                province_data: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """Run a single Governor Agent

        Args:
            agent: Governor Agent instance
            province: Province object
            province_data: Province calculation data (actual_income, actual_expenditure)

        Returns:
            Execution result dictionary, or None
        """
        try:
            # Trigger monthly start event
            await agent.on_month_start(self.state, [p.to_dict() for p in self.provinces])

            # Trigger action execution
            context = {
                'actual_income': province_data['actual_income'],
                'actual_expenditure': province_data['actual_expenditure']
            }
            result = await agent.take_action(context)

            return result

        except Exception as e:
            print(f"Governor Agent {agent.agent_id} execution failed: {e}")
            # Return a default honest reporting result
            return {
                'province_id': province.province_id,
                'province_name': province.name,
                'actual_income': province_data['actual_income'],
                'actual_expenditure': province_data['actual_expenditure'],
                'reported_income': province_data['actual_income'],
                'reported_expenditure': province_data['actual_expenditure'],
                'corruption_ratio': 0.0,
                'expenditure_inflation': 0.0,
                'last_month_corrupted': False,
                'reasoning': 'Agent execution failed, default to honest reporting'
            }

    async def _run_province_agents(self, current_month: int, current_year: int) -> None:
        """Run Province Agents (Perception, Decision, Execution) for all provinces

        Args:
            current_month: Current month number
            current_year: Current year
        """
        for province in self.provinces:
            try:
                # Get province agents
                agents = self.province_agents.get(province.province_id)
                if not agents:
                    continue

                perception_agent = agents['perception']
                decision_agent = agents['decision']
                execution_agent = agents['execution']

                # Route to enhanced or standard pipeline
                if self.use_enhanced_pipeline:
                    await self._run_enhanced_pipeline(
                        province, perception_agent, decision_agent, execution_agent,
                        current_month, current_year
                    )
                else:
                    await self._run_standard_pipeline(
                        province, perception_agent, decision_agent, execution_agent,
                        current_month, current_year
                    )

            except Exception as e:
                print(f"  ⚠️ {province.name}: Province Agent execution failed: {e}")

    async def _run_standard_pipeline(
        self,
        province,
        perception_agent,
        decision_agent,
        execution_agent,
        current_month: int,
        current_year: int
    ) -> None:
        """Run standard pipeline (rule-based)"""
        # === Stage 1: Perception ===
        perception_context = await perception_agent.perceive(
            province_id=province.province_id,
            current_month=current_month,
            current_year=current_year
        )

        # === Stage 2: Decision ===
        province_state = self._build_province_state(province)

        decision = await decision_agent.make_decision(
            perception=perception_context,
            instruction=None,
            province_state=province_state
        )

        # === Stage 3: Execution ===
        execution_result = await execution_agent.execute(
            decision=decision,
            province_state=province_state,
            month=current_month,
            year=current_year
        )

        # Apply results
        self._apply_pipeline_results(
            province, execution_result.executed_behaviors,
            execution_result.generated_events, current_month
        )

    async def _run_enhanced_pipeline(
        self,
        province,
        perception_agent,
        decision_agent,
        execution_agent,
        current_month: int,
        current_year: int
    ) -> None:
        """Run enhanced pipeline (LLM-powered)"""
        # === Stage 1: Perception ===
        perception_context = await perception_agent.perceive(
            province_id=province.province_id,
            current_month=current_month,
            current_year=current_year
        )

        # === Stage 2: Decision ===
        province_state = self._build_province_state(province)

        decision = await decision_agent.make_decision(
            perception=perception_context,
            instruction=None,
            province_state=province_state
        )

        # === Stage 3: Enhanced Execution ===
        execution_context = self._build_execution_context(province, current_month)

        execution_result = await execution_agent.execute_with_llm(
            decision=decision,
            province_state=province_state.copy(),
            execution_context=execution_context
        )

        # Extract execution data from enhanced result
        execution_data = execution_result.execution_result

        # Apply results
        executed_behaviors = []
        for behavior_dict in execution_data.get('executed_behaviors', []):
            # Convert dict back to ExecutedBehavior
            from agents.province.models import ExecutedBehavior, BehaviorEffect
            effect_dict = behavior_dict.get('effects', {})
            effect = BehaviorEffect(**effect_dict)
            executed_behaviors.append(ExecutedBehavior(
                behavior_type=behavior_dict['behavior_type'],
                behavior_name=behavior_dict['behavior_name'],
                parameters=behavior_dict.get('parameters', {}),
                effects=effect,
                reasoning=behavior_dict.get('reasoning'),
                execution_success=behavior_dict.get('execution_success', True),
                execution_message=behavior_dict.get('execution_message')
            ))

        generated_events = []
        for event_dict in execution_data.get('generated_events', []):
            # Convert dict back to BehaviorEvent
            from agents.province.models import BehaviorEvent
            generated_events.append(BehaviorEvent(**event_dict))

        # Print quality info if available
        if execution_result.quality_report:
            quality = execution_result.quality_report
            if quality.overall_score > 0.8:
                print(f"  {province.name}: High-quality execution ({quality.overall_score * 100:.0f}%)")
            elif quality.overall_score > 0.6:
                print(f"  {province.name}: Good execution quality ({quality.overall_score * 100:.0f}%)")

        self._apply_pipeline_results(
            province, executed_behaviors, generated_events, current_month
        )

    def _build_province_state(self, province) -> Dict[str, Any]:
        """Build province state dictionary"""
        return {
            'actual_income': province.actual_income,
            'actual_expenditure': province.actual_expenditure,
            'reported_income': province.reported_income,
            'reported_expenditure': province.reported_expenditure,
            'actual_surplus': province.actual_income - province.actual_expenditure,
            'loyalty': province.loyalty,
            'stability': province.stability,
            'development_level': province.development_level,
            'population': province.population
        }

    def _build_execution_context(self, province, current_month: int):
        """Build execution context for enhanced pipeline"""
        from agents.province.enhanced_execution_models import ExecutionContext

        # Determine season
        if current_month in [12, 1, 2]:
            season = "winter"
        elif current_month in [3, 4, 5]:
            season = "spring"
        elif current_month in [6, 7, 8]:
            season = "summer"
        else:
            season = "autumn"

        # Determine population mood
        if province.loyalty > 70:
            mood = "positive"
        elif province.loyalty < 30:
            mood = "negative"
        else:
            mood = "neutral"

        # Determine economic conditions
        if province.actual_income > 1000:
            economic = "booming"
        elif province.actual_income > 500:
            economic = "stable"
        elif province.actual_income > 200:
            economic = "struggling"
        else:
            economic = "crisis"

        # Determine political stability
        if province.stability > 70:
            stability = "stable"
        elif province.stability < 30:
            stability = "unstable"
        else:
            stability = "tense"

        return ExecutionContext(
            season=season,
            recent_events=[],  # Could be populated from recent events if needed
            population_mood=mood,
            economic_conditions=economic,
            political_stability=stability
        )

    def _apply_pipeline_results(
        self,
        province,
        executed_behaviors,
        generated_events,
        current_month: int
    ) -> None:
        """Apply pipeline results to province"""
        if not executed_behaviors:
            return

        print(f"  {province.name}: Executed {len(executed_behaviors)} behavior(s)")

        # Apply effects
        for behavior in executed_behaviors:
            effect = behavior.effects
            province.actual_income += effect.income_change
            province.actual_expenditure += effect.expenditure_change
            province.loyalty = max(0, min(100, province.loyalty + effect.loyalty_change))
            province.stability = max(0, min(100, province.stability + effect.stability_change))
            province.development_level = max(0, min(10, province.development_level + effect.development_change))

            print(f"    - {behavior.behavior_name}: loyalty {effect.loyalty_change:+.1f}, stability {effect.stability_change:+.1f}")

        # Generate and save events
        for event in generated_events:
            event_dict = {
                'event_id': event.event_id,
                'province_id': province.province_id,
                'name': event.name,
                'description': event.description,
                'event_type': event.event_type,
                'severity': event.severity,
                'start_month': current_month,
                'end_month': current_month,
                'is_active': True,
                'visibility': event.visibility,
                'is_agent_generated': event.is_agent_generated
            }

            # Parse effects into event format
            instant_effects = {}
            if abs(event.effects.get('income_change', 0)) > 0:
                instant_effects['income'] = event.effects['income_change']
            if abs(event.effects.get('expenditure_change', 0)) > 0:
                instant_effects['expenditure'] = event.effects['expenditure_change']
            if abs(event.effects.get('loyalty_change', 0)) > 0:
                instant_effects['loyalty'] = event.effects['loyalty_change']
            if abs(event.effects.get('stability_change', 0)) > 0:
                instant_effects['stability'] = event.effects['stability_change']

            import json
            event_dict['instant_effects'] = json.dumps(instant_effects)
            event_dict['continuous_effects'] = json.dumps({})

            # Save to database
            self.db.save_event(event_dict)

            print(f"    Generated event: {event.name}")

    def _process_active_projects(self) -> None:
        """Process effects of active projects"""
        project_data = self.db.get_active_projects()

        for proj_data in project_data:
            # Check if project takes effect in current month (simplified: takes effect next month after creation)
            if proj_data['month_created'] == self.state['current_month'] - 1:
                self._apply_project_effect(proj_data)
                # Mark project as completed
                self.db.complete_project(proj_data['project_id'])

    def _apply_project_effect(self, project_data: Dict[str, Any]) -> None:
        """Apply project effects"""
        province = next((p for p in self.provinces
                        if p.province_id == project_data['province_id']),
                       None)

        if not province:
            return

        effect_type = project_data['effect_type']
        effect_value = project_data['effect_value']

        from .calculations import calculate_project_effect

        if effect_type == 'income_bonus':
            # Increase base income
            old_income = province.base_income
            province.base_income = calculate_project_effect(effect_type, effect_value, old_income)
            print(f"  {province.name}: Agricultural reform takes effect, base income increases by {effect_value*100:.0f}% ({old_income:.0f}→{province.base_income:.0f})")

        elif effect_type == 'development_bonus':
            # Increase development level
            old_level = province.development_level
            province.development_level = calculate_project_effect(effect_type, effect_value, old_level)
            print(f"  {province.name}: Infrastructure improvement, development level +{effect_value} ({old_level:.1f}→{province.development_level:.1f})")

        elif effect_type == 'loyalty_bonus':
            # Increase loyalty
            old_loyalty = province.loyalty
            province.loyalty = calculate_project_effect(effect_type, effect_value, old_loyalty)
            print(f"  {province.name}: Tax relief, loyalty +{effect_value} ({old_loyalty:.0f}→{province.loyalty:.0f})")

        elif effect_type == 'stability_bonus':
            # Increase stability
            old_stability = province.stability
            province.stability = calculate_project_effect(effect_type, effect_value, old_stability)
            print(f"  {province.name}: Security enhancement, stability +{effect_value} ({old_stability:.0f}→{province.stability:.0f})")

    def add_project(self, project: Project) -> None:
        """Add new project"""
        project_data = project.to_dict()
        project_data['month_created'] = self.state['current_month']

        self.db.add_project(project_data)

        # Deduct project cost
        self.state['treasury'] -= project.cost
        self.db.save_game_state(self.state)

        print(f"\n✓ Started {project.project_type} project in province")
        print(f"  Cost: {project.cost} gold coins, National treasury remaining: {self.state['treasury']:.2f} gold coins")

    def toggle_debug_mode(self) -> None:
        """Toggle Debug mode"""
        self.state['debug_mode'] = not self.state['debug_mode']
        self.db.save_game_state(self.state)

        status = "enabled" if self.state['debug_mode'] else "disabled"
        print(f"\nDebug mode {status}")

        if self.state['debug_mode']:
            print("Now you can see actual income/expenditure data for each province (reported / actual)")
        else:
            print("Now you can only see data reported by officials (real game experience)")

    def get_financial_summary(self) -> dict:
        """Get financial summary"""
        total_reported_income = sum(p.reported_income for p in self.provinces)
        total_reported_expenditure = sum(p.reported_expenditure for p in self.provinces)

        return {
            'month': self.state['current_month'],
            'treasury': self.state['treasury'],
            'month_starting_treasury': self.state['month_starting_treasury'],
            'total_reported_income': total_reported_income,
            'total_reported_expenditure': total_reported_expenditure,
            'provinces': self.provinces
        }

    # Wrapper method for non-async calls
    def next_month_sync(self) -> None:
        """Synchronous version of next_month (for non-async environments)"""
        asyncio.run(self.next_month())
