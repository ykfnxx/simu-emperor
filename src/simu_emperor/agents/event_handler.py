"""Agent 事件处理器（Phase 1 适配层）。

将事件转换为对 AgentRuntime 的调用，保持现有 AgentRuntime 不变。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from simu_emperor.core.event_bus import ControlEvent, EventBus, EventFilter, EventType
from simu_emperor.engine.models.events import PlayerEvent

if TYPE_CHECKING:
    from simu_emperor.agents.runtime import AgentRuntime

logger = logging.getLogger(__name__)


class AgentEventHandler:
    """Agent 事件处理器（Phase 1 适配层）。

    将事件转换为对 AgentRuntime 的调用，保持现有 AgentRuntime 不变。
    这是一个薄路由层，后续 Phase 4 Agent 驱动模式会替代此设计。
    """

    def __init__(
        self,
        agent_id: str,
        event_bus: EventBus,
        runtime: AgentRuntime,
    ) -> None:
        self.agent_id = agent_id
        self.event_bus = event_bus
        self.runtime = runtime

        # 订阅相关事件
        self._subscriptions: list[Callable[[], None]] = []
        self._setup_subscriptions()

    def _setup_subscriptions(self) -> None:
        """设置事件订阅。"""
        # 订阅汇总请求
        unsub = self.event_bus.subscribe(
            event_types=[EventType.AGENT_SUMMARY_REQUESTED],
            handler=self._on_summary_requested,
            filter=EventFilter(agent_ids={self.agent_id}),
        )
        self._subscriptions.append(unsub)

        # 订阅响应请求
        unsub = self.event_bus.subscribe(
            event_types=[EventType.AGENT_RESPONSE_REQUESTED],
            handler=self._on_response_requested,
            filter=EventFilter(agent_ids={self.agent_id}),
        )
        self._subscriptions.append(unsub)

        # 订阅执行请求
        unsub = self.event_bus.subscribe(
            event_types=[EventType.AGENT_EXECUTE_REQUESTED],
            handler=self._on_execute_requested,
            filter=EventFilter(agent_ids={self.agent_id}),
        )
        self._subscriptions.append(unsub)

        # 订阅数据变更（用于后续 Agent 主动响应）
        unsub = self.event_bus.subscribe(
            event_types=[EventType.PROVINCE_DATA_CHANGED, EventType.NATIONAL_DATA_CHANGED],
            handler=self._on_data_changed,
            # Phase 1：仅记录，不主动响应
        )
        self._subscriptions.append(unsub)

    def unsubscribe_all(self) -> None:
        """取消所有订阅。"""
        for unsub in self._subscriptions:
            unsub()
        self._subscriptions.clear()

    async def _on_summary_requested(self, event: ControlEvent) -> None:
        """处理汇总请求事件。"""
        from simu_emperor.engine.models.base_data import NationalBaseData

        payload = event.payload
        national_data_raw = payload.get("national_data")

        if isinstance(national_data_raw, NationalBaseData):
            national_data = national_data_raw
        else:
            national_data = NationalBaseData.model_validate(national_data_raw)

        # 调用现有 AgentRuntime
        report = await self.runtime.summarize(
            agent_id=self.agent_id,
            turn=event.turn,
            national_data=national_data,
        )

        # 发布完成事件
        await self.event_bus.publish(
            event_type=EventType.AGENT_SUMMARY_COMPLETED,
            turn=event.turn,
            phase=event.phase,
            agent_id=self.agent_id,
            payload={
                "report": report,
                "request_event_id": event.event_id,
            },
            correlation_id=event.correlation_id,
            parent_id=event.event_id,
        )

    async def _on_response_requested(self, event: ControlEvent) -> None:
        """处理响应请求事件。"""
        from simu_emperor.engine.models.base_data import NationalBaseData

        payload = event.payload
        national_data_raw = payload.get("national_data")
        message = payload.get("message", "")

        if isinstance(national_data_raw, NationalBaseData):
            national_data = national_data_raw
        else:
            national_data = NationalBaseData.model_validate(national_data_raw)

        response = await self.runtime.respond(
            agent_id=self.agent_id,
            turn=event.turn,
            player_message=message,
            national_data=national_data,
        )

        await self.event_bus.publish(
            event_type=EventType.AGENT_RESPONSE_COMPLETED,
            turn=event.turn,
            phase=event.phase,
            agent_id=self.agent_id,
            payload={
                "response": response,
                "request_event_id": event.event_id,
            },
            correlation_id=event.correlation_id,
            parent_id=event.event_id,
        )

    async def _on_execute_requested(self, event: ControlEvent) -> None:
        """处理执行请求事件。"""
        from decimal import Decimal

        from simu_emperor.engine.models.base_data import NationalBaseData
        from simu_emperor.engine.models.events import AgentEvent, EventSource

        payload = event.payload
        national_data_raw = payload.get("national_data")
        command_data = payload.get("command")

        logger.debug(
            f"Agent {self.agent_id} received execute request: "
            f"turn={event.turn}, command_type={command_data.get('command_type') if command_data else None}"
        )

        if isinstance(national_data_raw, NationalBaseData):
            national_data = national_data_raw
        else:
            national_data = NationalBaseData.model_validate(national_data_raw)

        command = PlayerEvent.model_validate(command_data)

        try:
            agent_event = await self.runtime.execute(
                agent_id=self.agent_id,
                turn=event.turn,
                command=command,
                national_data=national_data,
            )
        except Exception as e:
            logger.error(
                f"Agent {self.agent_id} execute failed: {e}. "
                f"Creating fallback AgentEvent."
            )
            # 创建一个降级的 AgentEvent
            agent_event = AgentEvent(
                source=EventSource.AGENT,
                turn_created=event.turn,
                description=f"[执行失败] {command.description} - 因技术原因未能执行：{e}",
                effects=[],
                agent_event_type=command.command_type,
                agent_id=self.agent_id,
                fidelity=Decimal("0"),
            )

        await self.event_bus.publish(
            event_type=EventType.AGENT_EXECUTE_COMPLETED,
            turn=event.turn,
            phase=event.phase,
            agent_id=self.agent_id,
            payload={
                "agent_event": agent_event.model_dump(),
                "request_event_id": event.event_id,
            },
            correlation_id=event.correlation_id,
            parent_id=event.event_id,
        )

    async def _on_data_changed(self, event: ControlEvent) -> None:
        """处理数据变更事件（Phase 1：仅记录）。"""
        # Phase 1：不主动响应，仅记录到 Agent 内部状态
        # Phase 2：Agent 可自主决定是否响应
        logger.debug(
            f"Agent {self.agent_id} observed data change: {event.type} "
            f"at turn {event.turn}"
        )
