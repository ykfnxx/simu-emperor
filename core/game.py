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
        current_month = self.state['current_month']
        current_year = (current_month - 1) // 12 + 1  # Calculate current year

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
