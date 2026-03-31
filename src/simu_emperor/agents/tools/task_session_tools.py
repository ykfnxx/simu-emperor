"""Task session tools for V4 Task Session architecture."""

import json
import uuid
from datetime import datetime, timezone

from simu_emperor.agents.config import AgentState
from simu_emperor.agents.tools.registry import ToolProvider, ToolResult, tool
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.session.constants import MAX_TASK_DEPTH
from simu_emperor.session.models import Session

# Maximum number of members allowed in a task session
# This prevents task creation in crowded sessions (>2 members)
MAX_TASK_SESSION_MEMBERS = 2


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskSessionTools(ToolProvider):
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

    @tool(
        name="create_task_session",
        description="创建任务会话",
        parameters={
            "type": "object",
            "properties": {
                "timeout_seconds": {"type": "integer", "default": 300},
                "description": {"type": "string"},
                "goal": {"type": "string"},
                "constraints": {"type": "string"},
            },
            "required": [],
        },
        category="session",
    )
    async def create_task_session(self, args: dict, event: Event) -> ToolResult:
        timeout_seconds = args.get("timeout_seconds", 300)
        description = args.get("description", "")
        current_session_id = event.session_id

        current_session = await self.session_manager.get_session(current_session_id)
        if current_session is None:
            return ToolResult(
                output=json.dumps(
                    {"success": False, "error": f"Current session not found: {current_session_id}"},
                    ensure_ascii=False,
                ),
                success=False,
            )

        current_member_count = len(current_session.agent_states)
        if current_member_count > MAX_TASK_SESSION_MEMBERS:
            return ToolResult(
                output=json.dumps(
                    {
                        "success": False,
                        "error": f"Task session 最多支持 {MAX_TASK_SESSION_MEMBERS} 个成员。当前 session 有 {current_member_count} 个成员。",
                    },
                    ensure_ascii=False,
                ),
                success=False,
            )

        depth = self.session_manager._calculate_depth(current_session_id)
        if depth >= MAX_TASK_DEPTH:
            return ToolResult(
                output=json.dumps(
                    {
                        "success": False,
                        "error": f"Task nesting depth exceeded (max: {MAX_TASK_DEPTH})",
                    },
                    ensure_ascii=False,
                ),
                success=False,
            )

        timestamp = utcnow().strftime("%Y%m%d%H%M%S")
        suffix = uuid.uuid4().hex[:8]
        task_session_id = f"task:{self.agent_id}:{timestamp}:{suffix}"

        await self.session_manager.create_session(
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
                "goal": args.get("goal", ""),
                "constraints": args.get("constraints", ""),
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
                waiting_for_tasks=new_waiting_list,
            )
            await self.session_manager.set_agent_state(
                current_session_id,
                self.agent_id,
                AgentState.WAITING_REPLY.value,
            )

        return ToolResult(
            output=json.dumps(
                {
                    "success": True,
                    "task_session_id": task_session_id,
                    "status": "WAITING_REPLY",
                    "depth": depth + 1,
                    "message": f"Task session created: {task_session_id}. Agent will pause.",
                },
                ensure_ascii=False,
            ),
            creates_task=True,
        )

    async def _validate_task_ownership(
        self, task_session_id: str
    ) -> tuple[dict | None, Session | None]:
        """Check session exists, is a task, not finished, and caller is creator.

        Returns ``(None, session)`` on success, or ``(error_dict, None)`` on failure.
        """
        session = await self.session_manager.get_session(task_session_id)
        if session is None:
            return {"success": False, "error": f"Task session not found: {task_session_id}"}, None
        if not session.is_task:
            return (
                {"success": False, "error": f"Session {task_session_id} is not a task session"},
                None,
            )
        if session.status in ("FINISHED", "FAILED"):
            return {"success": False, "error": f"任务已结束，状态：{session.status}"}, None
        if session.created_by != f"agent:{self.agent_id}":
            return {"success": False, "error": "权限错误：只有任务创建者可以结束任务"}, None
        return None, session

    async def _close_task(
        self,
        task_session_id: str,
        *,
        status: str,
        event_type: str,
        payload_key: str,
        payload_value: str,
        session: Session,
    ) -> dict:
        """Shared close logic: update status, emit event, restore parent state."""
        await self.session_manager.update_session(task_session_id, status=status)

        parent_id = session.parent_id or task_session_id

        await self.event_bus.send_event(
            Event(
                src=f"agent:{self.agent_id}",
                dst=[f"agent:{self.agent_id}"],
                type=event_type,
                payload={
                    "task_session_id": task_session_id,
                    "parent_session_id": session.parent_id,
                    payload_key: payload_value,
                },
                session_id=parent_id,
            )
        )

        if session.parent_id:
            is_empty, _ = await self.session_manager.remove_from_waiting_list(
                session.parent_id, task_session_id
            )
            if is_empty:
                await self.session_manager.set_agent_state(
                    session.parent_id, self.agent_id, AgentState.ACTIVE.value
                )

        return {"success": True, "status": status}

    @tool(
        name="finish_task_session",
        description="完成任务会话",
        parameters={
            "type": "object",
            "properties": {"result": {"type": "string"}},
            "required": ["result"],
        },
        category="session",
    )
    async def finish_task_session(self, args: dict, event: Event) -> ToolResult:
        error, session = await self._validate_task_ownership(event.session_id)
        if error:
            return ToolResult(
                output=json.dumps(error, ensure_ascii=False),
                success=False,
            )

        result = await self._finish_task(event.session_id, args.get("result", ""))
        return ToolResult(
            output=json.dumps(result, ensure_ascii=False),
            closes_task=result.get("success", False),
        )

    @tool(
        name="fail_task_session",
        description="任务会话失败",
        parameters={
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
        category="session",
    )
    async def fail_task_session(self, args: dict, event: Event) -> ToolResult:
        error, session = await self._validate_task_ownership(event.session_id)
        if error:
            return ToolResult(
                output=json.dumps(error, ensure_ascii=False),
                success=False,
            )

        result = await self._fail_task(event.session_id, args.get("reason", ""))
        return ToolResult(
            output=json.dumps(result, ensure_ascii=False),
            closes_task=result.get("success", False),
        )

    async def _finish_task(self, task_session_id: str, result: str) -> dict:
        error, session = await self._validate_task_ownership(task_session_id)
        if error or session is None:
            return error or {"success": False, "error": "Session not found"}

        return await self._close_task(
            task_session_id,
            status="FINISHED",
            event_type=EventType.TASK_FINISHED,
            payload_key="result",
            payload_value=result,
            session=session,
        )

    async def _fail_task(self, task_session_id: str, reason: str) -> dict:
        error, session = await self._validate_task_ownership(task_session_id)
        if error or session is None:
            return error or {"success": False, "error": "Session not found"}

        return await self._close_task(
            task_session_id,
            status="FAILED",
            event_type=EventType.TASK_FAILED,
            payload_key="reason",
            payload_value=reason,
            session=session,
        )
