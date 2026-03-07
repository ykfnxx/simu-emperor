"""
TaskMonitor for V4 Task Session Architecture.

Background monitoring for task session timeouts.
"""

import asyncio
from datetime import datetime, timezone
import logging

from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.session.manager import SessionManager


logger = logging.getLogger(__name__)


class TaskMonitor:
    """Background monitor for task session timeouts."""

    def __init__(
        self, session_manager: SessionManager, event_bus: EventBus, check_interval: float = 5.0
    ):
        self.session_manager = session_manager
        self.event_bus = event_bus
        self.check_interval = check_interval
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start monitoring."""
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("TaskMonitor started")

    async def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("TaskMonitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            await asyncio.sleep(self.check_interval)
            await self._check_timeouts()

    async def _check_timeouts(self) -> None:
        """Check for timed out sessions."""
        now = datetime.now(timezone.utc)

        for session in self.session_manager.get_waiting_sessions():
            try:
                if (
                    session.timeout_at
                    and now > session.timeout_at
                    and not session.timeout_notified_at
                ):
                    await self._notify_timeout(session)

                    await self.session_manager.update_session(
                        session.session_id,
                        timeout_notified_at=now,
                    )
            except Exception as e:
                logger.error(f"Error checking timeout for {session.session_id}: {e}", exc_info=True)

    async def _notify_timeout(self, session) -> None:
        """Send timeout notification event."""
        await self.event_bus.send_event(
            Event(
                src="system:task_monitor",
                dst=[session.created_by],
                type=EventType.TASK_TIMEOUT,
                payload={
                    "task_session_id": session.session_id,
                    "timeout_at": session.timeout_at.isoformat(),
                },
                session_id=session.session_id,
            )
        )
        logger.info(f"Task timeout notified: {session.session_id}")
