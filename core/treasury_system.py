"""
Treasury Management System

Manages national and provincial treasury fund flows, balance queries, and fund transfers
"""

import sqlite3
import uuid
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime


class TreasurySystem:
    """Treasury Management System class"""

    def __init__(self, db):
        """
        Initialize treasury system

        Args:
            db: Database instance
        """
        self.db = db

    def record_national_transaction(self, month: int, year: int, type: str,
                                   amount: float, province_id: Optional[int] = None,
                                   description: str = "") -> Optional[str]:
        """
        Record national treasury transaction

        Args:
            month: Month
            year: Year
            type: Transaction type ('income', 'expenditure', 'allocation_province',
                          'recall_province', 'surplus_allocation', 'surplus_rollover')
            amount: Amount (positive for income, negative for expenditure)
            province_id: Province ID (for allocation/recall records)
            description: Description

        Returns:
            transaction_id: Transaction ID or None (if failed)
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Get current national treasury balance
        current_balance = self.get_national_balance()
        new_balance = current_balance + amount

        # Record transaction
        transaction_id = f"national_{uuid.uuid4().hex[:12]}"
        cursor.execute("""
            INSERT INTO national_treasury_transactions
            (transaction_id, month, year, type, amount, province_id, description, balance_after)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (transaction_id, month, year, type, amount, province_id, description, new_balance))

        # Update national treasury balance in game state
        cursor.execute("""
            UPDATE game_state
            SET treasury = ?
            WHERE id = 1
        """, (new_balance,))

        conn.commit()
        conn.close()

        return transaction_id

    def get_national_balance(self) -> float:
        """
        Query national treasury balance

        Returns:
            Current national treasury balance
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT treasury FROM game_state WHERE id = 1")
        result = cursor.fetchone()

        conn.close()

        return result[0] if result else 0.0

    def get_national_transaction_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Query national treasury transaction history

        Args:
            limit: Record limit

        Returns:
            Transaction record list
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT transaction_id, month, year, type, amount, province_id,
                   description, balance_after
            FROM national_treasury_transactions
            ORDER BY year DESC, month DESC, transaction_id DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        transactions = []
        for row in rows:
            transactions.append({
                'transaction_id': row[0],
                'month': row[1],
                'year': row[2],
                'type': row[3],
                'amount': row[4],
                'province_id': row[5],
                'description': row[6],
                'balance_after': row[7]
            })

        return transactions

    def record_provincial_transaction(self, province_id: int, month: int, year: int,
                                     type: str, amount: float,
                                     description: str = "") -> Optional[str]:
        """
        Record provincial treasury transaction

        Args:
            province_id: Province ID
            month: Month
            year: Year
            type: Transaction type ('income', 'expenditure', 'central_allocation',
                          'surplus_allocation', 'transfer_to_national', 'surplus_rollover')
            amount: Amount (positive for income, negative for expenditure)
            description: Description

        Returns:
            transaction_id: Transaction ID or None (if failed)
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Get current provincial treasury balance
        current_balance = self.get_provincial_balance(province_id)
        new_balance = current_balance + amount

        # Record transaction
        transaction_id = f"provincial_{province_id}_{uuid.uuid4().hex[:12]}"
        cursor.execute("""
            INSERT INTO provincial_treasury_transactions
            (transaction_id, province_id, month, year, type, amount, description, balance_after)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (transaction_id, province_id, month, year, type, amount, description, new_balance))

        # Update provincial treasury balance
        cursor.execute("""
            UPDATE provinces
            SET provincial_treasury = ?
            WHERE province_id = ?
        """, (new_balance, province_id))

        conn.commit()
        conn.close()

        return transaction_id

    def get_provincial_balance(self, province_id: int) -> float:
        """
        Query provincial treasury balance

        Args:
            province_id: Province ID

        Returns:
            Current provincial treasury balance
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT provincial_treasury
            FROM provinces
            WHERE province_id = ?
        """, (province_id,))

        result = cursor.fetchone()
        conn.close()

        return result[0] if result and result[0] is not None else 0.0

    def get_provincial_transaction_history(self, province_id: int,
                                          limit: int = 10) -> List[Dict[str, Any]]:
        """
        Query provincial treasury transaction history

        Args:
            province_id: Province ID
            limit: Record limit

        Returns:
            Transaction record list
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT transaction_id, month, year, type, amount, description, balance_after
            FROM provincial_treasury_transactions
            WHERE province_id = ?
            ORDER BY year DESC, month DESC, transaction_id DESC
            LIMIT ?
        """, (province_id, limit))

        rows = cursor.fetchall()
        conn.close()

        transactions = []
        for row in rows:
            transactions.append({
                'transaction_id': row[0],
                'month': row[1],
                'year': row[2],
                'type': row[3],
                'amount': row[4],
                'description': row[5],
                'balance_after': row[6]
            })

        return transactions

    def transfer_from_national_to_province(self, province_id: int, amount: float,
                                          month: int, year: int) -> Tuple[bool, str]:
        """
        Transfer from national to province

        Args:
            province_id: Province ID
            amount: Allocation amount (must be positive)
            month: Month
            year: Year

        Returns:
            Tuple[bool, str]: (Whether successful, message)
        """
        if amount <= 0:
            return False, "Allocation amount must be positive"

        # Check national treasury balance
        national_balance = self.get_national_balance()
        if national_balance < amount:
            return False, f"Insufficient national treasury balance (Current: {national_balance:.2f}, Required: {amount:.2f})"

        # Record national expenditure
        self.record_national_transaction(
            month=month,
            year=year,
            type='allocation_province',
            amount=-amount,
            province_id=province_id,
            description=f"Central allocation to province {province_id}"
        )

        # Record provincial income
        self.record_provincial_transaction(
            province_id=province_id,
            month=month,
            year=year,
            type='central_allocation',
            amount=amount,
            description=f"收到中央拨款"
        )

        return True, f"Successfully allocated {amount:.2f} gold coins to province {province_id}"

    def transfer_from_province_to_national(self, province_id: int, amount: float,
                                          month: int, year: int) -> Tuple[bool, str]:
        """
        Provincial surplus transfer to national给中央

        Args:
            province_id: 省份ID
            amount: 上缴金额（必须为正数）
            month: 月份
            year: 年份

        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        if amount <= 0:
            return False, "上缴金额必须为正数"

        # Check省库余额
        provincial_balance = self.get_provincial_balance(province_id)
        if provincial_balance < amount:
            return False, f"省库余额不足（当前: {provincial_balance:.2f}，需要: {amount:.2f}）"

        # 记录省库支出
        self.record_provincial_transaction(
            province_id=province_id,
            month=month,
            year=year,
            type='transfer_to_national',
            amount=-amount,
            description=f"Transfer to central government"
        )

        # 记录国库收入
        self.record_national_transaction(
            month=month,
            year=year,
            type='recall_province',
            amount=amount,
            province_id=province_id,
            description=f"省份{province_id}上缴"
        )

        return True, f"省份{province_id}成功上缴 {amount:.2f} 金币"

    def get_all_provincial_balances(self) -> Dict[int, float]:
        """
        获取所有省份的省库余额

        Returns:
            字典：{province_id: balance}
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT province_id, provincial_treasury
            FROM provinces
            WHERE provincial_treasury IS NOT NULL
        """)

        rows = cursor.fetchall()
        conn.close()

        balances = {}
        for row in rows:
            balances[row[0]] = row[1] or 0.0

        return balances

    def initialize_provincial_treasury(self, province_id: int, initial_amount: float):
        """
        初始化省库余额

        Args:
            province_id: 省份ID
            initial_amount: 初始金额
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Set initial balance
        cursor.execute("""
            UPDATE provinces
            SET provincial_treasury = ?
            WHERE province_id = ?
        """, (initial_amount, province_id))

        conn.commit()
        conn.close()
