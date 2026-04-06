"""Server configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class ServerConfig(BaseSettings):
    """Server settings loaded from .env file and/or env vars.

    Precedence: env vars > .env file > defaults.
    """

    model_config = {"env_prefix": "SIMU_", "env_file": ".env", "env_file_encoding": "utf-8"}

    host: str = "0.0.0.0"
    port: int = 8000

    # Paths
    data_dir: Path = Path("data")
    db_path: Path = Path("data/db/server.db")
    agent_templates_dir: Path = Path("data/agent_templates")
    agents_dir: Path = Path("data/agents")
    default_agents_dir: Path = Path("data/default_agents")
    initial_state_path: Path = Path("data/initial_state.json")

    # Agent process management
    agent_heartbeat_timeout: int = 90  # seconds
    agent_invocation_timeout: int = 600  # seconds
    agent_queue_depth: int = 10

    # LLM (for agent generation only — Server does NOT do LLM reasoning)
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-20250514"
    llm_api_key: str = ""
    llm_base_url: str = ""  # Custom base URL for OpenAI-compatible APIs


settings = ServerConfig()
