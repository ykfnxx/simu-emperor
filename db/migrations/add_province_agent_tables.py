"""
Database migration script for Province Agent system

This script adds the following tables:
1. province_monthly_summaries - Monthly detailed summaries
2. province_quarterly_summaries - Quarterly aggregated summaries
3. province_annual_summaries - Annual summaries
4. player_instructions - Player instruction tracking
5. province_behaviors - Agent behavior records
6. special_events_index - Special event indexing
"""

import sqlite3
import os
from typing import Optional


def migrate(db_path: str = "game.db") -> bool:
    """
    Run migration to add Province Agent tables

    Args:
        db_path: Path to SQLite database file

    Returns:
        True if migration succeeded, False otherwise
    """
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Create province_monthly_summaries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS province_monthly_summaries (
                summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
                province_id INTEGER NOT NULL,
                month INTEGER NOT NULL,
                year INTEGER NOT NULL,
                population INTEGER,
                development_level REAL,
                loyalty REAL,
                stability REAL,
                actual_income REAL,
                actual_expenditure REAL,
                reported_income REAL,
                reported_expenditure REAL,
                income_trend TEXT,
                expenditure_trend TEXT,
                loyalty_trend TEXT,
                major_events TEXT,
                event_count INTEGER DEFAULT 0,
                agent_decision TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (province_id) REFERENCES provinces(province_id),
                UNIQUE(province_id, month, year)
            )
        """)

        # Create province_quarterly_summaries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS province_quarterly_summaries (
                summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
                province_id INTEGER NOT NULL,
                quarter INTEGER NOT NULL,
                year INTEGER NOT NULL,
                avg_income REAL,
                median_income REAL,
                avg_expenditure REAL,
                median_expenditure REAL,
                total_surplus REAL,
                income_trend TEXT,
                expenditure_trend TEXT,
                loyalty_change REAL,
                stability_change REAL,
                major_events TEXT,
                special_event_types TEXT,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (province_id) REFERENCES provinces(province_id),
                UNIQUE(province_id, quarter, year)
            )
        """)

        # Create province_annual_summaries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS province_annual_summaries (
                summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
                province_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                total_income REAL,
                total_expenditure REAL,
                avg_monthly_income REAL,
                avg_monthly_expenditure REAL,
                total_surplus REAL,
                population_change INTEGER,
                development_change REAL,
                loyalty_start REAL,
                loyalty_end REAL,
                loyalty_change REAL,
                major_events TEXT,
                disaster_count INTEGER DEFAULT 0,
                rebellion_count INTEGER DEFAULT 0,
                performance_rating TEXT,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (province_id) REFERENCES provinces(province_id),
                UNIQUE(province_id, year)
            )
        """)

        # Create player_instructions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_instructions (
                instruction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                province_id INTEGER NOT NULL,
                month INTEGER NOT NULL,
                year INTEGER NOT NULL,
                instruction_type TEXT NOT NULL,
                template_name TEXT NOT NULL,
                parameters TEXT,
                status TEXT DEFAULT 'pending',
                result_summary TEXT,
                agent_reasoning TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                executed_at TIMESTAMP,
                FOREIGN KEY (province_id) REFERENCES provinces(province_id)
            )
        """)

        # Create province_behaviors table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS province_behaviors (
                behavior_id INTEGER PRIMARY KEY AUTOINCREMENT,
                province_id INTEGER NOT NULL,
                month INTEGER NOT NULL,
                year INTEGER NOT NULL,
                behavior_type TEXT NOT NULL,
                behavior_name TEXT NOT NULL,
                parameters TEXT,
                effects TEXT,
                in_response_to_instruction INTEGER,
                reasoning TEXT,
                is_valid BOOLEAN DEFAULT 1,
                validation_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (province_id) REFERENCES provinces(province_id),
                FOREIGN KEY (in_response_to_instruction) REFERENCES player_instructions(instruction_id)
            )
        """)

        # Create special_events_index table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS special_events_index (
                index_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                province_id INTEGER NOT NULL,
                event_category TEXT NOT NULL,
                event_name TEXT NOT NULL,
                severity REAL,
                month INTEGER NOT NULL,
                year INTEGER NOT NULL,
                impact_description TEXT,
                is_resolved BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (province_id) REFERENCES provinces(province_id),
                UNIQUE(event_id)
            )
        """)

        # Add columns to monthly_reports table
        try:
            cursor.execute("""
                ALTER TABLE monthly_reports ADD COLUMN agent_behavior_id INTEGER
            """)
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute("""
                ALTER TABLE monthly_reports ADD COLUMN player_instruction_id INTEGER
            """)
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute("""
                ALTER TABLE monthly_reports ADD COLUMN decision_summary TEXT
            """)
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Add year column to monthly_reports if it doesn't exist
        try:
            cursor.execute("""
                ALTER TABLE monthly_reports ADD COLUMN year INTEGER DEFAULT 1
            """)
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Add province state columns to monthly_reports for historical tracking
        try:
            cursor.execute("""
                ALTER TABLE monthly_reports ADD COLUMN population INTEGER DEFAULT 0
            """)
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("""
                ALTER TABLE monthly_reports ADD COLUMN development_level REAL DEFAULT 5.0
            """)
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("""
                ALTER TABLE monthly_reports ADD COLUMN loyalty REAL DEFAULT 50.0
            """)
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("""
                ALTER TABLE monthly_reports ADD COLUMN stability REAL DEFAULT 50.0
            """)
        except sqlite3.OperationalError:
            pass

        # Create indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_monthly_summaries_province
            ON province_monthly_summaries(province_id, year, month)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_quarterly_summaries_province
            ON province_quarterly_summaries(province_id, year, quarter)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_annual_summaries_province
            ON province_annual_summaries(province_id, year)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_instructions_province
            ON player_instructions(province_id, year, month)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_behaviors_province
            ON province_behaviors(province_id, year, month)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_special_events_province
            ON special_events_index(province_id, event_category, severity)
        """)

        conn.commit()
        print("✓ Province Agent tables created successfully")
        return True

    except Exception as e:
        conn.rollback()
        print(f"✗ Migration failed: {e}")
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    # Run migration
    db_path = "game.db"
    if migrate(db_path):
        print("\nMigration completed successfully!")
        print(f"Database: {db_path}")
    else:
        print("\nMigration failed!")
