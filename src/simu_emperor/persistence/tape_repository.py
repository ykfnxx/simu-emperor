"""
TapeRepository - V4.2 磁带式事件存储

提供 tape_events 和 failed_embeddings 表的 CRUD 操作。
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from simu_emperor.event_bus.event import Event

logger = logging.getLogger(__name__)


class TapeRepository:
    """
    磁带式事件存储仓库

    管理两个表：
    - tape_events: 事件记录（增强查询）
    - failed_embeddings: Embedding 失败重试记录
    """

    def __init__(self, db_path: str = "game.db"):
        """
        初始化仓库

        Args:
            db_path: 数据库文件路径
        """
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """连接到数据库并确保表存在。"""
        self._conn = await aiosqlite.connect(self._db_path)
        logger.info(f"TapeRepository initialized with db: {self._db_path}")

    async def close(self) -> None:
        """关闭数据库连接。"""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            logger.info("TapeRepository connection closed")

    def _ensure_connected(self) -> aiosqlite.Connection:
        """确保数据库已连接。"""
        if self._conn is None:
            raise RuntimeError("TapeRepository not initialized. Call initialize() first.")
        return self._conn

    async def insert_event(self, event: Event, agent_id: str, tick: int | None = None) -> None:
        """
        插入事件到 tape_events 表

        Args:
            event: 事件对象
            agent_id: Agent 标识符
            tick: 游戏时间（可选）
        """
        conn = self._ensure_connected()

        await conn.execute(
            """
            INSERT OR REPLACE INTO tape_events (
                event_id, session_id, agent_id, src, dst, type, payload,
                timestamp, tick, parent_event_id, root_event_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.session_id,
                agent_id,
                event.src,
                json.dumps(event.dst),
                event.type,
                json.dumps(event.payload),
                event.timestamp,
                tick,
                event.parent_event_id,
                event.root_event_id,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await conn.commit()
        logger.debug(f"Inserted event {event.event_id} for agent {agent_id}")

    async def query_events(
        self,
        session_id: str | None = None,
        agent_id: str | None = None,
        event_type: str | None = None,
        tick: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        灵活查询事件

        Args:
            session_id: 会话 ID 过滤
            agent_id: Agent ID 过滤
            event_type: 事件类型过滤
            tick: 时间点过滤
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            匹配的事件列表（字典格式）
        """
        conn = self._ensure_connected()

        conditions = []
        params: list[Any] = []

        if session_id is not None:
            conditions.append("session_id = ?")
            params.append(session_id)
        if agent_id is not None:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if event_type is not None:
            conditions.append("type = ?")
            params.append(event_type)
        if tick is not None:
            conditions.append("tick = ?")
            params.append(tick)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        query = f"""
            SELECT * FROM tape_events
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """

        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()

        # 获取列名
        columns = [description[0] for description in cursor.description]

        results = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            # 解析 JSON 字段
            if row_dict.get("dst"):
                row_dict["dst"] = json.loads(row_dict["dst"])
            if row_dict.get("payload"):
                row_dict["payload"] = json.loads(row_dict["payload"])
            results.append(row_dict)

        return results

    async def count_events(self, session_id: str) -> int:
        """
        统计会话的事件数量

        Args:
            session_id: 会话 ID

        Returns:
            事件数量
        """
        conn = self._ensure_connected()

        cursor = await conn.execute(
            "SELECT COUNT(*) FROM tape_events WHERE session_id = ?",
            (session_id,),
        )
        result = await cursor.fetchone()
        return result[0] if result else 0

    async def record_failed_embedding(
        self, segment_id: str, summary: str, metadata: dict[str, Any], error: str
    ) -> None:
        """
        记录失败的 Embedding

        Args:
            segment_id: 段落 ID
            summary: 摘要内容
            metadata: 元数据字典
            error: 错误信息
        """
        conn = self._ensure_connected()

        await conn.execute(
            """
            INSERT OR REPLACE INTO failed_embeddings (
                segment_id, summary, metadata, error, retry_count, created_at, last_retry_at
            ) VALUES (?, ?, ?, ?, 0, ?, NULL)
            """,
            (
                segment_id,
                summary,
                json.dumps(metadata),
                error,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await conn.commit()
        logger.info(f"Recorded failed embedding for segment {segment_id}")

    async def get_failed_embeddings(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        获取待重试的失败 Embedding 记录

        只返回 retry_count < 3 的记录。

        Args:
            limit: 返回数量限制

        Returns:
            失败记录列表
        """
        conn = self._ensure_connected()

        cursor = await conn.execute(
            """
            SELECT * FROM failed_embeddings
            WHERE retry_count < 3
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()

        columns = [description[0] for description in cursor.description]

        results = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            # 解析 JSON 字段
            if row_dict.get("metadata"):
                row_dict["metadata"] = json.loads(row_dict["metadata"])
            results.append(row_dict)

        return results

    async def mark_embedding_retried(self, segment_id: str) -> None:
        """
        标记 Embedding 已重试（增加重试计数）

        Args:
            segment_id: 段落 ID
        """
        conn = self._ensure_connected()

        await conn.execute(
            """
            UPDATE failed_embeddings
            SET retry_count = retry_count + 1, last_retry_at = ?
            WHERE segment_id = ?
            """,
            (datetime.now(timezone.utc).isoformat(), segment_id),
        )
        await conn.commit()
        logger.debug(f"Marked embedding {segment_id} as retried")

    async def remove_failed_embedding(self, segment_id: str) -> None:
        """
        移除失败的 Embedding 记录

        Args:
            segment_id: 段落 ID
        """
        conn = self._ensure_connected()

        await conn.execute(
            "DELETE FROM failed_embeddings WHERE segment_id = ?",
            (segment_id,),
        )
        await conn.commit()
        logger.info(f"Removed failed embedding record for segment {segment_id}")
