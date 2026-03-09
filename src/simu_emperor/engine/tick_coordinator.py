"""Tick 计时器协调器 - 负责定时触发 tick (V4)."""

import asyncio
import logging
import time
from datetime import datetime

from simu_emperor.event_bus.core import EventBus
from simu_emperor.engine.engine import Engine


logger = logging.getLogger(__name__)


class TickCoordinator:
    """Tick 计时器协调器 - 负责定时触发 tick

    维护 tick 计时器，收集活跃的 Incident 和 Effect，
    调用 Engine 计算每个 tick。
    """

    def __init__(
        self,
        event_bus: EventBus,
        engine: Engine,
        tick_interval_seconds: int = 5
    ):
        """初始化 TickCoordinator

        Args:
            event_bus: EventBus 实例，用于发布 tick_completed 事件
            engine: Engine 实例，用于执行 tick 计算
            tick_interval_seconds: 每个 tick 间隔秒数（默认 5 秒）
        """
        self.event_bus = event_bus
        self.engine = engine
        self.tick_interval = tick_interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """启动定时 tick

        如果已经运行，则不执行任何操作。
        """
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._tick_loop())
        logger.info(f"TickCoordinator started with interval {self.tick_interval}s")

    async def stop(self) -> None:
        """停止定时 tick"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("TickCoordinator stopped")

    async def _tick_loop(self) -> None:
        """主循环：执行 tick → 计算剩余间隔 → 等待 → 循环"""
        while self._running:
            start_time = time.monotonic()
            try:
                # 执行 tick 计算
                new_state = self.engine.apply_tick()

                # 持久化（通过 repository）
                # TODO: 调用 persistence 保存新状态

                # 发布 tick_completed 事件
                await self.event_bus.publish(
                    src="system:tick_coordinator",
                    dst=["*"],
                    type="tick_completed",
                    payload={
                        "tick": new_state.turn,
                        "timestamp": datetime.now().isoformat()
                    }
                )

                logger.info(f"Tick {new_state.turn} completed")

                # 计算剩余等待时间，保证固定间隔
                elapsed = time.monotonic() - start_time
                sleep_time = max(0, self.tick_interval - elapsed)

                if elapsed > self.tick_interval:
                    logger.warning(
                        f"Tick took {elapsed:.2f}s, exceeds interval {self.tick_interval}s"
                    )

                await asyncio.sleep(sleep_time)

            except Exception as e:
                # 记录错误但继续运行
                logger.error(f"Tick error: {e}")
                await asyncio.sleep(self.tick_interval)
