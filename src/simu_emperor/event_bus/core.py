"""
EventBus 核心实现

提供事件路由、订阅和发布功能。
"""

import asyncio
from collections import defaultdict
from typing import Callable, Awaitable
import logging

from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.logger import EventLogger


logger = logging.getLogger(__name__)


EventHandler = Callable[[Event], Awaitable[None] | None]
"""
事件处理器类型

可以是同步函数或异步函数。
"""


class EventBus:
    """
    事件总线

    负责事件的订阅、取消订阅和路由分发。
    支持点对点（单播）、一对多（组播）和广播。

    Attributes:
        _subscribers: 订阅者字典 {dst: [handlers]}
        _event_logger: 事件日志记录器
    """

    def __init__(self, event_logger: EventLogger | None = None):
        """
        初始化 EventBus

        Args:
            event_logger: 事件日志记录器（可选）
        """
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._event_logger = event_logger
        logger.info("EventBus initialized")

    def subscribe(self, dst: str, handler: EventHandler) -> None:
        """
        订阅事件

        Args:
            dst: 目标标识符（如 "player", "agent:revenue_minister", "*"）
            handler: 事件处理函数

        Example:
            ```python
            async def handle_event(event: Event):
                print(f"Received: {event}")

            event_bus.subscribe("player", handle_event)
            event_bus.subscribe("*", handle_event)  # 订阅所有事件
            ```
        """
        if not callable(handler):
            raise TypeError(f"Handler must be callable, got {type(handler)}")

        # 检查是否已经订阅过
        handler_ids = [id(h) for h in self._subscribers[dst]]
        if id(handler) in handler_ids:
            logger.warning(f"⚠️  [EventBus] Handler {handler.__name__} already subscribed to {dst}, skipping")
            return

        self._subscribers[dst].append(handler)
        logger.debug(f"✅ [EventBus] Subscribed: dst={dst}, handler={handler.__name__}")

    def unsubscribe(self, dst: str, handler: EventHandler) -> bool:
        """
        取消订阅

        Args:
            dst: 目标标识符
            handler: 事件处理函数

        Returns:
            是否成功取消订阅（如果未订阅则返回 False）
        """
        if dst not in self._subscribers:
            return False

        try:
            self._subscribers[dst].remove(handler)
            logger.debug(f"Unsubscribed: dst={dst}, handler={handler.__name__}")

            # 如果该 dst 没有订阅者了，删除键
            if not self._subscribers[dst]:
                del self._subscribers[dst]

            return True
        except ValueError:
            return False

    def _route_event(self, event: Event) -> list[EventHandler]:
        """
        路由事件到对应的处理器

        路由规则：
        1. 精确匹配：如果 dst 在订阅列表中，返回对应的处理器
        2. 前缀匹配：如果 dst 以 "agent:" 开头，匹配 "agent:*"
        3. 广播匹配：如果订阅了 "*"，返回对应的处理器

        Args:
            event: 事件对象

        Returns:
            匹配的处理器列表（去重）
        """
        handlers: list[EventHandler] = []
        seen_handlers = set()  # 用于去重（通过 id）

        logger.debug(f"🔀 [EventBus] Routing event: {event.type} to {event.dst}")

        # 精确匹配
        for dst in event.dst:
            if dst in self._subscribers:
                logger.debug(f"  📌 [EventBus] Exact match: {dst} -> {len(self._subscribers[dst])} handlers")
                for handler in self._subscribers[dst]:
                    if id(handler) not in seen_handlers:
                        handlers.append(handler)
                        seen_handlers.add(id(handler))

        # 前缀匹配（agent:*）
        for dst in event.dst:
            if dst.startswith("agent:"):
                agent_wildcard = "agent:*"
                if agent_wildcard in self._subscribers:
                    logger.debug(f"  🌟 [EventBus] Prefix match: {agent_wildcard} -> {len(self._subscribers[agent_wildcard])} handlers")
                    for handler in self._subscribers[agent_wildcard]:
                        if id(handler) not in seen_handlers:
                            handlers.append(handler)
                            seen_handlers.add(id(handler))

        # 广播匹配
        if "*" in self._subscribers:
            logger.debug(f"  📡 [EventBus] Broadcast match: * -> {len(self._subscribers['*'])} handlers")
            for handler in self._subscribers["*"]:
                if id(handler) not in seen_handlers:
                    handlers.append(handler)
                    seen_handlers.add(id(handler))

        logger.debug(f"  ✅ [EventBus] Total unique handlers: {len(handlers)}")
        return handlers

    async def send_event(self, event: Event) -> None:
        """
        异步发送事件

        路由事件到所有匹配的处理器，并异步执行处理器。
        使用 fire-and-forget 模式（不等待处理器完成）。

        Args:
            event: 事件对象

        Example:
            ```python
            event = Event(
                src="player",
                dst=["agent:revenue_minister"],
                type=EventType.COMMAND,
                payload={"action": "adjust_tax", "rate": 0.1}
            )
            await event_bus.send_event(event)
            ```
        """
        request_id = event.payload.get("_request_id", "unknown")
        logger.debug(f"📤 [EventBus:{request_id}] send_event called: {event.type} -> {event.dst}")

        # 记录日志
        if self._event_logger:
            try:
                self._event_logger.log(event)
            except Exception as e:
                logger.error(f"Failed to log event: {e}")

        # 路由事件
        handlers = self._route_event(event)

        if not handlers:
            logger.debug(f"No handlers for event: {event}")
            return

        # 异步执行所有处理器（fire-and-forget）
        tasks = []
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    # 异步处理器
                    task = asyncio.create_task(handler(event))
                    tasks.append(task)
                else:
                    # 同步处理器，在 asyncio 中执行
                    task = asyncio.create_task(self._run_sync_handler(handler, event))
                    tasks.append(task)
            except Exception as e:
                logger.error(f"Failed to create task for handler {handler.__name__}: {e}")

        # 不等待任务完成（fire-and-forget）
        logger.debug(f"✅ [EventBus:{request_id}] Event sent to {len(tasks)} handlers")

    def send_event_sync(self, event: Event) -> None:
        """
        同步发送事件（非异步接口）

        注意：此方法会在当前线程的事件循环中调度事件。
        如果没有运行中的事件循环，会创建一个新的。

        Args:
            event: 事件对象
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，使用 call_soon
                asyncio.ensure_future(self.send_event(event))
            else:
                # 如果事件循环未运行，直接运行
                loop.run_until_complete(self.send_event(event))
        except RuntimeError:
            # 没有事件循环，创建一个新的
            asyncio.run(self.send_event(event))

    async def _run_sync_handler(self, handler: EventHandler, event: Event) -> None:
        """
        在异步上下文中运行同步处理器

        Args:
            handler: 同步处理器
            event: 事件对象
        """
        try:
            result = handler(event)
            # 如果返回的是 awaitable，等待它
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Error in sync handler {handler.__name__}: {e}", exc_info=True)

    def get_subscribers(self) -> dict[str, list[EventHandler]]:
        """
        获取所有订阅者（调试用）

        Returns:
            订阅者字典的副本
        """
        return dict(self._subscribers)

    def clear_subscribers(self) -> None:
        """清除所有订阅者（测试用）"""
        self._subscribers.clear()
        logger.debug("All subscribers cleared")
