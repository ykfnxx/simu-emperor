"""Server configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings


def _find_project_root() -> Path:
    """Walk up from this file to find the project root (contains data/ dir)."""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "data").is_dir():
            return current
        current = current.parent
    # Fallback to CWD if project root not found
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
