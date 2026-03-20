import os
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass
class BenchmarkConfig:
    provider: str = "anthropic"
    model: str = "claude-3-5-sonnet-20241022"
    api_key: str = ""  # Loaded from env or file
    base_url: str | None = None  # Optional for custom endpoints
    timeout: int = 120  # Request timeout in seconds
    max_retries: int = 3

    @classmethod
    def load(cls, config_path: str | None = None) -> "BenchmarkConfig":
        """Load config from file or environment variables. Priority: explicit path, project config, environment vars, defaults."""

        # Helper to build from a dict representing llm
        def _from_llm_dict(llm: dict) -> dict:
            provider = llm.get("provider")
            model = llm.get("model")
            api_key = llm.get("api_key")
            base_url = llm.get("base_url")
            if base_url is None:
                # compatibility with older configs using api_base
                base_url = llm.get("api_base")
            timeout = llm.get("timeout")
            max_retries = llm.get("max_retries")
            return {
                "provider": provider,
                "model": model,
                "api_key": api_key,
                "base_url": base_url,
                "timeout": timeout,
                "max_retries": max_retries,
            }

        # 1) Load from explicit path if provided
        llm_from_source: dict = {}
        if config_path:
            p = Path(config_path)
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                llm_from_source = data.get("llm", {}) if isinstance(data, dict) else {}

        # 2) Load from project root config.benchmark.yaml if available
        if not llm_from_source:
            repo_root = Path(__file__).resolve().parents[1]
            candidate = repo_root / "config.benchmark.yaml"
            if candidate.exists():
                with open(candidate, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                if isinstance(data, dict):
                    llm_from_source = data.get("llm", {})

        # 4) Environment variables as fallback (order: provider, model, api_key, base_url, timeout, max_retries)
        env_provider = os.getenv("BENCHMARK_LLM_PROVIDER")
        env_model = os.getenv("BENCHMARK_LLM_MODEL")
        env_api_key = os.getenv("BENCHMARK_LLM_API_KEY")
        env_base_url = os.getenv("BENCHMARK_LLM_BASE_URL")
        env_timeout = os.getenv("BENCHMARK_LLM_TIMEOUT")
        env_max_retries = os.getenv("BENCHMARK_LLM_MAX_RETRIES")

        # Start with defaults from class
        provider = cls.__annotations__["provider"]
        model = cls.__annotations__["model"]
        api_key = cls.__annotations__["api_key"]
        base_url = cls.__annotations__["base_url"]
        timeout = cls.__annotations__["timeout"]
        max_retries = cls.__annotations__["max_retries"]

        # Override with file/env values if present
        if llm_from_source:
            from_file = _from_llm_dict(llm_from_source)
            provider = from_file.get("provider") or provider
            model = from_file.get("model") or model
            api_key = from_file.get("api_key") if from_file.get("api_key") is not None else api_key
            base_url = (
                from_file.get("base_url") if from_file.get("base_url") is not None else base_url
            )
            timeout = from_file.get("timeout") if from_file.get("timeout") is not None else timeout
            max_retries = (
                from_file.get("max_retries")
                if from_file.get("max_retries") is not None
                else max_retries
            )

        if env_provider is not None:
            provider = env_provider
        if env_model is not None:
            model = env_model
        if env_api_key is not None:
            api_key = env_api_key
        if env_base_url is not None:
            base_url = env_base_url
        if env_timeout is not None:
            try:
                timeout = int(env_timeout)
            except ValueError:
                pass
        if env_max_retries is not None:
            try:
                max_retries = int(env_max_retries)
            except ValueError:
                pass

        # Normalize missing values to defaults
        provider = provider or "anthropic"
        model = model or "claude-3-5-sonnet-20241022"
        api_key = api_key or ""
        base_url = base_url
        timeout = int(timeout) if timeout is not None else 120
        max_retries = int(max_retries) if max_retries is not None else 3

        return cls(provider, model, api_key, base_url, timeout, max_retries)
