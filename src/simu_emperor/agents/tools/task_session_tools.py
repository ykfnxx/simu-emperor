"""Task session tools for V4 Task Session architecture."""

import uuid
from datetime import datetime, timezone

from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.session.constants import MAX_TASK_DEPTH


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskSessionTools:
    """Tools for managing task sessions."""

    def __init__(
        self,
        agent_id: str,
        session_manager,
        event_bus,
    ):
        self.agent_id = agent_id
        self.session_manager = session_manager
        self.event_bus = event_bus

    async def create_task_session(
        self,
        timeout_seconds: int = 300,
        description: str = "",
        current_session_id: str = None,
    ) -> dict:
        current_session = await self.session_manager.get_session(current_session_id)
        if current_session is None:
            raise ValueError(f"Current session not found: {current_session_id}")

        depth = self.session_manager._calculate_depth(current_session_id)
        if depth >= MAX_TASK_DEPTH:
            raise ValueError(f"Task nesting depth exceeded (max: {MAX_TASK_DEPTH})")

        timestamp = utcnow().strftime("%Y%m%d%H%M%S")
        suffix = uuid.uuid4().hex[:8]
        task_session_id = f"task:{self.agent_id}:{timestamp}:{suffix}"

        session = await self.session_manager.create_session(
            session_id=task_session_id,
            parent_id=current_session_id,
            created_by=f"agent:{self.agent_id}",
            timeout_seconds=timeout_seconds,
        )

        task_created_event = Event(
            src=f"agent:{self.agent_id}",
            dst=[f"agent:{self.agent_id}"],
            type=EventType.TASK_CREATED,
            payload={
                "task_session_id": task_session_id,
                "parent_session_id": current_session_id,
                "description": description,
            },
            session_id=task_session_id,
        )
        await self.event_bus.send_event(task_created_event)

        await self.session_manager.update_session(
            task_session_id,
            root_event_id=task_created_event.event_id,
        )

        parent_session = await self.session_manager.get_session(current_session_id)
        if parent_session:
            new_waiting_list = parent_session.waiting_for_tasks + [task_session_id]
            await self.session_manager.update_session(
                current_session_id,
                status="WAITING_REPLY",
                waiting_for_tasks=new_waiting_list,
            )

        return {
            "success": True,
            "task_session_id": task_session_id,
            "status": "WAITING_REPLY",
            "depth": depth + 1,
            "message": f"Task session created: {task_session_id}. Agent will pause.",
        }

    async def finish_task_session(
        self,
        task_session_id: str,
        result: str,
    ) -> dict:
        session = await self.session_manager.get_session(task_session_id)
        if session is None:
            raise ValueError(f"Task session not found: {task_session_id}")

        if not session.is_task:
            raise ValueError(f"Session {task_session_id} is not a task session")

        if session.created_by != f"agent:{self.agent_id}":
            raise ValueError(
                f"Permission denied: task was created by {session.created_by}, "
                f"not agent:{self.agent_id}"
            )

        await self.session_manager.update_session(
            task_session_id,
            status="FINISHED",
        )

        await self.event_bus.send_event(
            Event(
                src=f"agent:{self.agent_id}",
                dst=[f"agent:{self.agent_id}"],
                type=EventType.TASK_FINISHED,
                payload={
                    "task_session_id": task_session_id,
                    "parent_session_id": session.parent_id,
                    "result": result,
                },
                session_id=task_session_id,
            )
        )

        if session.parent_id:
            is_empty, _ = await self.session_manager.remove_from_waiting_list(
                session.parent_id,
                task_session_id,
            )

            if is_empty:
                await self.session_manager.update_session(
                    session.parent_id,
                    status="ACTIVE",
                )

        return {"success": True, "status": "FINISHED"}

    async def fail_task_session(
        self,
        task_session_id: str,
        reason: str,
    ) -> dict:
        session = await self.session_manager.get_session(task_session_id)
        if session is None:
            raise ValueError(f"Task session not found: {task_session_id}")

        if not session.is_task:
            raise ValueError(f"Session {task_session_id} is not a task session")

        if session.created_by != f"agent:{self.agent_id}":
            raise ValueError(
                f"Permission denied: task was created by {session.created_by}, "
                f"not agent:{self.agent_id}"
            )

        await self.session_manager.update_session(
            task_session_id,
            status="FAILED",
        )

        await self.event_bus.send_event(
            Event(
                src=f"agent:{self.agent_id}",
                dst=[f"agent:{self.agent_id}"],
                type=EventType.TASK_FAILED,
                payload={
                    "task_session_id": task_session_id,
                    "parent_session_id": session.parent_id,
                    "reason": reason,
                },
                session_id=task_session_id,
            )
        )

        if session.parent_id:
            is_empty, _ = await self.session_manager.remove_from_waiting_list(
                session.parent_id,
                task_session_id,
            )

            if is_empty:
                await self.session_manager.update_session(
                    session.parent_id,
                    status="ACTIVE",
                )

        return {"success": True, "status": "FAILED"}
