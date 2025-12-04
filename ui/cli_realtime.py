"""
Simplified Real-time Refresh CLI Interface

Only refreshes when entering different menu interfaces, auto-refresh removed
"""

import sys
import asyncio
from datetime import datetime
from typing import Optional
from core.game import Game


class RealtimeGameCLI:
    """Real-time refresh CLI interface (simplified)"""

    def __init__(self, game: Game):
        """Initialize CLI

        Args:
            game: Game instance
        """
        self.game = game

    def clear_screen(self):
        """Clear screen"""
        print("\033[2J\033[H", end="")  # ANSI clear screen and move cursor to top left

    def draw_dashboard(self):
        """Draw dashboard"""
        current_month = self.game.state['current_month']
        current_year = (current_month - 1) // 12 + 1
        treasury = self.game.state['treasury']
        debug_mode = self.game.state['debug_mode']

        # Clear screen
        self.clear_screen()

        # Title
        print(f"\033[1m\033[36m{'='*80}\033[0m")
        print(f"\033[1m\033[36mEU4 Style Strategy Game - Real-time Dashboard{' '*45}\033[0m")
        print(f"\033[1m\033[36m{'='*80}\033[0m")
        print()

        # Basic info
        print(f"\033[1m{'Game Time:'}\033[0m Month {current_month} (Year {current_year})")
        print(f"\033[1m{'Treasury Balance:'}\033[0m \033[33m{treasury:>10.2f}\033[0m gold")
        debug_status = "[32mON[0m" if debug_mode else "[31mOFF[0m"
        print(f"[1m{'Debug Mode:'}[0m {debug_status}")
        print()

        # Active events
        active_events = self.game.event_manager.get_active_events(current_month)
        national_events = [e for e in active_events if str(e.event_type) == 'national']
        province_events = [e for e in active_events if str(e.event_type) == 'province']

        print(f"\033[1mActive Events:\033[0m National \033[33m{len(national_events)}\033[0m, "
              f"Provincial \033[33m{len(province_events)}\033[0m")
        print()

        # Budget execution
        print(f"\033[1m\033[34m{'─'*80}\033[0m")
        print(f"\033[1mBudget Execution:\033[0m")
        print(f"\033[1m\033[34m{'─'*80}\033[0m")

        budgets = self.game.budget_system.get_current_budgets(current_year)
        if budgets['national']:
            national = budgets['national']
            execution_rate = (national['actual_spent'] / national['allocated_budget'] * 100)                            if national['allocated_budget'] > 0 else 0
            remaining = national['allocated_budget'] - national['actual_spent']

            print(f"\033[1mCentral Budget:\033[0m")
            print(f"  Total Budget: \033[33m{national['allocated_budget']:>10.2f}\033[0m gold")
            print(f"  Executed: \033[33m{national['actual_spent']:>10.2f}\033[0m gold")
            print(f"  Remaining: \033[33m{remaining:>10.2f}\033[0m gold")
            print(f"  Execution Rate: \033[33m{execution_rate:>9.1f}%\033[0m")
            print()

        # Province overview
        print(f"\033[1m\033[34m{'─'*80}\033[0m")
        print(f"\033[1mProvincial Overview:\033[0m")
        print(f"\033[1m\033[34m{'─'*80}\033[0m")
        print()

        # Header
        print(f"{'Province':<12} {'Loyalty':<8} {'Stability':<8} {'Provincial Balance':<18} {'Status'}")
        print(f"{'─'*12} {'─'*8} {'─'*8} {'─'*18} {'─'*20}")

        # Province data
        for province in self.game.provinces:
            balance = self.game.treasury_system.get_provincial_balance(province.province_id)

            # Status indicator
            status = ""
            if province.last_month_corrupted:
                status = "\033[31mConcealing\033[0m"
            elif province.loyalty < 60:
                status = "\033[33mLow Loyalty\033[0m"
            elif province.stability < 60:
                status = "\033[33mLow Stability\033[0m"
            else:
                status = "\033[32mNormal\033[0m"

            print(f"\033[1m{province.name:<12}\033[0m "
                  f"{province.loyalty:<8.0f} "
                  f"{province.stability:<8.0f} "
                  f"\033[33m{balance:>18.2f}\033[0m "
                  f"{status}")

        print()

        # Action menu
        print(f"\033[1m\033[34m{'─'*80}\033[0m")
        print(f"\033[1mAction Menu:\033[0m")
        print(f"\033[1m\033[34m{'─'*80}\033[0m")
        print("  1. Financial Report  2. Project Management  3. Toggle Debug  4. Next Month  5. Provincial Events")
        print("  6. National Status  7. Fund Management  8. Budget Execution  9. Refresh  Q. Exit")
        print()

        # Last update time
        now = datetime.now().strftime("%H:%M:%S")
        print(f"\033[90mLast Updated: {now} (Enter number for menu, Q to exit)\033[0m")
        print()

    def show_main_menu(self):
        """Display main menu (refresh dashboard)"""
        self.draw_dashboard()

        try:
            choice = input("\nSelect operation: ").strip()

            if choice.lower() == 'q':
                return False  # Exit

            # Process choice
            self.handle_choice(choice)

            return True  # Continue

        except (KeyboardInterrupt, EOFError):
            return False

    def handle_choice(self, choice: str):
        """Handle user choice

        Args:
            choice: User input
        """
        if choice == '1':
            self.show_financial_report()
        elif choice == '2':
            self.manage_projects()
        elif choice == '3':
            self.game.toggle_debug_mode()
            print("\033[32mDebug Mode toggled\033[0m")
            input("\nPress Enter to return to dashboard...")
        elif choice == '4':
            print()
            asyncio.run(self.game.next_month())
            input("\nPress Enter to return to dashboard...")
        elif choice == '5':
            self.show_province_events()
        elif choice == '6':
            self.show_national_status()
        elif choice == '7':
            self.fund_management()
        elif choice == '8':
            self.show_budget_execution()
        elif choice == '9':
            # Refresh dashboard
            pass
        else:
            print(f"\nInvalid choice: {choice}")
            input("\nPress Enter to continue...")

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
            print(f"\n{'Provincial Reports':-^70}")
            for province in summary['provinces']:
                surplus = province.reported_income - province.reported_expenditure
                status = ""
                if province.last_month_corrupted:
                    status = " [Abnormal]"
                print(f"[{province.name}] Income: {province.reported_income:.2f}, Expense: {province.reported_expenditure:.2f}, "
                      f"Surplus: {surplus:.2f} gold{status}")

        print(f"\n{'='*70}")
        input("\nPress Enter to return to dashboard...")

    def manage_projects(self):
        """Manage projects"""
        from ui.cli import GameCLI
        old_cli = GameCLI(self.game)
        old_cli.manage_projects()

    def show_province_events(self):
        """View provincial events"""
        from ui.cli import GameCLI
        old_cli = GameCLI(self.game)
        old_cli.show_province_events()

    def show_national_status(self):
        """View national status"""
        from ui.cli import GameCLI
        old_cli = GameCLI(self.game)
        old_cli.show_national_status()

    def fund_management(self):
        """Fund management"""
        from ui.cli import GameCLI
        old_cli = GameCLI(self.game)
        old_cli.fund_management()

    def show_budget_execution(self):
        """View budget execution"""
        from ui.cli import GameCLI
        old_cli = GameCLI(self.game)
        old_cli.show_budget_execution()

    def run(self):
        """Main run loop"""
        print("\033[?25h", end="")  # Ensure cursor visible

        try:
            while True:
                # Draw dashboard
                self.draw_dashboard()

                # Handle user input
                if not self.show_main_menu():
                    break  # Exit

        except KeyboardInterrupt:
            print("\n\nGame exited")
        finally:
            print("\033[?25h", end="")  # Ensure cursor visible
            print("\033[0m", end="")    # Reset color
            print("\nThanks for playing!")
