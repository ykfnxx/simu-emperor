"""ProcessManager — manages Agent subprocess lifecycle.

Each Agent runs as an independent Python subprocess.  The ProcessManager
spawns, monitors, and terminates these processes.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import uuid
from pathlib import Path
from typing import Any

from simu_shared.models import AgentRegistration, AgentStatus

logger = logging.getLogger(__name__)

_GRACEFUL_SHUTDOWN_TIMEOUT = 30  # seconds


class ProcessManager:
    """Spawn and manage Agent child processes."""

    def __init__(self, server_url: str) -> None:
        self._server_url = server_url
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._tokens: dict[str, str] = {}  # agent_id → callback_token

    async def spawn(self, registration: AgentRegistration) -> int:
        """Start an Agent subprocess.  Returns the PID."""
        token = uuid.uuid4().hex
        self._tokens[registration.agent_id] = token

        env = {
            **os.environ,
            "SIMU_SERVER_URL": self._server_url,
            "SIMU_AGENT_ID": registration.agent_id,
            "SIMU_AGENT_TOKEN": token,
            "SIMU_CONFIG_PATH": registration.config_path,
        }

        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "simu_sdk.agent",
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._processes[registration.agent_id] = proc
        logger.info(
            "Spawned agent %s as PID %d", registration.agent_id, proc.pid,
        )
        return proc.pid or 0

    async def terminate(self, agent_id: str, graceful: bool = True) -> None:
        """Stop an Agent subprocess."""
        proc = self._processes.pop(agent_id, None)
        if proc is None:
            return

        if graceful:
            proc.send_signal(signal.SIGTERM)
            try:
                await asyncio.wait_for(proc.wait(), timeout=_GRACEFUL_SHUTDOWN_TIMEOUT)
            except asyncio.TimeoutError:
                logger.warning("Agent %s did not exit gracefully, sending SIGKILL", agent_id)
                proc.kill()
                await proc.wait()
        else:
            proc.kill()
            await proc.wait()

        self._tokens.pop(agent_id, None)
        logger.info("Agent %s terminated", agent_id)

    async def restart(self, registration: AgentRegistration) -> int:
        await self.terminate(registration.agent_id)
        return await self.spawn(registration)

    def is_alive(self, agent_id: str) -> bool:
        proc = self._processes.get(agent_id)
        return proc is not None and proc.returncode is None

    def get_token(self, agent_id: str) -> str | None:
        return self._tokens.get(agent_id)

    def get_pid(self, agent_id: str) -> int | None:
        proc = self._processes.get(agent_id)
        return proc.pid if proc else None

    async def shutdown_all(self) -> None:
        """Terminate all running Agent processes."""
        agent_ids = list(self._processes)
        for aid in agent_ids:
            await self.terminate(aid)
