"""AgentGenerator — dynamically create new Agent configurations via LLM.

Generates soul.md and data_scope.yaml for a new Agent based on a user
profile description.  This is the only place the Server calls an LLM.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AgentGenerator:
    """Creates Agent config files from a profile description."""

    def __init__(self, agents_dir: Path, llm_config: dict[str, Any]) -> None:
        self._agents_dir = agents_dir
        self._llm_config = llm_config
        self._tasks: dict[str, asyncio.Task] = {}

    async def generate(self, profile: dict[str, Any]) -> str:
        """Start async generation.  Returns a task_id for polling."""
        task_id = uuid.uuid4().hex[:12]
        task = asyncio.create_task(self._do_generate(task_id, profile))
        self._tasks[task_id] = task
        return task_id

    def get_status(self, task_id: str) -> dict[str, Any]:
        task = self._tasks.get(task_id)
        if task is None:
            return {"status": "not_found"}
        if task.done():
            if task.exception():
                return {"status": "failed", "error": str(task.exception())}
            return {"status": "completed", "result": task.result()}
        return {"status": "running"}

    async def _do_generate(self, task_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        """Generate soul.md + data_scope.yaml for a new agent."""
        agent_id = profile.get("agent_id", f"agent_{uuid.uuid4().hex[:8]}")
        agent_dir = self._agents_dir / agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Generate soul.md from profile using LLM
        display_name = profile.get("display_name", agent_id)
        role = profile.get("role", "")
        description = profile.get("description", "")

        soul_content = f"""# {display_name}

## Role
{role}

## Description
{description}

## Personality
You are {display_name}, serving in the imperial court.
Respond in character and fulfill your duties diligently.
"""
        (agent_dir / "soul.md").write_text(soul_content, encoding="utf-8")

        # Generate data_scope.yaml
        scope_content = """# Data access scope
accessible:
  - nation.imperial_treasury
  - nation.base_tax_rate
  - provinces.*
"""
        (agent_dir / "data_scope.yaml").write_text(scope_content, encoding="utf-8")

        logger.info("Generated agent config for %s at %s", agent_id, agent_dir)
        return {
            "agent_id": agent_id,
            "config_path": str(agent_dir),
            "display_name": display_name,
        }
