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
        current_session_id: str | None = None,
        goal: str = "",
        constraints: str = "",
    ) -> dict:
        current_session = await self.session_manager.get_session(current_session_id)
        if current_session is None:
            raise ValueError(f"Current session not found: {current_session_id}")

        # === 双重检查：确保 task session 最多 2 个成员 ===

        # 检查 1：当前 session 的成员数
        max_members = 2
        current_member_count = len(current_session.agent_states)

        if current_member_count > max_members:
            raise ValueError(
                f"❌ Task session 最多支持 {max_members} 个成员。\n"
                f"当前 session 有 {current_member_count} 个成员，无法创建 task。\n"
                f"请在成员数 ≤ {max_members} 的 session 中创建 task。"
            )

        depth = self.session_manager._calculate_depth(current_session_id)
        if depth >= MAX_TASK_DEPTH:
            raise ValueError(f"Task nesting depth exceeded (max: {MAX_TASK_DEPTH})")

        timestamp = utcnow().strftime("%Y%m%d%H%M%S")
        suffix = uuid.uuid4().hex[:8]
        task_session_id = f"task:{self.agent_id}:{timestamp}:{suffix}"

        _ = await self.session_manager.create_session(
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
                "goal": goal,
                "constraints": constraints,
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
            # 只让创建者 agent 进入 WAITING_REPLY 状态（per-agent 状态管理）
            await self.session_manager.set_agent_state(
                current_session_id,
                self.agent_id,
                "WAITING_REPLY",
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

        if session.status == "FINISHED":
            raise ValueError(f"❌ 任务已完成，不能调用 finish_task_session。任务状态：FINISHED")
        if session.status == "FAILED":
            raise ValueError(f"❌ 任务已失败，不能调用 finish_task_session。任务状态：FAILED")

        if session.created_by != f"agent:{self.agent_id}":
            error_msg = (
                "❌ 权限错误：只有任务创建者可以结束任务。\n"
                f"任务由 {session.created_by} 创建，而你是 agent:{self.agent_id}。\n"
                "⚠️ 作为任务参与者，你应该：\n"
                "1. 只使用 send_message_to_agent 回复消息\n"
                "2. 不要调用 finish_task_session\n"
                "3. 不要调用 respond_to_player\n"
                "4. 等待任务创建者自然结束任务"
            )
            raise ValueError(error_msg)

        await self.session_manager.update_session(
            task_session_id,
            status="FINISHED",
        )

        # Send TASK_FINISHED event to parent session so the agent can resume
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
                session_id=session.parent_id,  # Send to parent session, not task session
            )
        )

        # Update waiting list and agent state AFTER sending the event
        # This ensures the event is sent before the agent state is updated,
        # allowing the agent to process TASK_FINISHED while still WAITING_REPLY
        if session.parent_id:
            is_empty, _ = await self.session_manager.remove_from_waiting_list(
                session.parent_id,
                task_session_id,
            )

            if is_empty:
                # 恢复创建者 agent 的状态为 ACTIVE（per-agent 状态管理）
                await self.session_manager.set_agent_state(
                    session.parent_id,
                    self.agent_id,
                    "ACTIVE",
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

        if session.status == "FINISHED":
            raise ValueError(f"❌ 任务已完成，不能调用 fail_task_session。任务状态：FINISHED")
        if session.status == "FAILED":
            raise ValueError(f"❌ 任务已失败，不能调用 fail_task_session。任务状态：FAILED")

        if session.created_by != f"agent:{self.agent_id}":
            error_msg = (
                "❌ 权限错误：只有任务创建者可以结束任务。\n"
                f"任务由 {session.created_by} 创建，而你是 agent:{self.agent_id}。\n"
                "⚠️ 作为任务参与者，你应该：\n"
                "1. 只使用 send_message_to_agent 回复消息\n"
                "2. 不要调用 finish_task_session\n"
                "3. 不要调用 respond_to_player\n"
                "4. 等待任务创建者自然结束任务"
            )
            raise ValueError(error_msg)

        await self.session_manager.update_session(
            task_session_id,
            status="FAILED",
        )

        # Send TASK_FAILED event to parent session so the agent can resume
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
                session_id=session.parent_id,  # Send to parent session, not task session
            )
        )

        # Update waiting list and agent state AFTER sending the event
        # This ensures the event is sent before the agent state is updated,
        # allowing the agent to process TASK_FAILED while still WAITING_REPLY
        if session.parent_id:
            is_empty, _ = await self.session_manager.remove_from_waiting_list(
                session.parent_id,
                task_session_id,
            )

            if is_empty:
                # 恢复创建者 agent 的状态为 ACTIVE（per-agent 状态管理）
                await self.session_manager.set_agent_state(
                    session.parent_id,
                    self.agent_id,
                    "ACTIVE",
                )

        return {"success": True, "status": "FAILED"}
