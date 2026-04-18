"""SQLite database initialization and connection management.

All Server-side persistent data lives in a single SQLite file with WAL mode.
"""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

_SCHEMA = """
-- Sessions
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    parent_id   TEXT,
    status      TEXT NOT NULL DEFAULT 'active',
    created_by  TEXT NOT NULL DEFAULT '',
    agent_ids   TEXT NOT NULL DEFAULT '[]',
    metadata    TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- Routed messages (for frontend history)
CREATE TABLE IF NOT EXISTS messages (
    message_id    TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL,
    src           TEXT NOT NULL,
    dst           TEXT NOT NULL,
    content       TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    timestamp     TEXT NOT NULL,
    origin_event_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages (session_id, timestamp);

-- Agent registration
CREATE TABLE IF NOT EXISTS agents (
    agent_id        TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'registered',
    process_pid     INTEGER,
    config_path     TEXT NOT NULL DEFAULT '',
    callback_url    TEXT,
    registered_at   TEXT NOT NULL,
    last_heartbeat  TEXT,
    capabilities    TEXT NOT NULL DEFAULT '[]'
);

-- Invocations
CREATE TABLE IF NOT EXISTS invocations (
    invocation_id    TEXT PRIMARY KEY,
    agent_id         TEXT NOT NULL,
    session_id       TEXT NOT NULL,
    trigger_event_id TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'queued',
    callback_token   TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    started_at       TEXT,
    completed_at     TEXT,
    error            TEXT
);
CREATE INDEX IF NOT EXISTS idx_invocations_agent ON invocations (agent_id, status);

-- Game state (nation-level)
CREATE TABLE IF NOT EXISTS game_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Incidents
CREATE TABLE IF NOT EXISTS incidents (
    incident_id     TEXT PRIMARY KEY,
    data            TEXT NOT NULL,
    remaining_ticks INTEGER NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class Database:
    """Thin async wrapper around a SQLite connection."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self._db_path))
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()
        logger.info("Database initialized at %s", self._db_path)

    @property
    def conn(self) -> aiosqlite.Connection:
        assert self._conn is not None, "Database not initialized"
        return self._conn

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
