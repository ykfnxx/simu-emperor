"""Agent configuration loaded from environment variables and config files."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

from simu_shared.models import ContextConfig, LLMConfig, MemoryConfig, ReActConfig


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
    memory: MemoryConfig = Field(default_factory=MemoryConfig)

    @classmethod
    def from_env(cls) -> AgentConfig:
        """Build config from environment variables set by Server."""
        llm_kwargs: dict[str, str] = {}
        if os.environ.get("SIMU_LLM_PROVIDER"):
            llm_kwargs["provider"] = os.environ["SIMU_LLM_PROVIDER"]
        if os.environ.get("SIMU_LLM_MODEL"):
            llm_kwargs["model"] = os.environ["SIMU_LLM_MODEL"]
        if os.environ.get("SIMU_LLM_API_KEY"):
            llm_kwargs["api_key"] = os.environ["SIMU_LLM_API_KEY"]
        if os.environ.get("SIMU_LLM_BASE_URL"):
            llm_kwargs["base_url"] = os.environ["SIMU_LLM_BASE_URL"]

        # Optional separate LLM for memory summarization
        mem_llm_kwargs: dict[str, str] = {}
        if os.environ.get("SIMU_MEMORY_LLM_PROVIDER"):
            mem_llm_kwargs["provider"] = os.environ["SIMU_MEMORY_LLM_PROVIDER"]
        if os.environ.get("SIMU_MEMORY_LLM_MODEL"):
            mem_llm_kwargs["model"] = os.environ["SIMU_MEMORY_LLM_MODEL"]
        if os.environ.get("SIMU_MEMORY_LLM_API_KEY"):
            mem_llm_kwargs["api_key"] = os.environ["SIMU_MEMORY_LLM_API_KEY"]
        if os.environ.get("SIMU_MEMORY_LLM_BASE_URL"):
            mem_llm_kwargs["base_url"] = os.environ["SIMU_MEMORY_LLM_BASE_URL"]

        memory_config = MemoryConfig()
        if mem_llm_kwargs:
            memory_config = MemoryConfig(summary_llm=LLMConfig(**mem_llm_kwargs))

        return cls(
            agent_id=os.environ["SIMU_AGENT_ID"],
            server_url=os.environ.get("SIMU_SERVER_URL", "http://localhost:8000"),
            agent_token=os.environ.get("SIMU_AGENT_TOKEN", ""),
            config_path=Path(os.environ.get("SIMU_CONFIG_PATH", ".")),
            llm=LLMConfig(**llm_kwargs) if llm_kwargs else LLMConfig(),
            memory=memory_config,
        )
