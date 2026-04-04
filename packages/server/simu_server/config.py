"""Server configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class ServerConfig(BaseSettings):
    """Server settings loaded from env vars / config file."""

    model_config = {"env_prefix": "SIMU_"}

    host: str = "0.0.0.0"
    port: int = 8000

    # Paths
    data_dir: Path = Path("data")
    db_path: Path = Path("data/db/server.db")
    agent_templates_dir: Path = Path("data/agent_templates")
    agents_dir: Path = Path("data/agents")
    initial_state_path: Path = Path("data/initial_state.json")

    # Agent process management
    agent_heartbeat_timeout: int = 90  # seconds
    agent_invocation_timeout: int = 600  # seconds
    agent_queue_depth: int = 10

    # LLM (for agent generation only — Server does NOT do LLM reasoning)
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-20250514"
    llm_api_key: str = ""


settings = ServerConfig()
