"""轻量级异步事件总线。

设计特点：
1. 内存优先：Phase 1 使用内存队列，Phase 2 可考虑持久化
2. 优先级队列：关键事件优先处理
3. 订阅模式：支持按事件类型、Agent、省份过滤
4. 背压控制：队列满时丢弃低优先级事件
5. Future/Promise：支持请求-响应模式的零延迟等待
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING, Any, Awaitable, Callable
from uuid import uuid4

if TYPE_CHECKING:
    from simu_emperor.engine.models.state import GamePhase


class EventPriority(IntEnum):
    """事件处理优先级。"""

    CRITICAL = 0  # 关键事件：状态变更、阶段切换
    HIGH = 1  # 高优先级：Agent 执行请求
    NORMAL = 2  # 普通优先级：数据查询、报告生成
    LOW = 3  # 低优先级：日志、监控


class EventType(StrEnum):
    """系统事件类型（Phase 1 范围）。"""

    # 阶段事件
    PHASE_TRANSITION = "phase_transition"  # 阶段切换

    # Agent 生命周期事件
    AGENT_SUMMARY_REQUESTED = "agent_summary_requested"
    AGENT_SUMMARY_COMPLETED = "agent_summary_completed"
    AGENT_RESPONSE_REQUESTED = "agent_response_requested"
    AGENT_RESPONSE_COMPLETED = "agent_response_completed"
    AGENT_EXECUTE_REQUESTED = "agent_execute_requested"
    AGENT_EXECUTE_COMPLETED = "agent_execute_completed"

    # 数据事件
    PROVINCE_DATA_CHANGED = "province_data_changed"
    NATIONAL_DATA_CHANGED = "national_data_changed"

    # 玩家事件
    PLAYER_COMMAND_SUBMITTED = "player_command_submitted"
    PLAYER_MESSAGE_SENT = "player_message_sent"


@dataclass(frozen=True)
class EventFilter:
    """事件订阅过滤器。"""

    event_types: set[EventType] = field(default_factory=set)
    agent_ids: set[str] | None = None  # None = 所有 Agent
    province_ids: set[str] | None = None  # None = 所有省份
    phases: set[GamePhase] | None = None  # None = 所有阶段

    def matches(self, event: ControlEvent) -> bool:
        """检查事件是否匹配过滤器。"""
        if self.event_types and event.type not in self.event_types:
            return False
        if self.agent_ids is not None and event.agent_id not in self.agent_ids:
            return False
        if self.province_ids is not None and event.province_id not in self.province_ids:
            return False
        if self.phases is not None and event.phase not in self.phases:
            return False
        return True


@dataclass(order=True)
class ControlEvent:
    """运行时控制事件（Phase 1 内部使用，不替换 GameEvent）。

    与 GameEvent 的区别：
    - GameEvent: 游戏数据事件，需要持久化到存档（PlayerEvent/AgentEvent/RandomEvent）
    - ControlEvent: 运行时控制流事件，用于系统内部通信，不持久化

    注意：使用 order=True 支持 PriorityQueue 排序（按 event_id 字典序）
    """

    # 排序字段（优先级队列需要可比较对象）
    event_id: str = field(compare=True)
    type: EventType = field(compare=False)
    timestamp: float = field(compare=False)
    turn: int = field(compare=False)
    phase: GamePhase = field(compare=False)

    # 可选上下文
    agent_id: str | None = field(default=None, compare=False)
    province_id: str | None = field(default=None, compare=False)
    payload: dict[str, Any] = field(default_factory=dict, compare=False)

    # 追踪
    correlation_id: str | None = field(default=None, compare=False)
    parent_id: str | None = field(default=None, compare=False)


# 处理器类型定义
EventHandler = Callable[[ControlEvent], Awaitable[None]]


class EventBus:
    """轻量级异步事件总线。"""

    def __init__(
        self,
        max_queue_size: int = 1000,
    ) -> None:
        self._max_queue_size = max_queue_size

        # 优先级队列：asyncio.PriorityQueue
        self._queue: asyncio.PriorityQueue[tuple[int, ControlEvent]] = (
            asyncio.PriorityQueue()
        )

        # 订阅表：EventType -> list[(filter, handler)]
        self._subscribers: dict[
            EventType, list[tuple[EventFilter, EventHandler]]
        ] = defaultdict(list)

        # 事件历史（用于调试观测，Phase 1 仅内存，上限较小）
        # Phase 2+: 持久化到 SQLite event_log 表，支持完整历史查询
        self._event_history: list[ControlEvent] = []
        self._max_history = 1000

        # 运行状态
        self._running = False
        self._dispatcher_task: asyncio.Task | None = None

        # Future/Promise 映射：request_key -> Future
        # request_key 格式: "{correlation_id}:{agent_id}" 或 "{correlation_id}"
        self._pending_requests: dict[str, asyncio.Future[ControlEvent]] = {}

        # 指标
        self._metrics = {
            "published": 0,
            "delivered": 0,
            "dropped": 0,
            "handler_errors": 0,
            "requests_completed": 0,
            "requests_timeout": 0,
        }

    async def start(self) -> None:
        """启动事件分发器。"""
        if self._running:
            return
        self._running = True
        self._dispatcher_task = asyncio.create_task(self._dispatch_loop())

    async def stop(self) -> None:
        """停止事件分发器。"""
        self._running = False
        if self._dispatcher_task:
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except asyncio.CancelledError:
                pass

        # 取消所有 pending requests
        for fut in self._pending_requests.values():
            if not fut.done():
                fut.cancel()
        self._pending_requests.clear()

    def create_request_future(
        self,
        correlation_id: str,
        agent_id: str | None = None,
    ) -> asyncio.Future[ControlEvent]:
        """创建可等待的请求 Future。

        Args:
            correlation_id: 请求关联 ID
            agent_id: 可选的 Agent ID，用于区分同一批次中不同 Agent 的响应

        Returns:
            asyncio.Future，可被 await 等待完成事件
        """
        key = f"{correlation_id}:{agent_id}" if agent_id else correlation_id
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[ControlEvent] = loop.create_future()
        self._pending_requests[key] = fut
        return fut

    def cancel_request(self, correlation_id: str, agent_id: str | None = None) -> None:
        """取消请求 Future。"""
        key = f"{correlation_id}:{agent_id}" if agent_id else correlation_id
        fut = self._pending_requests.pop(key, None)
        if fut and not fut.done():
            fut.cancel()

    async def publish(
        self,
        event_type: EventType,
        turn: int,
        phase: GamePhase,
        agent_id: str | None = None,
        province_id: str | None = None,
        payload: dict[str, Any] | None = None,
        priority: EventPriority = EventPriority.NORMAL,
        correlation_id: str | None = None,
        parent_id: str | None = None,
    ) -> ControlEvent:
        """发布事件到总线。

        Returns:
            创建的事件对象（包含生成的 event_id）
        """
        event = ControlEvent(
            event_id=uuid4().hex,
            type=event_type,
            timestamp=time.time(),
            turn=turn,
            phase=phase,
            agent_id=agent_id,
            province_id=province_id,
            payload=payload or {},
            correlation_id=correlation_id,
            parent_id=parent_id,
        )

        # 背压控制：队列满时丢弃低优先级事件
        if self._queue.qsize() >= self._max_queue_size:
            if priority.value >= EventPriority.LOW.value:
                self._metrics["dropped"] += 1
                return event  # 静默丢弃
            # 高优先级：等待队列有空位
            while self._queue.qsize() >= self._max_queue_size:
                await asyncio.sleep(0.01)

        await self._queue.put((priority.value, event))
        self._metrics["published"] += 1

        # 记录历史
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        return event

    def subscribe(
        self,
        event_types: list[EventType],
        handler: EventHandler,
        filter: EventFilter | None = None,
    ) -> Callable[[], None]:
        """订阅事件。

        Args:
            event_types: 要订阅的事件类型列表
            handler: 事件处理器
            filter: 可选的过滤器

        Returns:
            取消订阅函数
        """
        if filter is None:
            filter = EventFilter()

        subscriptions = []
        for event_type in event_types:
            self._subscribers[event_type].append((filter, handler))
            subscriptions.append((event_type, handler))

        def unsubscribe():
            for event_type, handler in subscriptions:
                self._subscribers[event_type] = [
                    (f, h) for f, h in self._subscribers[event_type] if h != handler
                ]

        return unsubscribe

    async def _dispatch_loop(self) -> None:
        """事件分发循环。"""
        while self._running:
            try:
                # 使用 timeout 以便检查 _running 状态
                priority, event = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                await self._dispatch_event(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                # 记录错误但继续运行
                import logging
                logging.getLogger(__name__).error(f"Event dispatch error: {e}")

    async def _dispatch_event(self, event: ControlEvent) -> None:
        """分发单个事件到所有匹配的处理器。"""
        # 1. 处理 Future 等待（仅对完成类型事件）
        # 完成事件类型：*_completed
        if event.correlation_id and str(event.type).endswith("_completed"):
            # 尝试匹配带 agent_id 的 key
            key_with_agent = f"{event.correlation_id}:{event.agent_id}"
            key_without_agent = event.correlation_id

            fut = self._pending_requests.pop(key_with_agent, None)
            if fut is None:
                fut = self._pending_requests.pop(key_without_agent, None)

            if fut and not fut.done():
                fut.set_result(event)
                self._metrics["requests_completed"] += 1

        # 2. 分发到订阅的处理器
        handlers = self._subscribers.get(event.type, [])

        tasks = []
        for filter, handler in handlers:
            if filter.matches(event):
                tasks.append(self._invoke_handler(handler, event))

        if tasks:
            # 并发执行所有处理器
            await asyncio.gather(*tasks, return_exceptions=True)

        self._metrics["delivered"] += 1

    async def _invoke_handler(
        self, handler: EventHandler, event: ControlEvent
    ) -> None:
        """调用单个处理器并处理异常。"""
        try:
            await handler(event)
        except Exception as e:
            self._metrics["handler_errors"] += 1
            # 记录错误但不中断其他处理器
            import logging
            logging.getLogger(__name__).error(
                f"Handler error for {event.type}: {e}"
            )

    def get_metrics(self) -> dict[str, int]:
        """获取事件总线指标。"""
        return dict(self._metrics)

    def get_event_history(
        self,
        event_types: list[EventType] | None = None,
        turn: int | None = None,
        limit: int = 100,
    ) -> list[ControlEvent]:
        """获取事件历史（用于调试和观测）。"""
        events = self._event_history

        if event_types:
            events = [e for e in events if e.type in event_types]
        if turn is not None:
            events = [e for e in events if e.turn == turn]

        return events[-limit:]
