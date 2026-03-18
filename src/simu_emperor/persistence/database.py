"""
SQLite 数据库连接与 schema 初始化（V2）

V2 简化设计：
- 移除阶段相关的表
- 移除 Agent 报告、聊天历史、玩家命令（由文件系统替代）
- 保留游戏状态、回合指标、Agent 状态
"""

import aiosqlite
from aiosqlite import Connection
import logging

logger = logging.getLogger(__name__)

_db_connection: Connection | None = None
_db_path: str = "game.db"


async def init_database(db_path: str = "game.db") -> Connection:
    """初始化数据库连接并创建 V2 schema。

    Args:
        db_path: 数据库文件路径，默认为 "game.db"

    Returns:
        数据库连接对象
    """
    global _db_connection, _db_path

    _db_path = db_path
    _db_connection = await aiosqlite.connect(db_path)

    await _create_schema(_db_connection)
    logger.info(f"Database initialized at {db_path}")
    return _db_connection


async def _create_schema(conn: Connection) -> None:
    """创建 V2 数据库 schema（4 张表 + 索引）。"""
    await conn.executescript("""
        -- 游戏状态
        CREATE TABLE IF NOT EXISTS game_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            game_id TEXT NOT NULL DEFAULT 'default',
            turn INTEGER NOT NULL DEFAULT 0,
            state_json TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 回合指标
        CREATE TABLE IF NOT EXISTS turn_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL DEFAULT 'default',
            turn INTEGER NOT NULL,
            metrics_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(game_id, turn)
        );

        -- Agent 状态
        CREATE TABLE IF NOT EXISTS agent_state (
            agent_id TEXT PRIMARY KEY,
            is_active INTEGER NOT NULL DEFAULT 0,
            soul_markdown TEXT,
            data_scope_yaml TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 事件日志（用于 Session 隔离和事件链追踪）
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            root_event_id TEXT NOT NULL,
            parent_event_id TEXT,
            src TEXT NOT NULL,
            dst TEXT NOT NULL,
            type TEXT NOT NULL,
            payload TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Incident 持久化（V4 Incident/Effect 系统）
        CREATE TABLE IF NOT EXISTS incidents (
            incident_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            source TEXT NOT NULL,
            created_tick INTEGER NOT NULL,
            expired_tick INTEGER,
            remaining_ticks INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            effects_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expired_at TEXT
        );

        -- 插入默认游戏状态
        INSERT OR IGNORE INTO game_state (id, game_id, turn, state_json)
        VALUES (1, 'default', 0, '{}');

        -- 索引
        CREATE INDEX IF NOT EXISTS idx_turn_metrics_game_turn ON turn_metrics(game_id, turn);
        CREATE INDEX IF NOT EXISTS idx_agent_state_active ON agent_state(is_active);

        -- 事件表索引（用于快速查询）
        CREATE INDEX IF NOT EXISTS idx_events_session_time ON events(session_id, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_events_root_event ON events(root_event_id, timestamp);
        CREATE INDEX IF NOT EXISTS idx_events_parent ON events(parent_event_id);
        CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
        CREATE INDEX IF NOT EXISTS idx_events_src_dst ON events(src, dst);
        CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
    """)
    await conn.commit()
    logger.info("Database schema created")


async def get_connection() -> Connection:
    """获取当前数据库连接。

    Returns:
        数据库连接对象

    Raises:
        RuntimeError: 如果数据库未初始化
    """
    if _db_connection is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _db_connection


async def close_database() -> None:
    """关闭数据库连接。"""
    global _db_connection
    if _db_connection is not None:
        await _db_connection.close()
        _db_connection = None
        logger.info("Database connection closed")
