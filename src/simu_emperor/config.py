"""pydantic-settings 全局配置。"""

from pathlib import Path
from typing import Any, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class MemoryContextConfig(BaseSettings):
    """V3 记忆系统 - 上下文窗口配置。"""

    max_tokens: int | None = Field(
        default=None, description="上下文最大token数（None=从LLM API自动获取）"
    )
    threshold_ratio: float = Field(default=0.95, ge=0.0, le=1.0, description="触发总结的比例阈值")
    keep_recent_events: int = Field(default=20, ge=1, description="滑动窗口后保留的最近事件数")


class MemoryRetrievalConfig(BaseSettings):
    """V3 记忆系统 - 检索配置。"""

    default_max_results: int = Field(default=5, ge=1, description="默认返回的最大结果数")
    cross_session_enabled: bool = Field(default=True, description="是否启用跨会话检索")
    entity_match_weights: dict[str, float] = Field(
        default={"action": 0.4, "target": 0.3, "time": 0.2}, description="实体匹配权重"
    )


class MemoryConfig(BaseSettings):
    """V3 记忆系统配置。"""

    enabled: bool = Field(default=True, description="记忆系统开关")
    context: MemoryContextConfig = Field(default_factory=MemoryContextConfig)
    retrieval: MemoryRetrievalConfig = Field(default_factory=MemoryRetrievalConfig)
    memory_dir: str = Field(default="data/memory", description="记忆存储根目录")


class LoggingConfig(BaseSettings):
    """日志配置。"""

    log_level: str = Field(default="INFO", description="日志级别")
    log_json_format: bool = Field(default=False, description="是否使用 JSON 格式输出日志")
    llm_audit_enabled: bool = Field(default=False, description="是否启用 LLM 调用审计")
    llm_audit_dir: str = Field(default="data/audit/llm", description="LLM 审计日志目录")


class TelegramConfig(BaseSettings):
    """Telegram Bot 配置。"""

    bot_token: str = Field(default="", description="Telegram Bot Token")
    mode: Literal["polling", "webhook"] = Field(default="polling", description="运行模式")
    session_timeout_hours: int = Field(default=24, ge=1, description="会话超时时间（小时）")
    response_timeout_seconds: int = Field(default=30, ge=5, description="响应超时时间（秒）")
    max_sessions: int = Field(default=100, ge=1, description="最大会话数")
    enabled_commands: list[str] = Field(
        default=["start", "help", "agents", "stat", "end_turn"], description="启用的命令列表"
    )


class AgentConfig(BaseSettings):
    """Agent 子系统配置。"""

    max_concurrent_llm_calls: int = Field(default=5, ge=1, description="并发 LLM 请求数上限")
    enable_execution_validation: bool = Field(
        default=False, description="是否启用 LLM 二次校验（调试用，默认关闭）"
    )


class LLMConfig(BaseSettings):
    """LLM Provider 配置。"""

    provider: Literal["mock", "anthropic", "openai"] = Field(
        default="mock", description="LLM 提供商: mock/anthropic/openai"
    )
    api_key: str | None = Field(default=None, description="API Key")
    api_base: str | None = Field(
        default=None, description="API Base URL（用于兼容 OpenAI 格式的服务，如 DeepSeek、智谱等）"
    )
    model: str | None = Field(default=None, description="模型名称（可选，使用默认值）")

    # 默认模型
    _DEFAULT_MODELS = {
        "anthropic": "claude-sonnet-4-20250514",
        "openai": "gpt-4o",
    }

    def get_model(self) -> str:
        """获取模型名称，未指定时返回默认值。"""
        if self.model:
            return self.model
        return self._DEFAULT_MODELS.get(self.provider, "unknown")


class GameConfig(BaseSettings):
    """游戏全局配置。"""

    model_config = SettingsConfigDict(
        env_prefix="SIMU_",
        env_nested_delimiter="__",
    )

    db_path: str = Field(default="game.db", description="SQLite 数据库路径")
    data_dir: Path = Field(default=Path("data"), description="数据根目录")
    log_dir: Path = Field(default=Path("data/logs"), description="日志根目录")
    seed: int | None = Field(default=None, description="随机种子（None 为随机）")
    max_random_events_per_turn: int = Field(default=2, ge=0, description="每回合最大随机事件数")
    log_sensitive_data: bool = Field(default=False, description="敏感数据脱敏开关")
    agent: AgentConfig = Field(default_factory=AgentConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """自定义配置源：支持 YAML 配置文件 + 环境变量。"""
        # 尝试加载 YAML 配置文件
        yaml_settings = _YamlSettingsSource(settings_cls, "config.yaml")

        # 优先级: init > env > yaml > dotenv > secrets
        return (
            init_settings,
            env_settings,
            yaml_settings,
            dotenv_settings,
            file_secret_settings,
        )


class _YamlSettingsSource(PydanticBaseSettingsSource):
    """YAML 配置文件源。"""

    def __init__(self, settings_cls: type[BaseSettings], yaml_file: str):
        super().__init__(settings_cls)
        self.yaml_file = Path(yaml_file)
        self._data: dict[str, Any] | None = None

    def _load_yaml(self) -> dict[str, Any]:
        if self._data is not None:
            return self._data

        if not self.yaml_file.exists():
            self._data = {}
            return self._data

        try:
            import yaml
        except ImportError:
            print(f"警告: 未安装 pyyaml，无法读取 {self.yaml_file}")
            self._data = {}
            return self._data

        with open(self.yaml_file, encoding="utf-8") as f:
            self._data = yaml.safe_load(f) or {}
        return self._data

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        data = self._load_yaml()
        if field_name in data:
            return data[field_name], field_name, False
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._load_yaml()


# 全局配置实例
settings = GameConfig()
