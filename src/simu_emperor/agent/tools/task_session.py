"""
Task session tools for V5 Agent

Task sessions allow agents to create sub-tasks with their own context.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from simu_emperor.mq.event import Event
from simu_emperor.mq.dealer import MQDealer
from simu_emperor.persistence.repositories.task_session import TaskSessionRepository


logger = logging.getLogger(__name__)


MAX_TASK_DEPTH = 3
MAX_TASK_SESSION_MEMBERS = 2


class TaskSessionTools:
    """Tools for managing task sessions."""

    def __init__(
        self,
        agent_id: str,
        dealer: MQDealer,
        task_session_repo: TaskSessionRepository,
    ):
        self.agent_id = agent_id
        self.dealer = dealer
        self.task_session_repo = task_session_repo

    async def create_task_session(self, args: dict, event: Event) -> str:
        timeout_seconds = args.get("timeout_seconds", 300)
        description = args.get("description", "")
        goal = args.get("goal", "")
        constraints = args.get("constraints", "")

        current_session = await self.task_session_repo.get(event.session_id)
        if current_session:
            depth = self._calculate_depth(event.session_id)
            if depth >= MAX_TASK_DEPTH:
                return f"❌ 任务嵌套深度超限 (最大: {MAX_TASK_DEPTH})"

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        suffix = uuid.uuid4().hex[:8]
        task_session_id = f"task:{self.agent_id}:{timestamp}:{suffix}"

        try:
            await self.task_session_repo.create(
                task_id=task_session_id,
                session_id=event.session_id,
                creator_id=f"agent:{self.agent_id}",
                task_type=description,
                timeout_seconds=timeout_seconds,
            )

            task_event = Event(
                event_id="",
                event_type="TASK_CREATED",
                src=f"agent:{self.agent_id}",
                dst=[f"agent:{self.agent_id}"],
                session_id=task_session_id,
                payload={
                    "task_session_id": task_session_id,
                    "parent_session_id": event.session_id,
                    "description": description,
                    "goal": goal,
                    "constraints": constraints,
                },
                timestamp="",
            )
            await self.dealer.send_event(task_event)

            logger.info(f"Agent {self.agent_id} created task session {task_session_id}")

            return json.dumps(
                {
                    "success": True,
                    "task_session_id": task_session_id,
                    "status": "WAITING_REPLY",
                    "message": f"Task session created: {task_session_id}. Agent will pause.",
                },
                ensure_ascii=False,
            )

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error creating task session: {e}")
            return f"❌ 任务创建失败：{str(e)}"

    async def finish_task_session(self, args: dict, event: Event) -> str:
        task_session_id = args.get("task_session_id")
        result = args.get("result", "")

        if not task_session_id:
            return "❌ 请提供 task_session_id 参数"

        try:
            session = await self.task_session_repo.get(task_session_id)
            if not session:
                return f"❌ 未找到任务会话 {task_session_id}"

            if session.get("status") in ("completed", "failed"):
                return f"❌ 任务已结束，状态：{session.get('status')}"

            if session.get("creator_id") != f"agent:{self.agent_id}":
                return "❌ 只有任务创建者可以结束任务"

            await self.task_session_repo.update_status(
                task_session_id, "completed", {"result": result}
            )

            task_event = Event(
                event_id="",
                event_type="TASK_FINISHED",
                src=f"agent:{self.agent_id}",
                dst=[session.get("creator_id", "player")],
                session_id=session.get("session_id", ""),
                payload={
                    "task_session_id": task_session_id,
                    "result": result,
                },
                timestamp="",
            )
            await self.dealer.send_event(task_event)

            logger.info(f"Agent {self.agent_id} finished task session {task_session_id}")

            return f"✅ 任务已完成：{task_session_id}"

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error finishing task session: {e}")
            return f"❌ 任务结束失败：{str(e)}"

    async def fail_task_session(self, args: dict, event: Event) -> str:
        task_session_id = args.get("task_session_id")
        error = args.get("error", "Unknown error")

        if not task_session_id:
            return "❌ 请提供 task_session_id 参数"

        try:
            session = await self.task_session_repo.get(task_session_id)
            if not session:
                return f"❌ 未找到任务会话 {task_session_id}"

            await self.task_session_repo.update_status(task_session_id, "failed", {"error": error})

            task_event = Event(
                event_id="",
                event_type="TASK_FAILED",
                src=f"agent:{self.agent_id}",
                dst=[session.get("creator_id", "player")],
                session_id=session.get("session_id", ""),
                payload={
                    "task_session_id": task_session_id,
                    "error": error,
                },
                timestamp="",
            )
            await self.dealer.send_event(task_event)

            logger.info(f"Agent {self.agent_id} failed task session {task_session_id}")

            return f"✅ 任务已标记为失败：{task_session_id}"

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error failing task session: {e}")
            return f"❌ 任务失败操作失败：{str(e)}"

    def _calculate_depth(self, session_id: str) -> int:
        depth = 0
        current = session_id
        while current and current.startswith("task:"):
            depth += 1
            parts = current.split(":")
            if len(parts) < 4:
                break
            current = None
        return depth
