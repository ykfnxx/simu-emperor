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


class AgentConfig(BaseSettings):
    """Agent 子系统配置。"""

    max_concurrent_llm_calls: int = Field(default=5, ge=1, description="并发 LLM 请求数上限")
    enable_execution_validation: bool = Field(
        default=False, description="是否启用 LLM 二次校验（调试用，默认关闭）"
    )


class AutonomousMemoryConfig(BaseSettings):
    """Agent 自主记忆配置。"""

    enabled: bool = Field(default=True, description="是否启用自主记忆反思")
    check_interval_ticks: int = Field(
        default=4, ge=1, description="每隔多少 tick 反思一次（4=每月）"
    )
    soul_evolution_enabled: bool = Field(default=True, description="是否允许 soul.md 性格演化")


class IncidentConfig(BaseSettings):
    """Incident 子系统配置。"""

    enabled: bool = Field(default=True, description="是否启用随机事件生成")
    check_interval_ticks: int = Field(
        default=4, ge=1, description="每隔多少 tick 检查一次随机事件（4=每月）"
    )
    base_trigger_probability: float = Field(default=0.1, ge=0.0, le=1.0, description="基础触发概率")
    max_active_system_incidents: int = Field(
        default=5, ge=1, description="系统生成的最大活跃 incident 数"
    )
    llm_beautify_enabled: bool = Field(default=True, description="是否启用 LLM 叙事美化")


class LLMTaskConfig(BaseSettings):
    """单个任务的 LLM 配置（V4.3）"""

    model: str | None = Field(default=None, description="模型名称")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0, description="温度参数")
    max_tokens: int | None = Field(default=None, ge=1, description="最大生成 token 数")


class LLMConfig(BaseSettings):
    """LLM Provider 配置（V4.3 两层配置）"""

    model_config = SettingsConfigDict(extra="ignore")

    provider: Literal["mock", "anthropic", "openai"] = Field(
        default="mock", description="LLM 提供商: mock/anthropic/openai"
    )
    api_key: str | None = Field(default=None, description="API Key")
    api_base: str | None = Field(
        default=None, description="API Base URL（用于兼容 OpenAI 格式的服务，如 DeepSeek、智谱等）"
    )
    context_window: int | None = Field(
        default=128000, description="LLM 上下文窗口大小（token 数），用于调试和测试"
    )

    # 默认配置
    default: LLMTaskConfig = Field(
        default_factory=lambda: LLMTaskConfig(
            model="claude-sonnet-4-20250514", temperature=0.7, max_tokens=2000
        )
    )

    # 任务特定配置
    task_configs: dict[str, LLMTaskConfig] = Field(default_factory=dict)

    # 默认模型
    _DEFAULT_MODELS = {
        "anthropic": "claude-sonnet-4-20250514",
        "openai": "gpt-4o",
    }

    def get_task_config(self, task_type: str) -> LLMTaskConfig:
        """获取任务配置，未配置则返回 default"""
        return self.task_configs.get(task_type, self.default)

    def get_model(self) -> str:
        """获取默认模型名称"""
        if self.default.model:
            return self.default.model
        return self._DEFAULT_MODELS.get(self.provider, "unknown")


class EmbeddingConfig(BaseSettings):
    """向量检索 Embedding 配置（V4.2 增强）。"""

    provider: Literal["openai", "mock"] = Field(
        default="openai", description="Embedding 提供商: openai/mock"
    )
    api_key: str | None = Field(default=None, description="OpenAI API Key")
    api_base: str | None = Field(default=None, description="API Base URL（兼容 OpenAI 格式的服务）")
    model: str = Field(default="text-embedding-3-small", description="Embedding 模型")
    enabled: bool = Field(default=True, description="是否启用向量检索")
    batch_size: int = Field(default=100, ge=1, description="批量 embedding 大小")
    dimensions: int = Field(default=1536, ge=1, description="向量维度")
    timeout: int = Field(default=30, ge=1, description="API 超时（秒）")
    max_retries: int = Field(default=3, ge=0, description="失败重试次数")
    retry_delay: float = Field(default=1.0, ge=0.0, description="重试延迟（秒），指数退避")


class ChromaDBConfig(BaseSettings):
    """ChromaDB 向量数据库配置（V4.2 新增）。"""

    enabled: bool = Field(default=True, description="是否启用 ChromaDB")
    persist_directory: str = Field(default="data/chroma", description="持久化目录")
    collection_name: str = Field(default="memory_segments", description="集合名称")
    distance_metric: Literal["cosine", "l2", "ip"] = Field(default="cosine", description="距离度量")


class DebugConfig(BaseSettings):
    """调试配置（V4.2 新增）。"""

    enable_jsonl: bool = Field(default=True, description="同时写入 tape.jsonl（调试用）")


class AgentQueueConfig(BaseSettings):
    """Agent 事件队列配置（V4.2 新增）。"""

    enabled: bool = Field(default=True, description="是否启用消息队列（背压处理）")
    max_size: int = Field(default=0, ge=0, description="队列最大容量（0 = 无界）")


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
    autonomous_memory: AutonomousMemoryConfig = Field(default_factory=AutonomousMemoryConfig)
    incident: IncidentConfig = Field(default_factory=IncidentConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    chromadb: ChromaDBConfig = Field(default_factory=ChromaDBConfig)
    debug: DebugConfig = Field(default_factory=DebugConfig)
    agent_queue: AgentQueueConfig = Field(default_factory=AgentQueueConfig)

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
