"""
Command Line Interface Module
"""

import asyncio
from core.game import Game
from core.project import Project


class GameCLI:
    """Command Line Interface Class"""

    def __init__(self, game: Game):
        """Initialize CLI

        Args:
            game: Game instance
        """
        self.game = game

    def run(self):
        """Main game loop (synchronous entry)"""
        asyncio.run(self._run_async())

    async def _run_async(self):
        """Asynchronous main game loop"""
        while True:
            self.show_main_menu()
            choice = input("\nSelect operation: ").strip()

            if choice == '1':
                self.show_financial_report()
            elif choice == '2':
                self.manage_projects()
            elif choice == '3':
                self.game.toggle_debug_mode()
            elif choice == '4':
                await self.game.next_month()
            elif choice == '5':
                self.show_province_events()
            elif choice == '6':
                self.show_national_status()
            elif choice == '7':
                self.fund_management()
            elif choice == '8':
                self.show_budget_execution()
            elif choice.lower() == 'q':
                print("\nThanks for playing!")
                break
            else:
                print("\nInvalid selection, please try again")

    def show_main_menu(self):
        """Display main menu"""
        print(f"\n{'='*60}")
        print(f"Month {self.game.state['current_month']} - Ruler Console")
        print(f"{'='*60}")
        print(f"Treasury Balance: {self.game.state['treasury']:.2f} gold")
        debug_status = "Enabled" if self.game.state['debug_mode'] else "Disabled"
        print(f"Debug Mode: {debug_status}")

        # Display active event counts
        active_events = self.game.event_manager.get_active_events(self.game.state['current_month'])
        national_events = [e for e in active_events if e.event_type == 'national']
        province_events = [e for e in active_events if e.event_type == 'province']
        print(f"Active Events: {len(national_events)} national, {len(province_events)} provincial")

        print("\n1. View Financial Report")
        print("2. Manage Provincial Projects")
        print("3. Toggle Debug Mode")
        print("4. Next Month")
        print("5. View Provincial Events")
        print("6. View National Status")
        print("7. Fund Management")
        print("8. View Budget Execution")
        print("q. Quit Game")

    def show_financial_report(self):
        """Display financial report"""
        print(f"\n{'='*70}")
        print(f"Month {self.game.state['current_month']} Financial Report")
        print(f"{'='*70}")

        summary = self.game.get_financial_summary()
        print(f"Month Start Treasury: {summary['month_starting_treasury']:.2f} gold")
        print(f"Month End Treasury: {summary['treasury']:.2f} gold")

        month_change = summary['treasury'] - summary['month_starting_treasury']
        print(f"Monthly Change: {month_change:+.2f} gold")

        if self.game.state['debug_mode']:
            # Debug mode: show comparison data
            print(f"\n{'[Debug] Provincial Status (Reported / Actual)':-^70}")
            for province in summary['provinces']:
                print(f"\n[{province.name}]")
                print(f"  Income: {province.reported_income:.2f} / {province.actual_income:.2f} gold")
                print(f"  Expenditure: {province.reported_expenditure:.2f} / {province.actual_expenditure:.2f} gold")

                surplus_reported = province.reported_income - province.reported_expenditure
                surplus_actual = province.actual_income - province.actual_expenditure
                print(f"  Surplus: {surplus_reported:.2f} / {surplus_actual:.2f} gold")

                if province.last_month_corrupted:
                    diff = province.actual_income - province.reported_income
                    print(f"  ⚠️  Officials concealed {diff:.2f} gold in income!")
        else:
            # Normal mode: only show reported values
            print(f"\n{'Provincial Reports':-^70}")
            for province in summary['provinces']:
                surplus = province.reported_income - province.reported_expenditure
                status = ""
                if province.last_month_corrupted:
                    status = " [Abnormal]"
                print(f"[{province.name}] Income: {province.reported_income:.2f}, "
                      f"Expenditure: {province.reported_expenditure:.2f}, "
                      f"Surplus: {surplus:.2f} gold{status}")

        print(f"\n{'='*70}")

    def show_national_status(self):
        """Display national status overview"""
        print(f"\n{'='*70}")
        print(f"Month {self.game.state['current_month']} National Status Overview")
        print(f"{'='*70}")

        # Treasury and revenue/expenditure overview
        summary = self.game.get_financial_summary()
        print(f"\nTreasury Overview:")
        print(f"  Month Start: {summary['month_starting_treasury']:.2f} gold")
        print(f"  Current: {summary['treasury']:.2f} gold")
        print(f"  Monthly Change: {summary['treasury'] - summary['month_starting_treasury']:+.2f} gold")

        # National revenue/expenditure statistics
        total_income = sum(p.actual_income for p in self.game.provinces)
        total_reported_income = sum(p.reported_income for p in self.game.provinces)
        total_expenditure = sum(p.actual_expenditure for p in self.game.provinces)
        total_reported_expenditure = sum(p.reported_expenditure for p in self.game.provinces)

        print(f"\nNational Revenue/Expenditure Statistics:")
        print(f"  Actual Income: {total_income:.2f} gold")
        print(f"  Reported Income: {total_reported_income:.2f} gold")
        print(f"  Actual Expenditure: {total_expenditure:.2f} gold")
        print(f"  Reported Expenditure: {total_reported_expenditure:.2f} gold")
        print(f"  Actual Surplus: {total_income - total_expenditure:+.2f} gold")
        print(f"  Reported Surplus: {total_reported_income - total_reported_expenditure:+.2f} gold")

        # Display provincial overview
        print(f"\nProvincial Overview:")
        for province in self.game.provinces:
            actual_surplus = province.actual_income - province.actual_expenditure
            reported_surplus = province.reported_income - province.reported_expenditure

            status = ""
            if province.last_month_corrupted:
                status = " (⚠️ Concealing)"

            print(f"  [{province.name}]{status}")
            if self.game.state['debug_mode']:
                print(f"    Income: {province.reported_income:.2f} / {province.actual_income:.2f} gold")
                print(f"    Surplus: {reported_surplus:.2f} / {actual_surplus:+.2f} gold")
            else:
                print(f"    Income: {province.reported_income:.2f}, Surplus: {reported_surplus:+.2f} gold")

        # National active events and effects
        print(f"\n{'Active Events and Effects':-^70}")
        active_events = self.game.event_manager.get_active_events(self.game.state['current_month'])

        if not active_events:
            print("  No active events")
        else:
            # Group by event type
            national_events = [e for e in active_events if e.event_type == 'national']
            province_events = [e for e in active_events if e.event_type == 'province']

            if national_events:
                print(f"\nNational Events ({len(national_events)}):")
                for event in national_events:
                    print(f"  • {event.name} (Severity: {event.severity:.1f})")
                    if event.continuous_effects:
                        for effect in event.continuous_effects:
                            if hasattr(effect, 'scope'):
                                scope = effect.scope.value if hasattr(effect.scope, 'value') else effect.scope
                                # operation may be string or enum
                                if hasattr(effect, 'operation'):
                                    operation = effect.operation.value if hasattr(effect.operation, 'value') else effect.operation
                                    if operation == 'multiply':
                                        percentage = effect.value * 100
                                        print(f"    → {scope}: x{1 + effect.value:.2f} ({percentage:+.0f}%)")
                                    else:
                                        print(f"    → {scope}: {effect.value:+.2f}")
                                else:
                                    print(f"    → {scope}: {effect.value:+.2f}")

            if province_events:
                print(f"\nProvincial Events ({len(province_events)}):")
                # Group by province
                events_by_province = {}
                for event in province_events:
                    province_id = getattr(event, 'province_id', None)
                    if province_id not in events_by_province:
                        events_by_province[province_id] = []
                    events_by_province[province_id].append(event)

                for province_id, events in events_by_province.items():
                    province = next((p for p in self.game.provinces if p.province_id == province_id), None)
                    if province:
                        print(f"  [{province.name}] {len(events)} events")
                        for event in events:
                            print(f"    • {event.name}")

        print(f"\n{'='*70}")
        input("\nPress Enter to continue...")

    def show_province_events(self):
        """View provincial events"""
        print(f"\n{'='*70}")
        print("Provincial Events List")
        print(f"{'='*70}")

        active_events = self.game.event_manager.get_active_events(
            self.game.state['current_month']
        )

        # Group by province
        province_events = {}
        for event in active_events:
            if hasattr(event, 'event_type') and event.event_type == 'province':
                province_id = getattr(event, 'province_id', None)
                if province_id is not None:
                    if province_id not in province_events:
                        province_events[province_id] = []
                    province_events[province_id].append(event)

        if not province_events:
            print("\nNo provincial events\n")
            return

        for province_id, events in province_events.items():
            province = next((p for p in self.game.provinces if p.province_id == province_id), None)
            if not province:
                continue

            print(f"\n[{province.name}]")

            for event in events:
                # Hidden events (invisible in non-Debug mode)
                if hasattr(event, 'visibility') and event.visibility == 'hidden' and not self.game.state['debug_mode']:
                    continue

                print(f"  Event: {getattr(event, 'name', 'Unknown')}")
                print(f"    Description: {getattr(event, 'description', 'No description')}")
                print(f"    Severity: {getattr(event, 'severity', 0):.1f}")

                # Display event effects
                if hasattr(event, 'continuous_effects') and event.continuous_effects:
                    print(f"    Event Effects:")
                    for i, effect in enumerate(event.continuous_effects, 1):
                        scope = effect.scope.value if hasattr(effect.scope, 'value') else effect.scope
                        op = "+" if effect.value > 0 else ""
                        if hasattr(effect, 'operation'):
                            # operation may be string or enum
                            operation = effect.operation.value if hasattr(effect.operation, 'value') else effect.operation
                            if operation == 'multiply':
                                percentage = effect.value * 100
                                print(f"      {i}. {scope} x{1 + effect.value:.2f} ({percentage:+.0f}%)")
                            else:
                                print(f"      {i}. {scope}: {op}{effect.value}")
                        else:
                            print(f"      {i}. {scope}: {op}{effect.value}")

                # Debug mode shows all details
                if self.game.state['debug_mode']:
                    print(f"    Visibility: {getattr(event, 'visibility', 'unknown')}")
                    print(f"    Hidden by Governor: {getattr(event, 'is_hidden_by_governor', False)}")
                    print(f"    Fabricated: {getattr(event, 'is_fabricated', False)}")

                print()

        input("\nPress Enter to continue...")

    def manage_projects(self):
        """Manage provincial projects"""
        print("\n=== Initiate Provincial Projects ===")
        print(f"Treasury Balance: {self.game.state['treasury']:.2f} gold\n")

        if self.game.state['treasury'] < 30:
            print("Insufficient treasury to start new projects!")
            return

        # Select province
        print("Select province:")
        for i, province in enumerate(self.game.provinces):
            print(f"{i+1}. {province.name}")

        try:
            prov_choice = int(input("\nEnter province number (0 to cancel): "))
            if prov_choice == 0:
                return
            if prov_choice < 1 or prov_choice > len(self.game.provinces):
                print("Invalid number!")
                return
        except ValueError:
            print("Please enter a number!")
            return

        province = self.game.provinces[prov_choice - 1]
        print(f"\nSelected: {province.name}")

        # Select project type
        print("\nProject Type:")
        print("1. Agricultural Reform (Cost: 50 gold) - Increase base income by 8%")
        print("2. Infrastructure Development (Cost: 80 gold) - Development level +0.5")
        print("3. Tax Relief (Cost: 30 gold) - Loyalty +15")
        print("4. Security Enhancement (Cost: 60 gold) - Stability +12")

        try:
            proj_choice = int(input("\nEnter project number (0 to cancel): "))
            if proj_choice == 0:
                return
            if proj_choice < 1 or proj_choice > 4:
                print("Invalid number!")
                return
        except ValueError:
            print("Please enter a number!")
            return

        project_types = ['agriculture', 'infrastructure', 'tax_relief', 'security']
        project_type = project_types[proj_choice - 1]

        # Create and add project
        project = Project(province.province_id, project_type,
                         self.game.state['current_month'])

        if self.game.state['treasury'] < project.cost:
            print(f"\nInsufficient treasury! Need {project.cost} gold, current balance: "
                  f"{self.game.state['treasury']:.2f} gold")
            return

        self.game.add_project(project)
        print(f"\n✓ Project started in {province.name}!")
        print(f"  Project Type: {self._get_project_name(project_type)}")
        print(f"  Cost: {project.cost} gold")
        print(f"  Effect: {self._get_project_effect(project)}")

    def _get_project_name(self, project_type: str) -> str:
        """Get project name"""
        names = {
            'agriculture': 'Agricultural Reform',
            'infrastructure': 'Infrastructure Development',
            'tax_relief': 'Tax Relief',
            'security': 'Security Enhancement'
        }
        return names.get(project_type, project_type)

    def _get_project_effect(self, project: Project) -> str:
        """Get project effect description"""
        if project.effect_type == 'income_bonus':
            return f"Base Income +{project.effect_value*100:.0f}%"
        elif project.effect_type == 'development_bonus':
            return f"Development Level +{project.effect_value}"
        elif project.effect_type == 'loyalty_bonus':
            return f"Loyalty +{project.effect_value}"
        elif project.effect_type == 'stability_bonus':
            return f"Stability +{project.effect_value}"
        return "Unknown"

    def fund_management(self):
        """Fund management interface"""
        while True:
            print(f"\n{'='*60}")
            print("Fund Management")
            print(f"{'='*60}")
            print(f"Current Treasury Balance: {self.game.treasury_system.get_national_balance():.2f} gold\n")

            print("1. Transfer to Province")
            print("2. Transfer from Province")
            print("3. Set Surplus Allocation Ratios")
            print("4. View Allocation Ratios")
            print("5. View National Transactions")
            print("6. View Provincial Transactions")
            print("0. Return to Main Menu")

            choice = input("\nSelect operation: ").strip()

            if choice == '1':
                self._transfer_to_province()
            elif choice == '2':
                self._transfer_from_province()
            elif choice == '3':
                self._set_allocation_ratios()
            elif choice == '4':
                self._view_allocation_ratios()
            elif choice == '5':
                self._view_national_transactions()
            elif choice == '6':
                self._view_provincial_transactions()
            elif choice == '0':
                break
            else:
                print("\nInvalid selection, please try again")

    def show_budget_execution(self):
        """View budget execution"""
        print(f"\n{'='*70}")
        print("Budget Execution")
        print(f"{'='*70}")

        current_month = self.game.state['current_month']
        current_year = (current_month - 1) // 12 + 1

        # Display central budget execution
        print("\n[Central Budget]")
        national_budget = self.game.budget_system.get_national_budget(current_year)
        if national_budget:
            allocated = national_budget['allocated_budget']
            spent = national_budget['actual_spent']
            remaining = allocated - spent
            execution_rate = (spent / allocated * 100) if allocated > 0 else 0

            print(f"  Total Budget: {allocated:.2f} gold")
            print(f"  Executed: {spent:.2f} gold")
            print(f"  Remaining: {remaining:.2f} gold")
            print(f"  Execution Rate: {execution_rate:.1f}%")
        else:
            print("  No budget data available")

        # Display provincial budgets
        print("\n[Provincial Budgets]")
        budgets = self.game.budget_system.get_current_budgets(current_year)

        if budgets['provinces']:
            for province_id, budget in budgets['provinces'].items():
                allocated = budget['allocated_budget']
                spent = budget['actual_spent']
                remaining = allocated - spent
                execution_rate = (spent / allocated * 100) if allocated > 0 else 0

                print(f"\n  {budget['name']}:")
                print(f"    Budget: {allocated:8.2f} gold")
                print(f"    Executed: {spent:8.2f} gold")
                print(f"    Remaining: {remaining:8.2f} gold")
                print(f"    Execution Rate: {execution_rate:6.1f}%")
        else:
            print("  No budget data available")

        input("\nPress Enter to continue...")

    def _transfer_to_province(self):
        """Transfer from national to province"""
        print("\n=== Transfer to Province ===")

        # Select province
        print("Select Province:")
        for i, province in enumerate(self.game.provinces):
            print(f"{i+1}. {province.name}")

        try:
            prov_choice = int(input("\nEnter Province Number (0 to cancel): "))
            if prov_choice == 0:
                return
            if prov_choice < 1 or prov_choice > len(self.game.provinces):
                print("Invalid number!")
                return
        except ValueError:
            print("Please enter a number!")
            return

        province = self.game.provinces[prov_choice - 1]

        # Enter amount
        try:
            amount = float(input("\nEnter transfer amount: "))
            if amount <= 0:
                print("Amount must be positive!")
                return
        except ValueError:
            print("Please enter a valid number!")
            return

        # Execute transfer
        current_month = self.game.state['current_month']
        current_year = (current_month - 1) // 12 + 1
        success, message = self.game.treasury_system.transfer_from_national_to_province(
            province.province_id, amount, current_month, current_year
        )

        if success:
            print(f"\n✓ {message}")
        else:
            print(f"\n✗ Failed: {message}")

        input("\nPress Enter to continue...")

    def _transfer_from_province(self):
        """Transfer from province to national"""
        print("\n=== Transfer from Province ===")

        # Select province
        print("Select Province:")
        for i, province in enumerate(self.game.provinces):
            balance = self.game.treasury_system.get_provincial_balance(province.province_id)
            print(f"{i+1}. {province.name} (Balance: {balance:.2f} gold)")

        try:
            prov_choice = int(input("\nEnter Province Number (0 to cancel): "))
            if prov_choice == 0:
                return
            if prov_choice < 1 or prov_choice > len(self.game.provinces):
                print("Invalid number!")
                return
        except ValueError:
            print("Please enter a number!")
            return

        province = self.game.provinces[prov_choice - 1]

        # Enter amount
        try:
            amount = float(input("\nEnter transfer amount: "))
            if amount <= 0:
                print("Amount must be positive!")
                return
        except ValueError:
            print("Please enter a valid number!")
            return

        # Execute transfer
        current_month = self.game.state['current_month']
        current_year = (current_month - 1) // 12 + 1
        success, message = self.game.treasury_system.transfer_from_province_to_national(
            province.province_id, amount, current_month, current_year
        )

        if success:
            print(f"\n✓ {message}")
        else:
            print(f"\n✗ Failed: {message}")

        input("\nPress Enter to continue...")

    def _set_allocation_ratios(self):
        """Set surplus allocation ratios for provinces"""
        print("\n=== Set Surplus Allocation Ratios ===")
        print("Ratio Range: 0.0-1.0 (0 = keep all local, 1.0 = transfer all)\n")

        # Set ratios for each province
        conn = self.game.db.get_connection()
        cursor = conn.cursor()

        for province in self.game.provinces:
            current_ratio = 0.5  # default
            cursor.execute("""
                SELECT ratio FROM surplus_allocation_ratios WHERE province_id = ?
            """, (province.province_id,))
            result = cursor.fetchone()
            if result:
                current_ratio = result[0]

            print(f"{province.name} (Current: {current_ratio:.2f})")
            try:
                new_ratio = input(f"  New Ratio (Press Enter to keep current): ").strip()
                if new_ratio:
                    ratio = float(new_ratio)
                    if 0 <= ratio <= 1:
                        cursor.execute("""
                            UPDATE surplus_allocation_ratios
                            SET ratio = ?
                            WHERE province_id = ?
                        """, (ratio, province.province_id))
                        print(f"    ✓ Set to {ratio:.2f}")
                    else:
                        print(f"    ✗ Ratio must be between 0.0 and 1.0")
            except ValueError:
                print(f"    ✗ Please enter a valid number")

        conn.commit()
        conn.close()
        print("\n✓ Allocation ratios updated")
        input("\nPress Enter to continue...")

    def _view_allocation_ratios(self):
        """View allocation ratios"""
        print(f"\n{'='*60}")
        print("Surplus Allocation Ratios")
        print(f"{'='*60}")
        print("(Ratio = share to national. E.g., 0.5 = 50% to national, 50% local)\n")

        conn = self.game.db.get_connection()
        cursor = conn.cursor()

        for province in self.game.provinces:
            cursor.execute("""
                SELECT ratio FROM surplus_allocation_ratios WHERE province_id = ?
            """, (province.province_id,))
            result = cursor.fetchone()
            ratio = result[0] if result else 0.5

            central_share = ratio * 100
            local_share = (1 - ratio) * 100

            print(f"{province.name:15s}: {ratio:.2f} ({central_share:.0f}% to national / {local_share:.0f}% local)")

        conn.close()
        input("\nPress Enter to continue...")

    def _view_national_transactions(self):
        """View national transaction history"""
        print(f"\n{'='*70}")
        print("National Transaction History (Last 10)")
        print(f"{'='*70}")

        transactions = self.game.treasury_system.get_national_transaction_history(limit=10)

        if not transactions:
            print("\nNo transaction records\n")
        else:
            print(f"{'Date':<12} {'Type':<20} {'Amount':>10} {'Balance':>10} {'Description'}")
            print("-" * 70)

            for t in transactions:
                date = f"{t['year']}-{t['month']:02d}"
                type_desc = self._get_transaction_type_desc(t['type'])
                amount = f"{t['amount']:+.2f}"
                balance = f"{t['balance_after']:.2f}"
                desc = t['description'][:30] if t['description'] else ""

                print(f"{date:<12} {type_desc:<20} {amount:>10} {balance:>10} {desc}")

        input("\nPress Enter to continue...")

    def _view_provincial_transactions(self):
        """View provincial transaction history"""
        print("\n=== Select Province to View Transaction History ===")

        # Select province
        for i, province in enumerate(self.game.provinces):
            print(f"{i+1}. {province.name}")

        try:
            prov_choice = int(input("\nEnter Province Number (0 to cancel): "))
            if prov_choice == 0:
                return
            if prov_choice < 1 or prov_choice > len(self.game.provinces):
                print("Invalid number!")
                return
        except ValueError:
            print("Please enter a number!")
            return

        province = self.game.provinces[prov_choice - 1]

        print(f"\n{'='*70}")
        print(f"{province.name} - Transaction History (Last 10)")
        print(f"{'='*70}")

        transactions = self.game.treasury_system.get_provincial_transaction_history(
            province.province_id, limit=10
        )

        if not transactions:
            print("\nNo transaction records\n")
        else:
            print(f"{'Date':<12} {'Type':<20} {'Amount':>10} {'Balance':>10} {'Description'}")
            print("-" * 70)

            for t in transactions:
                date = f"{t['year']}-{t['month']:02d}"
                type_desc = self._get_transaction_type_desc(t['type'])
                amount = f"{t['amount']:+.2f}"
                balance = f"{t['balance_after']:.2f}"
                desc = t['description'][:30] if t['description'] else ""

                print(f"{date:<12} {type_desc:<20} {amount:>10} {balance:>10} {desc}")

        input("\nPress Enter to continue...")

    def _get_transaction_type_desc(self, type_str: str) -> str:
        """Get transaction type description"""
        descriptions = {
            'income': 'Income',
            'expenditure': 'Expenditure',
            'allocation_province': 'Transfer to Province',
            'recall_province': 'Province Transfer',
            'surplus_allocation': 'Surplus Allocation',
            'transfer_to_national': 'Transfer to National',
            'central_allocation': 'Central Allocation',
            'surplus_rollover': 'Surplus Rollover'
        }
        return descriptions.get(type_str, type_str)
