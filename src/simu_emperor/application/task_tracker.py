"""异步任务追踪器

用于追踪后台长时间运行的任务（如 LLM 生成 agent 配置）。
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Awaitable
from uuid import uuid4

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态"""

    PENDING = "pending"  # 等待执行
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 完成
    FAILED = "failed"  # 失败


@dataclass
class Task:
    """后台任务"""

    task_id: str
    name: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result: dict[str, Any] | None = None
    progress: int = 0  # 0-100

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于 API 响应）"""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "result": self.result,
            "progress": self.progress,
        }


class TaskTracker:
    """任务追踪器

    管理后台异步任务的生命周期。
    """

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    def create_task(self, name: str) -> Task:
        """创建新任务

        Args:
            name: 任务名称

        Returns:
            创建的任务对象
        """
        task_id = str(uuid4())
        task = Task(task_id=task_id, name=name)
        self._tasks[task_id] = task
        logger.info(f"Task created: {task_id} - {name}")
        return task

    async def run_task(
        self,
        task_id: str,
        coro: Callable[[], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        """在后台运行任务

        Args:
            task_id: 任务 ID
            coro: 要执行的异步函数

        Returns:
            任务结果
        """
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        logger.info(f"Task started: {task_id}")

        try:
            result = await coro()
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            task.progress = 100
            logger.info(f"Task completed: {task_id}")
            return result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error = str(e)
            logger.error(f"Task failed: {task_id} - {e}")
            raise

    def get_task(self, task_id: str) -> Task | None:
        """获取任务

        Args:
            task_id: 任务 ID

        Returns:
            任务对象，不存在则返回 None
        """
        return self._tasks.get(task_id)

    def update_progress(self, task_id: str, progress: int) -> None:
        """更新任务进度

        Args:
            task_id: 任务 ID
            progress: 进度百分比 (0-100)
        """
        task = self._tasks.get(task_id)
        if task:
            task.progress = max(0, min(100, progress))

    def cleanup_old_tasks(self, max_age_seconds: int = 3600) -> None:
        """清理旧任务

        Args:
            max_age_seconds: 任务最大保留时间（秒）
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(seconds=max_age_seconds)
        to_remove = [
            task_id
            for task_id, task in self._tasks.items()
            if task.completed_at and task.completed_at < cutoff
        ]
        for task_id in to_remove:
            del self._tasks[task_id]
            logger.debug(f"Cleaned up old task: {task_id}")

    def get_all_tasks(self) -> list[Task]:
        """获取所有任务（用于调试）"""
        return list(self._tasks.values())


# 全局单例
_task_tracker: TaskTracker | None = None


def get_task_tracker() -> TaskTracker:
    """获取全局任务追踪器实例"""
    global _task_tracker
    if _task_tracker is None:
        _task_tracker = TaskTracker()
    return _task_tracker
