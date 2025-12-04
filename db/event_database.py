"""
Event system database extension

Adds event-related database operations for the Database class
"""

import sqlite3
from typing import Dict, Any


def save_event(self, event_data: Dict[str, Any]):
    """Save or update event

    Args:
        event_data: Event data dictionary
    """
    conn = self.get_connection()
    cursor = conn.cursor()

    # Create events table (if it doesn't exist)
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

    # Ensure event_type and visibility are strings (handle enum)
    event_type = event_data.get('event_type', 'province')
    if hasattr(event_type, 'value'):
        event_type = event_type.value

    visibility = event_data.get('visibility', 'provincial')
    if hasattr(visibility, 'value'):
        visibility = visibility.value

    # Insert or replace event
    cursor.execute("""
        INSERT OR REPLACE INTO events (
            event_id, name, description, event_type, province_id,
            instant_effects, continuous_effects, start_month, end_month,
            is_active, visibility, is_hidden_by_governor, hidden_reason,
            severity, public_perception, metadata, is_agent_generated,
            is_fabricated, fabrication_reason, generated_by_agent_id,
            narrative_consistency_score, verification_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        event_data['event_id'],
        event_data['name'],
        event_data.get('description', ''),
        event_type,
        event_data.get('province_id'),
        event_data.get('instant_effects', '[]'),
        event_data.get('continuous_effects', '[]'),
        event_data['start_month'],
        event_data.get('end_month'),
        event_data.get('is_active', True),
        visibility,
        event_data.get('is_hidden_by_governor', False),
        event_data.get('hidden_reason'),
        event_data.get('severity', 0.5),
        event_data.get('public_perception'),
        event_data.get('metadata', '{}'),
        event_data.get('is_agent_generated', False),
        event_data.get('is_fabricated', False),
        event_data.get('fabrication_reason'),
        event_data.get('generated_by_agent_id'),
        event_data.get('narrative_consistency_score'),
        event_data.get('verification_status')
    ))

    conn.commit()
    conn.close()


def get_active_events(self, current_month: int):
    """Get active events

    Args:
        current_month: Current month

    Returns:
        List of events
    """
    conn = self.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM events
        WHERE is_active = 1 AND (end_month IS NULL OR end_month >= ?)
    """, (current_month,))

    rows = cursor.fetchall()

    # Get column names
    cursor.execute("SELECT * FROM events LIMIT 0")
    columns = [description[0] for description in cursor.description]

    events = []
    for row in rows:
        event = dict(zip(columns, row))

        # Convert boolean values
        if 'is_active' in event:
            event['is_active'] = bool(event['is_active'])
        if 'is_hidden_by_governor' in event:
            event['is_hidden_by_governor'] = bool(event['is_hidden_by_governor'])
        if 'is_agent_generated' in event:
            event['is_agent_generated'] = bool(event['is_agent_generated'])
        if 'is_fabricated' in event:
            event['is_fabricated'] = bool(event['is_fabricated'])

        events.append(event)

    conn.close()
    return events


def update_event(self, event_id: str, updates: Dict[str, Any]):
    """Update event

    Args:
        event_id: Event ID
        updates: Update dictionary
    """
    conn = self.get_connection()
    cursor = conn.cursor()

    # Build update SQL
    set_clauses = []
    values = []

    for key, value in updates.items():
        set_clauses.append(f"{key} = ?")
        values.append(value)

    values.append(event_id)

    sql = f"""
        UPDATE events SET {', '.join(set_clauses)}
        WHERE event_id = ?
    """

    cursor.execute(sql, values)
    conn.commit()
    conn.close()
