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
    数据库事件日志记录器（可选实现）

    将事件记录到数据库表中。
    注意：此类为占位符，实际实现需要根据 persistence 模块的完成情况。
    """

    def __init__(self, repository: Any):
        """
        初始化数据库事件日志记录器

        Args:
            repository: 数据库仓储对象
        """
        self.repository = repository

    def log(self, event: Event) -> None:
        """
        记录事件（同步）

        Args:
            event: 事件对象
        """
        # TODO: 实现数据库日志记录
        # 需要等待 persistence 模块完成
        raise NotImplementedError("DatabaseEventLogger not implemented yet")

    async def log_async(self, event: Event) -> None:
        """
        记录事件（异步）

        Args:
            event: 事件对象
        """
        # TODO: 实现异步数据库日志记录
        raise NotImplementedError("DatabaseEventLogger not implemented yet")
