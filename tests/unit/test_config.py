"""GameConfig 单元测试。"""

from pathlib import Path

from simu_emperor.config import AgentConfig, GameConfig


class TestAgentConfig:
    def test_defaults(self) -> None:
        cfg = AgentConfig()
        assert cfg.max_concurrent_llm_calls == 5
        assert cfg.enable_execution_validation is False

    def test_custom_values(self) -> None:
        cfg = AgentConfig(max_concurrent_llm_calls=10, enable_execution_validation=True)
        assert cfg.max_concurrent_llm_calls == 10
        assert cfg.enable_execution_validation is True


class TestGameConfig:
    def test_defaults(self) -> None:
        cfg = GameConfig()
        assert cfg.db_path == "game.db"
        assert cfg.data_dir == Path("data")
        assert cfg.seed is None
        assert cfg.max_random_events_per_turn == 2
        assert isinstance(cfg.agent, AgentConfig)

    def test_custom_values(self) -> None:
        cfg = GameConfig(
            db_path="test.db",
            data_dir=Path("/tmp/data"),
            seed=42,
            max_random_events_per_turn=5,
            agent=AgentConfig(max_concurrent_llm_calls=3),
        )
        assert cfg.db_path == "test.db"
        assert cfg.data_dir == Path("/tmp/data")
        assert cfg.seed == 42
        assert cfg.max_random_events_per_turn == 5
        assert cfg.agent.max_concurrent_llm_calls == 3

    def test_nested_agent_config(self) -> None:
        cfg = GameConfig()
        assert cfg.agent.max_concurrent_llm_calls == 5
        assert cfg.agent.enable_execution_validation is False
