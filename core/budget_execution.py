"""
Budget Execution Engine

Handles monthly budget execution, surplus allocation, overdraft detection and handling
"""

import random
from typing import Dict, List, Any, Optional, Tuple
from .budget_system import BudgetSystem
from .treasury_system import TreasurySystem
from events.overdraft_events import OVERDRAFT_EVENTS
from events.event_models import Event


class BudgetExecutor:
    """Budget Execution Engine class"""

    def __init__(self, budget_system: BudgetSystem, treasury_system: TreasurySystem, event_manager):
        """
        Initialize budget execution engine

        Args:
            budget_system: Budget system instance
            treasury_system: Treasury system instance
            event_manager: Event manager instance
        """
        self.budget_system = budget_system
        self.treasury_system = treasury_system
        self.event_manager = event_manager

    def execute_monthly_budget(self, game_state: Dict[str, Any], provinces: List[Any],
                              month: int, year: int) -> Dict[str, Any]:
        """
        Monthly budget execution

        Args:
            game_state: Game state
            provinces: List of province objects
            month: Current month
            year: Current year

        Returns:
            Execution result summary
        """
        results = {
            'province_executions': {},
            'total_central_income': 0,
            'total_central_allocation': 0
        }

        for province in provinces:
            province_id = province.province_id

            # Calculate monthly surplus = reported income - reported expenditure
            monthly_surplus = province.reported_income - province.reported_expenditure

            if monthly_surplus > 0:
                # Surplus processing
                execution_result = self._handle_surplus(
                    province, monthly_surplus, month, year
                )
            else:
                # Deficit processing
                execution_result = self._handle_deficit(
                    province, monthly_surplus, month, year
                )

            results['province_executions'][province_id] = execution_result
            results['total_central_income'] += execution_result.get('central_allocation', 0)
            results['total_central_allocation'] += execution_result.get('provincial_allocation', 0)

        return results

    def _handle_surplus(self, province: Any, surplus: float, month: int, year: int) -> Dict[str, Any]:
        """
        Handle province surplus

        Args:
            province: Province object
            surplus: Surplus amount (positive)
            month: Month
            year: Year

        Returns:
            Processing result
        """
        # GetAllocation ratio
        ratio = self._get_allocation_ratio(province.province_id)

        # Calculate allocation amount
        central_allocation = surplus * ratio  # Transfer to nationaltreasury
        provincial_allocation = surplus * (1 - ratio)  # Transfer to provincial treasury

        # Record transaction
        if central_allocation > 0:
            self.treasury_system.record_national_transaction(
                month=month,
                year=year,
                type='surplus_allocation',
                amount=central_allocation,
                province_id=province.province_id,
                description=f"Province {province.province_id} surplus transfer to national"
            )

        if provincial_allocation > 0:
            self.treasury_system.record_provincial_transaction(
                province_id=province.province_id,
                month=month,
                year=year,
                type='surplus_allocation',
                amount=provincial_allocation,
                description=f"Surplus retention to provincial treasury"
            )

        return {
            'type': 'surplus',
            'amount': surplus,
            'central_allocation': central_allocation,
            'provincial_allocation': provincial_allocation,
            'ratio': ratio
        }

    def _handle_deficit(self, province: Any, deficit: float, month: int, year: int) -> Dict[str, Any]:
        """
        Handle province deficit

        Args:
            province: Province object
            deficit: Deficit amount (negative)
            month: Month
            year: Year

        Returns:
            Processing result
        """
        deficit_amount = abs(deficit)

        # GetCurrentprovincial treasurybalance
        provincial_balance = self.treasury_system.get_provincial_balance(province.province_id)

        # Deduct from provincial treasury
        self.treasury_system.record_provincial_transaction(
            province_id=province.province_id,
            month=month,
            year=year,
            type='expenditure',
            amount=-deficit_amount,
            description=f"Monthly deficit deduction"
        )

        result = {
            'type': 'deficit',
            'amount': deficit,
            'covered_from_treasury': min(deficit_amount, provincial_balance),
            'remaining_deficit': max(0, deficit_amount - provincial_balance)
        }

        # Check if provincial treasury insufficient
        if provincial_balance < deficit_amount:
            # Process overdraft
            overdraft_handled = self._handle_province_overdraft(
                province, deficit_amount - provincial_balance, month, year
            )
            result['overdraft_handled'] = overdraft_handled

        return result

    def _get_allocation_ratio(self, province_id: int) -> float:
        """
        Getprovince盈余allocation比例

        Args:
            province_id: provinceID

        Returns:
            allocation比例（0-1，表示上交中央的比例）
        """
        conn = self.budget_system.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ratio FROM surplus_allocation_ratios
            WHERE province_id = ?
        """, (province_id,))

        result = cursor.fetchone()
        conn.close()

        return result[0] if result else 0.5  # 默认0.5

    def execute_central_budget(self, month: int, year: int) -> Dict[str, Any]:
        """
        Central budget execution

        Args:
            month: Month
            year: Year

        Returns:
            Execution result
        """
        # 固定支出300gold coins（Adjusted）
        fixed_expenditure = 300

        # CalculateEvents支出（如果有活跃Events）
        event_expenditure = self._calculate_event_expenditure()

        total_expenditure = fixed_expenditure + event_expenditure

        # GetCurrenttreasurybalance（扣款前）
        starting_balance = self.treasury_system.get_national_balance()

        # Deduct from national treasury
        self.treasury_system.record_national_transaction(
            month=month,
            year=year,
            type='expenditure',
            amount=-total_expenditure,
            description=f"中央Monthly expenditure (basic: {fixed_expenditure:.0f}, event: {event_expenditure:.0f}）"
        )

        # Get balance after deduction
        ending_balance = self.treasury_system.get_national_balance()

        result = {
            'fixed_expenditure': fixed_expenditure,
            'event_expenditure': event_expenditure,
            'total_expenditure': total_expenditure,
            'starting_balance': starting_balance,
            'ending_balance': ending_balance
        }

        # Check if national treasury insufficient
        if ending_balance < 0:
            # Process central overdraft
            overdraft_handled = self._handle_national_overdraft(
                abs(ending_balance), month, year
            )
            result['overdraft_handled'] = overdraft_handled

        return result

    def _calculate_event_expenditure(self) -> float:
        """
        Calculateevent导致的中央支出

        Returns:
            event支出金额
        """
        # 这里可以扩展为根据Events类型和严重程度Calculate支出
        # 目前简化为固定值
        return 0

    def _handle_province_overdraft(self, province: Any, overdraft_amount: float,
                                  month: int, year: int) -> bool:
        """
        Processprovince超支

        Args:
            province: province对象
            overdraft_amount: 超支金额
            month: 月份
            year: 年份

        Returns:
            bool: 是否SuccessProcess
        """
        # 随机选择一个超支Events模板
        event_template = random.choice(OVERDRAFT_EVENTS)

        # Create超支Events
        event = Event(
            event_id=f"overdraft_{province.province_id}_{month}_{year}_{random.randint(1000, 9999)}",
            name=event_template['name'],
            description=event_template['description'],
            event_type='province',
            province_id=province.province_id,
            severity=event_template['severity'],
            continuous_effects=event_template['effects'],
            start_month=month,
            end_month=month + 3,  # 持续3months
            is_active=True
        )

        # Agent决定是否hiddenEvents
        if hasattr(province, 'agent') and province.agent:
            should_hide = province.agent.decide_event_visibility(event)
            if should_hide:
                event.visibility = 'hidden'
                event.is_hidden_by_governor = True
                event.hidden_reason = f"官员选择隐瞒超支event（超支金额：{overdraft_amount:.2f}）"

        # AddEvents到EventsManage器
        self.event_manager.add_event(event)

        return True

    def _handle_national_overdraft(self, overdraft_amount: float, month: int, year: int) -> bool:
        """
        Process中央超支

        Args:
            overdraft_amount: 超支金额
            month: 月份
            year: 年份

        Returns:
            bool: 是否SuccessProcess
        """
        # Create central fiscal crisis event
        event = Event(
            event_id=f"national_crisis_{month}_{year}_{random.randint(1000, 9999)}",
            name="Central fiscal crisis",
            description=f"中央财政出现严重赤字，超支 {overdraft_amount:.2f} gold coins",
            event_type='national',
            severity=0.9,
            continuous_effects=[
                {'scope': 'stability', 'operation': 'multiply', 'value': -0.2},
                {'scope': 'loyalty', 'operation': 'add', 'value': -10}
            ],
            start_month=month,
            end_month=month + 6,  # 持续6months
            is_active=True
        )

        # AddEvents到EventsManage器
        self.event_manager.add_event(event)

        return True

    def rollover_annual_surplus(self, year: int) -> Dict[str, Any]:
        """
        年度结余结转

        Args:
            year: 年度

        Returns:
            结转Result
        """
        results = {
            'national_rollover': 0,
            'provincial_rollovers': {}
        }

        # Calculate central annual surplus
        national_budget = self.budget_system.get_national_budget(year)
        if national_budget:
            national_surplus = national_budget['allocated_budget'] - national_budget['actual_spent']

            if national_surplus > 0:
                # Record surplus carried forward to下年1月
                self.treasury_system.record_national_transaction(
                    month=1,
                    year=year + 1,
                    type='surplus_rollover',
                    amount=national_surplus,
                    description=f"{year}Annual surplus carried forward to"
                )

                results['national_rollover'] = national_surplus

        # Calculate provincial annual surplus
        conn = self.budget_system.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT province_id FROM provinces")
        provinces = cursor.fetchall()
        conn.close()

        for (province_id,) in provinces:
            provincial_budget = self.budget_system.get_provincial_budget(province_id, year)
            if provincial_budget:
                provincial_surplus = provincial_budget['allocated_budget'] - provincial_budget['actual_spent']

                if provincial_surplus > 0:
                    # Record surplus carried forward to下年1月
                    self.treasury_system.record_provincial_transaction(
                        province_id=province_id,
                        month=1,
                        year=year + 1,
                        type='surplus_rollover',
                        amount=provincial_surplus,
                        description=f"{year}Annual surplus carried forward to"
                    )

                    results['provincial_rollovers'][province_id] = provincial_surplus

        # Mark completed budgets为completed状态
        conn = self.budget_system.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE annual_budgets
            SET status = 'completed'
            WHERE year = ? AND status = 'active'
        """, (year,))
        conn.commit()
        conn.close()

        return results
