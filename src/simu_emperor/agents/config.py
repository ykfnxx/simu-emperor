"""Agent configuration dataclass.

Replaces the 14-parameter Agent constructor with a single dataclass.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class AgentState(str, Enum):
    """Agent state enum for type-safe state comparisons."""

    ACTIVE = "ACTIVE"
    WAITING_REPLY = "WAITING_REPLY"
    FINISHED = "FINISHED"
    FAILED = "FAILED"


@dataclass
class AgentConfig:
    """Construction parameters for Agent.

    Usage::

        config = AgentConfig(agent_id="gov_zhili", event_bus=bus, ...)
        agent = Agent(config)
    """

    agent_id: str
    event_bus: Any
    llm_provider: Any
    data_dir: str | Path
    repository: Any = None
    session_id: str | None = None
    skill_loader: Any = None
    session_manager: Any = None
    tape_writer: Any = None
    tape_metadata_mgr: Any = None
    tape_repository: Any = None
    engine: Any = None
