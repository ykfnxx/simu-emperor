"""Tick 计时器协调器 - 负责定时触发 tick (V4)."""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.engine.engine import Engine
from simu_emperor.engine.protocols import GameStateRepository


logger = logging.getLogger(__name__)


def _generate_session_id() -> str:
    """生成新的会话标识符.

    格式: tick:{timestamp}:{uuid_suffix}
    例如: tick:20260310120000:a1b2c3d4
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"tick:{timestamp}:{suffix}"


class TickCoordinator:
    """Tick 计时器协调器 - 负责定时触发 tick

    维护 tick 计时器，收集活跃的 Incident 和 Effect，
    调用 Engine 计算每个 tick，并将状态持久化。
    """

    def __init__(
        self,
        event_bus: EventBus,
        engine: Engine,
        game_repo: GameStateRepository,
        tick_interval_seconds: int = 5,
        incident_repo=None,
    ):
        """初始化 TickCoordinator

        Args:
            event_bus: EventBus 实例，用于发布 tick_completed 事件
            engine: Engine 实例，用于执行 tick 计算
            game_repo: GameStateRepository 实例，用于持久化游戏状态
            tick_interval_seconds: 每个 tick 间隔秒数（默认 5 秒）
            incident_repo: IncidentRepository 实例（可选），用于持久化 incident

        Note:
            TickCoordinator 会自动生成唯一的 session_id，用于事件隔离。
            可通过 get_session_id() 方法获取。
        """
        self.event_bus = event_bus
        self.engine = engine
        self.game_repo = game_repo
        self.incident_repo = incident_repo
        self.session_id = _generate_session_id()
        self.tick_interval = tick_interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None

    def get_session_id(self) -> str:
        """获取当前会话标识符.

        Returns:
            唯一的会话 ID，格式为 tick:{timestamp}:{uuid_suffix}
        """
        return self.session_id

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
        """主循环：执行 tick → 持久化 → 发布事件 → 等待 → 循环"""
        while self._running:
            start_time = time.monotonic()
            try:
                # 执行 tick 计算
                new_state = self.engine.apply_tick()

                # 发布过期 incident 事件 + 持久化
                for expired_inc in self.engine.get_last_expired_incidents():
                    expired_event = Event(
                        src="system:engine",
                        dst=["*"],
                        type="incident_expired",
                        payload={
                            "incident_id": expired_inc.incident_id,
                            "title": expired_inc.title,
                            "source": expired_inc.source,
                        },
                        session_id=self.session_id,
                    )
                    await self.event_bus.send_event(expired_event)
                    if self.incident_repo:
                        await self.incident_repo.expire_incident(
                            expired_inc.incident_id, new_state.turn
                        )
                    logger.info(f"Incident expired: {expired_inc.incident_id} ({expired_inc.title})")

                # 持久化新状态
                await self._persist_state(new_state)

                # 发布 tick_completed 事件
                event = Event(
                    src="system:tick_coordinator",
                    dst=["*"],
                    type="tick_completed",
                    payload={"tick": new_state.turn, "timestamp": datetime.now().isoformat()},
                    session_id=self.session_id,
                )
                await self.event_bus.send_event(event)

                logger.info(f"Tick {new_state.turn} completed and persisted")

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

    async def _persist_state(self, state) -> None:
        """持久化游戏状态.

        Args:
            state: NationData 对象
        """
        try:
            await self.game_repo.save_nation_data(state)
        except Exception as e:
            logger.error(f"Failed to persist state: {e}")
            # 持久化失败不应中断 tick 循环
