"""
Database operation module
Uses SQLite to store game state
"""

import sqlite3
import os
from typing import List, Dict, Any, Optional
from .event_database import save_event, get_active_events, update_event


class Database:
    """Game database management class"""

    def __init__(self, db_path: str = "game.db"):
        """Initialize database connection"""
        self.db_path = db_path
        self.init_database()

    # Add event system methods
    save_event = save_event
    get_active_events = get_active_events
    update_event = update_event

    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)

    def init_database(self):
        """Initialize database table structure (if not exists)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Create events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                event_type TEXT NOT NULL,
                province_id INTEGER,
                instant_effects TEXT,
                continuous_effects TEXT,
                start_month INTEGER,
                end_month INTEGER,
                is_active BOOLEAN DEFAULT 1,
                visibility TEXT DEFAULT 'provincial',
                is_hidden_by_governor BOOLEAN DEFAULT 0,
                hidden_reason TEXT,
                severity REAL DEFAULT 0.5,
                public_perception TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_agent_generated BOOLEAN DEFAULT 0,
                is_fabricated BOOLEAN DEFAULT 0,
                fabrication_reason TEXT,
                generated_by_agent_id TEXT,
                narrative_consistency_score REAL,
                verification_status TEXT
            )
        """)

        # Provinces table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS provinces (
                province_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                population INTEGER,
                development_level REAL,
                loyalty REAL,
                stability REAL,
                base_income REAL,
                actual_income REAL,
                actual_expenditure REAL,
                reported_income REAL,
                reported_expenditure REAL,
                corruption_tendency REAL,
                last_month_corrupted BOOLEAN
            )
        """)

        # Game state table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                current_month INTEGER DEFAULT 1,
                treasury REAL DEFAULT 1000.0,
                month_starting_treasury REAL DEFAULT 1000.0,
                debug_mode BOOLEAN DEFAULT 1
            )
        """)

        # Projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                project_id INTEGER PRIMARY KEY AUTOINCREMENT,
                province_id INTEGER,
                project_type TEXT,
                cost REAL,
                effect_type TEXT,
                effect_value REAL,
                month_created INTEGER,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (province_id) REFERENCES provinces (province_id)
            )
        """)

        # Monthly reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monthly_reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                month INTEGER,
                province_id INTEGER,
                reported_income REAL,
                reported_expenditure REAL,
                actual_income REAL,
                actual_expenditure REAL,
                treasury_change REAL,
                FOREIGN KEY (province_id) REFERENCES provinces (province_id)
            )
        """)

        # ========== Budget System Tables ==========
        # Create annual budget table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS annual_budgets (
                budget_id TEXT PRIMARY KEY,
                year INTEGER NOT NULL,
                province_id INTEGER,
                allocated_budget REAL DEFAULT 0,
                actual_spent REAL DEFAULT 0,
                status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'completed'))
            )
        """)

        # Create national treasury transaction table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS national_treasury_transactions (
                transaction_id TEXT PRIMARY KEY,
                month INTEGER NOT NULL,
                year INTEGER NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('income', 'expenditure', 'allocation_province',
                               'recall_province', 'surplus_allocation', 'surplus_rollover')),
                amount REAL NOT NULL,
                province_id INTEGER,
                description TEXT,
                balance_after REAL
            )
        """)

        # Create provincial treasury transaction table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS provincial_treasury_transactions (
                transaction_id TEXT PRIMARY KEY,
                province_id INTEGER NOT NULL,
                month INTEGER NOT NULL,
                year INTEGER NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('income', 'expenditure', 'central_allocation',
                               'surplus_allocation', 'transfer_to_national', 'surplus_rollover')),
                amount REAL NOT NULL,
                description TEXT,
                balance_after REAL,
                FOREIGN KEY (province_id) REFERENCES provinces (province_id)
            )
        """)

        # Extend provinces table (add provincial treasury balance field)
        try:
            cursor.execute("""
                ALTER TABLE provinces ADD COLUMN provincial_treasury REAL DEFAULT 0
            """)
        except sqlite3.OperationalError:
            # Column already exists, ignore error
            pass

        # Create surplus allocation ratios table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS surplus_allocation_ratios (
                province_id INTEGER PRIMARY KEY,
                ratio REAL DEFAULT 0.5 CHECK (ratio >= 0 AND ratio <= 1),
                FOREIGN KEY (province_id) REFERENCES provinces (province_id)
            )
        """)

        # Initialize game data (if running for the first time)
        self.init_game_data(cursor)

        conn.commit()
        conn.close()

    def init_game_data(self, cursor):
        """Initialize game data"""
        # Check if data already exists
        cursor.execute("SELECT COUNT(*) FROM provinces")
        if cursor.fetchone()[0] == 0:
            # Initialize province data - single province, merge all attributes
            provinces = [
                (1, 'Capital', 35000, 7.0, 85, 72, 850, 0.4)
            ]

            cursor.executemany("""
                INSERT INTO provinces (
                    province_id, name, population, development_level,
                    loyalty, stability, base_income, corruption_tendency
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, provinces)

            # Initialize game state
            cursor.execute("""
                INSERT INTO game_state (id, current_month, treasury, debug_mode)
                VALUES (1, 1, 1000.0, 1)
            """)

    def load_game_state(self) -> Dict[str, Any]:
        """Load game state"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM game_state WHERE id = 1")
        row = cursor.fetchone()

        conn.close()

        if row:
            return {
                'id': row[0],
                'current_month': row[1],
                'treasury': row[2],
                'month_starting_treasury': row[3],
                'debug_mode': bool(row[4])
            }
        return None

    def save_game_state(self, state: Dict[str, Any]):
        """Save game state"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE game_state SET
                current_month = ?,
                treasury = ?,
                month_starting_treasury = ?,
                debug_mode = ?
            WHERE id = 1
        """, (
            state['current_month'],
            state['treasury'],
            state['month_starting_treasury'],
            state['debug_mode']
        ))

        conn.commit()
        conn.close()

    def load_provinces(self) -> List[Dict[str, Any]]:
        """Load all province data"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM provinces")
        rows = cursor.fetchall()

        conn.close()

        provinces = []
        for row in rows:
            provinces.append({
                'province_id': row[0],
                'name': row[1],
                'population': row[2],
                'development_level': row[3],
                'loyalty': row[4],
                'stability': row[5],
                'base_income': row[6],
                'actual_income': row[7] or 0,
                'actual_expenditure': row[8] or 0,
                'reported_income': row[9] or 0,
                'reported_expenditure': row[10] or 0,
                'corruption_tendency': row[11],
                'last_month_corrupted': bool(row[12])
            })

        return provinces

    def save_provinces(self, provinces: List[Dict[str, Any]]):
        """Save province data"""
        conn = self.get_connection()
        cursor = conn.cursor()

        for province in provinces:
            cursor.execute("""
                UPDATE provinces SET
                    population = ?,
                    development_level = ?,
                    loyalty = ?,
                    stability = ?,
                    base_income = ?,
                    actual_income = ?,
                    actual_expenditure = ?,
                    reported_income = ?,
                    reported_expenditure = ?,
                    last_month_corrupted = ?
                WHERE province_id = ?
            """, (
                province['population'],
                province['development_level'],
                province['loyalty'],
                province['stability'],
                province['base_income'],
                province['actual_income'],
                province['actual_expenditure'],
                province['reported_income'],
                province['reported_expenditure'],
                province['last_month_corrupted'],
                province['province_id']
            ))

        conn.commit()
        conn.close()

    def add_monthly_report(self, month: int, province_id: int,
                          reported_income: float, reported_expenditure: float,
                          actual_income: float, actual_expenditure: float,
                          treasury_change: float):
        """Add monthly report"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO monthly_reports (
                month, province_id,
                reported_income, reported_expenditure,
                actual_income, actual_expenditure, treasury_change
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (month, province_id, reported_income, reported_expenditure,
              actual_income, actual_expenditure, treasury_change))

        conn.commit()
        conn.close()

    def get_active_projects(self) -> List[Dict[str, Any]]:
        """Get all active projects"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM projects
            WHERE status = 'active'
        """)
        rows = cursor.fetchall()

        conn.close()

        projects = []
        for row in rows:
            projects.append({
                'project_id': row[0],
                'province_id': row[1],
                'project_type': row[2],
                'cost': row[3],
                'effect_type': row[4],
                'effect_value': row[5],
                'month_created': row[6],
                'status': row[7]
            })

        return projects

    def add_project(self, project: Dict[str, Any]):
        """Add new project"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO projects (
                province_id, project_type, cost,
                effect_type, effect_value, month_created
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            project['province_id'],
            project['project_type'],
            project['cost'],
            project['effect_type'],
            project['effect_value'],
            project['month_created']
        ))

        conn.commit()
        conn.close()

    def complete_project(self, project_id: int):
        """Mark project as completed"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE projects SET status = 'completed'
            WHERE project_id = ?
        """, (project_id,))

        conn.commit()
        conn.close()

    # ========== Province Agent Methods ==========

    def get_monthly_report(self, province_id: int, month: int, year: int) -> Optional[Dict[str, Any]]:
        """Get monthly report for a specific month"""
        import json
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM monthly_reports
            WHERE province_id = ? AND month = ? AND (year = ? OR year IS NULL)
        """, (province_id, month, year))
        row = cursor.fetchone()
        conn.close()

        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None

    def get_province(self, province_id: int) -> Optional[Dict[str, Any]]:
        """Get province data"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM provinces WHERE province_id = ?", (province_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None

    def get_events_for_month(self, province_id: int, month: int, year: int) -> List[Dict[str, Any]]:
        """Get all events for a specific month"""
        import json
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM events
            WHERE province_id = ? AND month = ? AND end_month = ?
        """, (province_id, month, month))
        rows = cursor.fetchall()
        conn.close()

        if rows:
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        return []

    def get_quarterly_summary(self, province_id: int, quarter: int, year: int) -> Optional[Dict[str, Any]]:
        """Get quarterly summary from database or None if not exists"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM province_quarterly_summaries
            WHERE province_id = ? AND quarter = ? AND year = ?
        """, (province_id, quarter, year))
        row = cursor.fetchone()
        conn.close()

        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None

    def save_quarterly_summary(self, province_id: int, quarter: int, year: int,
                               avg_income: float, median_income: float,
                               avg_expenditure: float, median_expenditure: float,
                               total_surplus: float, income_trend: str,
                               expenditure_trend: str, loyalty_change: float,
                               stability_change: float, major_events: List[str],
                               special_event_types: List[str], summary: str) -> int:
        """Save quarterly summary to database, returns summary_id"""
        import json
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO province_quarterly_summaries
            (province_id, quarter, year, avg_income, median_income, avg_expenditure,
             median_expenditure, total_surplus, income_trend, expenditure_trend,
             loyalty_change, stability_change, major_events, special_event_types, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            province_id, quarter, year,
            avg_income, median_income, avg_expenditure,
            median_expenditure, total_surplus,
            income_trend, expenditure_trend,
            loyalty_change, stability_change,
            json.dumps(major_events),
            json.dumps(special_event_types),
            summary
        ))
        summary_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return summary_id

    def get_annual_summary(self, province_id: int, year: int) -> Optional[Dict[str, Any]]:
        """Get annual summary from database or None if not exists"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM province_annual_summaries
            WHERE province_id = ? AND year = ?
        """, (province_id, year))
        row = cursor.fetchone()
        conn.close()

        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None

    def save_annual_summary(self, province_id: int, year: int,
                           total_income: float, total_expenditure: float,
                           avg_monthly_income: float, avg_monthly_expenditure: float,
                           total_surplus: float, population_change: int,
                           development_change: float, loyalty_start: float,
                           loyalty_end: float, loyalty_change: float,
                           major_events: List[str], disaster_count: int,
                           rebellion_count: int, performance_rating: str,
                           summary: str) -> int:
        """Save annual summary to database, returns summary_id"""
        import json
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO province_annual_summaries
            (province_id, year, total_income, total_expenditure, avg_monthly_income,
             avg_monthly_expenditure, total_surplus, population_change, development_change,
             loyalty_start, loyalty_end, loyalty_change, major_events,
             disaster_count, rebellion_count, performance_rating, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            province_id, year,
            total_income, total_expenditure,
            avg_monthly_income, avg_monthly_expenditure,
            total_surplus, population_change, development_change,
            loyalty_start, loyalty_end, loyalty_change,
            json.dumps(major_events),
            disaster_count, rebellion_count,
            performance_rating, summary
        ))
        summary_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return summary_id

    def get_special_events(self, province_id: int, categories: List[str], limit: int = 8) -> List[Dict[str, Any]]:
        """Get special events from index, ordered by severity desc"""
        conn = self.get_connection()
        cursor = conn.cursor()
        placeholders = ','.join(['?' for _ in categories])
        cursor.execute(f"""
            SELECT * FROM special_events_index
            WHERE province_id = ? AND event_category IN ({placeholders})
            ORDER BY severity DESC, month DESC
            LIMIT ?
        """, [province_id] + categories + [limit])
        rows = cursor.fetchall()
        conn.close()

        if rows:
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        return []
