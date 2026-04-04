"""Agent configuration loaded from environment variables and config files."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

from simu_shared.models import ContextConfig, LLMConfig, ReActConfig


class AgentConfig(BaseModel):
    """Complete configuration for an Agent process.

    Primary values come from environment variables set by the Server
    when spawning the process. LLM, context, and react settings can
    be overridden via a config file.
    """

    agent_id: str
    server_url: str = "http://localhost:8000"
    agent_token: str = ""
    config_path: Path = Path(".")

    llm: LLMConfig = Field(default_factory=LLMConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    react: ReActConfig = Field(default_factory=ReActConfig)

    @classmethod
    def from_env(cls) -> AgentConfig:
        """Build config from environment variables set by Server."""
        return cls(
            agent_id=os.environ["SIMU_AGENT_ID"],
            server_url=os.environ.get("SIMU_SERVER_URL", "http://localhost:8000"),
            agent_token=os.environ.get("SIMU_AGENT_TOKEN", ""),
            config_path=Path(os.environ.get("SIMU_CONFIG_PATH", ".")),
        )
