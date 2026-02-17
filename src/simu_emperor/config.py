"""pydantic-settings 全局配置。"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class AgentConfig(BaseSettings):
    """Agent 子系统配置。"""

    max_concurrent_llm_calls: int = Field(default=5, ge=1, description="并发 LLM 请求数上限")
    enable_execution_validation: bool = Field(
        default=False, description="是否启用 LLM 二次校验（调试用，默认关闭）"
    )


class GameConfig(BaseSettings):
    """游戏全局配置。"""

    model_config = {"env_prefix": "SIMU_", "env_nested_delimiter": "__"}

    db_path: str = Field(default="game.db", description="SQLite 数据库路径")
    data_dir: Path = Field(default=Path("data"), description="数据根目录")
    seed: int | None = Field(default=None, description="随机种子（None 为随机）")
    max_random_events_per_turn: int = Field(default=2, ge=0, description="每回合最大随机事件数")
    agent: AgentConfig = Field(default_factory=AgentConfig)
