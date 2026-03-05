"""
事件日志记录

提供事件日志记录接口和实现。
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from simu_emperor.event_bus.event import Event


class EventLogger(ABC):
    """
    事件日志记录器接口

    定义事件日志记录的抽象接口。
    """

    @abstractmethod
    def log(self, event: Event) -> None:
        """
        记录事件

        Args:
            event: 事件对象
        """
        pass

    @abstractmethod
    async def log_async(self, event: Event) -> None:
        """
        异步记录事件

        Args:
            event: 事件对象
        """
        pass


class FileEventLogger(EventLogger):
    """
    文件事件日志记录器

    将事件记录到 JSONL 文件（每天一个文件）。
    JSONL 格式：每行一个 JSON 对象。

    Attributes:
        log_dir: 日志目录
        current_date: 当前日期（用于日志轮转）
        current_file: 当前日志文件路径
    """

    def __init__(self, log_dir: str | Path):
        """
        初始化文件事件日志记录器

        Args:
            log_dir: 日志目录路径
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.current_date: str | None = None
        self.current_file: Path | None = None

        # 初始化当前文件
        self._rotate_if_needed()

    def log(self, event: Event) -> None:
        """
        记录事件（同步）

        Args:
            event: 事件对象
        """
        self._rotate_if_needed()

        if self.current_file is None:
            raise RuntimeError("Log file not initialized")

        # 写入事件（追加模式）
        with open(self.current_file, "a", encoding="utf-8") as f:
            f.write(event.to_json() + "\n")

    async def log_async(self, event: Event) -> None:
        """
        记录事件（异步）

        Args:
            event: 事件对象
        """
        self._rotate_if_needed()

        if self.current_file is None:
            raise RuntimeError("Log file not initialized")

        # 使用 asyncio 的文件 I/O
        import aiofiles

        async with aiofiles.open(self.current_file, mode="a", encoding="utf-8") as f:
            await f.write(event.to_json() + "\n")

    def _rotate_if_needed(self) -> None:
        """
        检查是否需要日志轮转

        如果日期变更，创建新的日志文件。
        """
        today = datetime.now(timezone.utc).strftime("%Y%m%d")

        if self.current_date != today:
            self.current_date = today
            self.current_file = self.log_dir / f"events_{today}.jsonl"

    def query_events(
        self,
        date: str | None = None,
        event_type: str | None = None,
        src: str | None = None,
        dst: str | None = None,
        limit: int | None = None,
    ) -> list[Event]:
        """
        查询事件日志

        Args:
            date: 日期（YYYYMMDD 格式），默认为今天
            event_type: 事件类型过滤
            src: 事件源过滤
            dst: 目标过滤
            limit: 返回结果数量限制

        Returns:
            事件列表
        """
        # 确定查询的文件
        if date:
            log_file = self.log_dir / f"events_{date}.jsonl"
        else:
            self._rotate_if_needed()
            log_file = self.current_file

        if log_file is None or not log_file.exists():
            return []

        # 读取并解析事件
        events: list[Event] = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    event = Event.from_json(line)

                    # 应用过滤条件
                    if event_type and event.type != event_type:
                        continue
                    if src and event.src != src:
                        continue
                    if dst and dst not in event.dst:
                        continue

                    events.append(event)

                    # 检查限制
                    if limit and len(events) >= limit:
                        break

                except json.JSONDecodeError:
                    continue

        return events

    def get_log_files(self) -> list[Path]:
        """
        获取所有日志文件

        Returns:
            日志文件路径列表（按修改时间排序）
        """
        pattern = "events_*.jsonl"
        files = sorted(self.log_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        return files


class DatabaseEventLogger(EventLogger):
    """
    数据库事件日志记录器

    将事件记录到数据库 events 表中，支持 Session 隔离和事件链追踪。
    """

    def __init__(self, db_connection: Any):
        """
        初始化数据库事件日志记录器

        Args:
            db_connection: aiosqlite.Connection 对象
        """
        self._db = db_connection

    def log(self, event: Event) -> None:
        """
        记录事件（同步）

        Args:
            event: 事件对象
        """
        import asyncio

        # 在同步上下文中运行异步方法
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，使用 create_task
                asyncio.ensure_future(self.log_async(event))
            else:
                # 如果事件循环未运行，直接运行
                loop.run_until_complete(self.log_async(event))
        except RuntimeError:
            # 没有事件循环，创建一个新的
            asyncio.run(self.log_async(event))

    async def log_async(self, event: Event) -> None:
        """
        记录事件（异步）

        Args:
            event: 事件对象
        """
        import json

        await self._db.execute(
            """INSERT INTO events
               (event_id, session_id, root_event_id, parent_event_id,
                src, dst, type, payload, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.event_id,
                event.session_id,
                event.root_event_id,
                event.parent_event_id,
                event.src,
                json.dumps(event.dst),
                event.type,
                json.dumps(event.payload),
                event.timestamp,
            ),
        )
        await self._db.commit()

    async def get_agent_visible_events(
        self,
        session_id: str,
        agent_id: str,
        limit: int = 20,
    ) -> list[Event]:
        """
        查询 Agent 在 Session 内可见的最近事件

        Args:
            session_id: 会话标识符
            agent_id: Agent 标识符（如 "revenue_minister"）
            limit: 返回事件数量限制

        Returns:
            事件列表（按时间倒序）
        """
        import json

        # Agent 可见的事件包括：
        # 1. dst 是 "agent:{agent_id}"
        # 2. dst 是 "agent:*"
        # 3. dst 是 "*"
        # 4. src 是 "agent:{agent_id}"（Agent 发送的事件）
        cursor = await self._db.execute(
            """SELECT event_id, session_id, root_event_id, parent_event_id,
                      src, dst, type, payload, timestamp
               FROM events
               WHERE session_id = ?
                 AND (
                     dst LIKE ? OR dst LIKE ? OR dst LIKE ? OR src = ?
                 )
               ORDER BY timestamp DESC
               LIMIT ?""",
            (
                session_id,
                f"%agent:{agent_id}%",
                "%agent:*%",
                "%*%",
                f"agent:{agent_id}",
                limit,
            ),
        )

        rows = await cursor.fetchall()
        events = []

        for row in rows:
            events.append(
                Event(
                    event_id=row[0],
                    session_id=row[1],
                    root_event_id=row[2],
                    parent_event_id=row[3],
                    src=row[4],
                    dst=json.loads(row[5]),
                    type=row[6],
                    payload=json.loads(row[7]),
                    timestamp=row[8],
                )
            )

        return events
