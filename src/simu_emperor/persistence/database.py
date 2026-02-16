"""SQLite 数据库连接与 schema 初始化。"""

import aiosqlite
from aiosqlite import Connection

_db_connection: Connection | None = None
_db_path: str = "game.db"


async def init_database(db_path: str = "game.db") -> Connection:
    """初始化数据库连接并创建 schema。

    Args:
        db_path: 数据库文件路径，默认为 "game.db"

    Returns:
        数据库连接对象
    """
    global _db_connection, _db_path

    _db_path = db_path
    _db_connection = await aiosqlite.connect(db_path)

    await _create_schema(_db_connection)
    return _db_connection


async def _create_schema(conn: Connection) -> None:
    """创建数据库 schema（5 张表 + 索引）。"""
    await conn.executescript("""
        -- 游戏存档
        CREATE TABLE IF NOT EXISTS game_saves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            turn INTEGER NOT NULL,
            state_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(game_id, turn)
        );

        -- 事件日志
        CREATE TABLE IF NOT EXISTS event_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            turn INTEGER NOT NULL,
            event_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_json TEXT NOT NULL,
            action TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Agent 报告
        CREATE TABLE IF NOT EXISTS agent_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            turn INTEGER NOT NULL,
            agent_id TEXT NOT NULL,
            report_markdown TEXT NOT NULL,
            real_data_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 对话历史
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 玩家命令
        CREATE TABLE IF NOT EXISTS player_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            turn INTEGER NOT NULL,
            command_type TEXT NOT NULL,
            target_province_id TEXT,
            parameters_json TEXT,
            result_event_json TEXT,
            fidelity REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 索引
        CREATE INDEX IF NOT EXISTS idx_game_saves_game_id ON game_saves(game_id);
        CREATE INDEX IF NOT EXISTS idx_event_log_game_turn ON event_log(game_id, turn);
        CREATE INDEX IF NOT EXISTS idx_agent_reports_game_turn ON agent_reports(game_id, turn);
        CREATE INDEX IF NOT EXISTS idx_chat_history_agent ON chat_history(game_id, agent_id);
    """)
    await conn.commit()


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
