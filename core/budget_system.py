"""
Budget Management System

Manages generation, adjustment, querying and execution tracking of annual budgets
"""

import sqlite3
import uuid
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime


class BudgetSystem:
    """Budget Management System class"""

    def __init__(self, db):
        """
        Initialize budget system

        Args:
            db: Database instance
        """
        self.db = db

    def generate_national_budget(self, year: int) -> str:
        """
        Generate central budget based on historical data

        Args:
            year: Budget year

        Returns:
            budget_id: Generated budget ID
        """
        # Query central actual expenditure for past 12 months
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT SUM(amount) as total_expenditure
            FROM national_treasury_transactions
            WHERE type = 'expenditure'
            AND ((year = ? AND month <= 12) OR (year = ?))
            ORDER BY year DESC, month DESC
            LIMIT 12
        """, (year - 1, year - 2))

        result = cursor.fetchone()
        avg_monthly_expenditure = (result[0] or 2000) / 12  # Default 2000 gold coins/year

        # Calculate budget = average × 1.1 (+10% buffer)
        annual_budget = avg_monthly_expenditure * 12 * 1.1

        # Save to annual_budgets table
        budget_id = f"national_{year}_{uuid.uuid4().hex[:8]}"
        cursor.execute("""
            INSERT INTO annual_budgets (budget_id, year, province_id, allocated_budget, status)
            VALUES (?, ?, NULL, ?, 'draft')
        """, (budget_id, year, annual_budget))

        conn.commit()
        conn.close()

        return budget_id

    def generate_provincial_budgets(self, year: int) -> List[str]:
        """
        Generate budget for each province

        Args:
            year: Budget year

        Returns:
            budget_ids: List of generated budget IDs
        """
        budget_ids = []
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Get all provinces
        cursor.execute("SELECT province_id FROM provinces")
        provinces = cursor.fetchall()

        for (province_id,) in provinces:
            # Query actual expenditure for this province over past 12 months
            cursor.execute("""
                SELECT SUM(amount) as total_expenditure
                FROM provincial_treasury_transactions
                WHERE province_id = ?
                AND type = 'expenditure'
                AND ((year = ? AND month <= 12) OR (year = ?))
                ORDER BY year DESC, month DESC
                LIMIT 12
            """, (province_id, year - 1, year - 2))

            result = cursor.fetchone()
            avg_monthly_expenditure = (result[0] or 100) / 12  # Default 100 gold coins/year

            # Calculate budget = average × 1.1 (+10% buffer)
            annual_budget = avg_monthly_expenditure * 12 * 1.1

            # Save to annual_budgets table
            budget_id = f"province_{province_id}_{year}_{uuid.uuid4().hex[:8]}"
            cursor.execute("""
                INSERT INTO annual_budgets (budget_id, year, province_id, allocated_budget, status)
                VALUES (?, ?, ?, ?, 'draft')
            """, (budget_id, year, province_id, annual_budget))

            budget_ids.append(budget_id)

        conn.commit()
        conn.close()

        return budget_ids

    def adjust_national_budget(self, year: int, adjustment: float) -> bool:
        """
        Adjust national budget

        Args:
            year: Budget year
            adjustment: Adjustment amount (positive for increase, negative for decrease)

        Returns:
            bool: Whether successful
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE annual_budgets
            SET allocated_budget = allocated_budget + ?
            WHERE year = ? AND province_id IS NULL AND status = 'draft'
        """, (adjustment, year))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return success

    def adjust_provincial_budget(self, province_id: int, year: int, adjustment: float) -> bool:
        """
        Adjust provincial budget

        Args:
            province_id: Province ID
            year: Budget year
            adjustment: Adjustment amount (positive for increase, negative for decrease)

        Returns:
            bool: Whether successful
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE annual_budgets
            SET allocated_budget = allocated_budget + ?
            WHERE year = ? AND province_id = ? AND status = 'draft'
        """, (adjustment, year, province_id))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return success

    def get_national_budget(self, year: int) -> Optional[Dict[str, Any]]:
        """
        Get national budget

        Args:
            year: Budget year

        Returns:
            Budget information dictionary or None
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT budget_id, year, allocated_budget, actual_spent, status
            FROM annual_budgets
            WHERE year = ? AND province_id IS NULL
        """, (year,))

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                'budget_id': result[0],
                'year': result[1],
                'allocated_budget': result[2],
                'actual_spent': result[3],
                'status': result[4]
            }
        return None

    def get_provincial_budget(self, province_id: int, year: int) -> Optional[Dict[str, Any]]:
        """
        Get provincial budget

        Args:
            province_id: Province ID
            year: Budget year

        Returns:
            Budget information dictionary or None
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT budget_id, year, allocated_budget, actual_spent, status
            FROM annual_budgets
            WHERE year = ? AND province_id = ?
        """, (year, province_id))

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                'budget_id': result[0],
                'year': result[1],
                'allocated_budget': result[2],
                'actual_spent': result[3],
                'status': result[4]
            }
        return None

    def generate_budget_advice(self, year: int) -> Dict[str, Any]:
        """
        Generate budget recommendations based on historical data

        Args:
            year: Budget year

        Returns:
            Recommendation dictionary: {'national': value, 'provinces': {province_id: value}}
        """
        advice = {'national': 0, 'provinces': {}}
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Central recommendation
        cursor.execute("""
            SELECT AVG(amount) as avg_monthly_expenditure
            FROM national_treasury_transactions
            WHERE type = 'expenditure'
            AND year = ?
        """, (year - 1,))

        result = cursor.fetchone()
        avg_monthly = result[0] or (2000 / 12)  # Default 2000 gold/year
        national_advice = avg_monthly * 12 * 1.1
        advice['national'] = round(national_advice, 2)

        # Provincial recommendations
        cursor.execute("SELECT province_id FROM provinces")
        provinces = cursor.fetchall()

        for (province_id,) in provinces:
            cursor.execute("""
                SELECT AVG(amount) as avg_monthly_expenditure
                FROM provincial_treasury_transactions
                WHERE province_id = ?
                AND type = 'expenditure'
                AND year = ?
            """, (province_id, year - 1))

            result = cursor.fetchone()
            avg_monthly = result[0] or (100 / 12)  # Default 100 gold/year
            provincial_advice = avg_monthly * 12 * 1.1
            advice['provinces'][province_id] = round(provincial_advice, 2)

        conn.close()
        return advice

    def get_current_budgets(self, year: int) -> Dict[str, Any]:
        """
        Get all active budgets

        Args:
            year: Budget year

        Returns:
            Budget information dictionary
        """
        budgets = {'national': None, 'provinces': {}}
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Get central budget
        budgets['national'] = self.get_national_budget(year)

        # Get provincial budgets
        cursor.execute("SELECT province_id, name FROM provinces")
        provinces = cursor.fetchall()

        for province_id, province_name in provinces:
            budget = self.get_provincial_budget(province_id, year)
            if budget:
                budgets['provinces'][province_id] = {
                    'name': province_name,
                    **budget
                }

        conn.close()
        return budgets

    def activate_budgets(self, year: int) -> bool:
        """
        Activate new year budget

        Args:
            year: Budget year

        Returns:
            bool: Whether successful
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Activate draft budgets
        cursor.execute("""
            UPDATE annual_budgets
            SET status = 'active'
            WHERE year = ? AND status = 'draft'
        """, (year,))

        activated = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return activated

    def record_budget_expenditure(self, budget_id: str, amount: float) -> bool:
        """
        Record budget actual expenditure

        Args:
            budget_id: Budget ID
            amount: Expenditure amount

        Returns:
            bool: Whether successful
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE annual_budgets
            SET actual_spent = actual_spent + ?
            WHERE budget_id = ?
        """, (amount, budget_id))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return success
