"""Server configuration."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


def _find_project_root() -> Path:
    """Find the project root (the directory containing ``data/``).

    Checks ``SIMU_PROJECT_ROOT`` env var first, then walks up from multiple
    starting points to find the directory containing ``data/initial_state_v4.json``.
    """
    # Explicit override — always wins
    env_root = os.environ.get("SIMU_PROJECT_ROOT")
    if env_root:
        p = Path(env_root).resolve()
        logger.info("Using SIMU_PROJECT_ROOT=%s", p)
        return p

    marker = Path("data") / "initial_state_v4.json"
    candidates: list[Path] = [
        # Walk up from this source file (editable installs)
        Path(__file__).resolve().parent,
        # Walk up from CWD
        Path.cwd().resolve(),
        # Walk up from venv root (non-editable installs)
        Path(sys.prefix).resolve(),
        # Walk up from the Python executable itself
        Path(sys.executable).resolve().parent,
    ]

    for start in candidates:
        current = start
        for _ in range(10):
            if (current / marker).is_file():
                logger.info("Project root found: %s (from %s)", current, start)
                return current
            current = current.parent

    logger.warning(
        "Could not find project root (looked for %s from %s). "
        "Set SIMU_PROJECT_ROOT env var to fix this.",
        marker,
        [str(c) for c in candidates],
    )
    return Path.cwd()


class ServerConfig(BaseSettings):
    """Server settings loaded from .env file and/or env vars.

    Precedence: env vars > .env file > defaults.
    """

    model_config = {"env_prefix": "SIMU_", "env_file": ".env", "env_file_encoding": "utf-8"}

    host: str = "0.0.0.0"
    port: int = 8000

    # Paths (relative paths are resolved against the project root)
    data_dir: Path = Path("data")
    db_path: Path = Path("data/db/server.db")
    memory_dir: Path = Path("data/memory")
    agent_templates_dir: Path = Path("data/agent_templates")
    agents_dir: Path = Path("data/agents")
    default_agents_dir: Path = Path("data/default_agents")
    initial_state_path: Path = Path("data/initial_state_v4.json")

    # Agent process management
    agent_heartbeat_timeout: int = 90  # seconds
    agent_invocation_timeout: int = 600  # seconds
    agent_queue_depth: int = 10

    # LLM (for agent generation only — Server does NOT do LLM reasoning)
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-20250514"
    llm_api_key: str = ""
    llm_base_url: str = ""  # Custom base URL for OpenAI-compatible APIs

    @model_validator(mode="after")
    def _resolve_relative_paths(self) -> "ServerConfig":
        """Resolve relative paths against the project root, not CWD."""
        root = _find_project_root()
        path_fields = [
            "data_dir", "db_path", "memory_dir", "agent_templates_dir",
            "agents_dir", "default_agents_dir", "initial_state_path",
        ]
        for field in path_fields:
            p = getattr(self, field)
            if not p.is_absolute():
                setattr(self, field, root / p)
        return self


settings = ServerConfig()
