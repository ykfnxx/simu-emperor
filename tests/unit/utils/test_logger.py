"""日志系统单元测试。"""

import logging
from pathlib import Path

import pytest

from simu_emperor.config import GameConfig
from simu_emperor.utils import logger as logger_module
from simu_emperor.utils.logger import (
    get_event_logger,
    get_llm_logger,
    log_event,
    log_llm_request,
    log_llm_response,
    setup_logging,
)


@pytest.fixture
def temp_log_dir(self, tmp_path: Path):
    """创建临时日志目录。"""
    log_dir = tmp_path / "log"
    log_dir.mkdir()
    return log_dir


@pytest.fixture
def config_with_log_dir(self, tmp_path: Path):
    """创建带临时日志目录的配置。"""
    return GameConfig(data_dir=tmp_path)


class TestSetupLogging:
    """测试 setup_logging 函数。"""

    def test_creates_log_directory(self, tmp_path: Path):
        """测试日志目录创建。"""
        config = GameConfig(data_dir=tmp_path)
        setup_logging(config)

        log_dir = tmp_path / "log"
        assert log_dir.exists()
        assert log_dir.is_dir()

    def test_creates_llm_logger(self, tmp_path: Path):
        """测试 LLM 日志器创建。"""
        config = GameConfig(data_dir=tmp_path)
        setup_logging(config)

        llm_logger = get_llm_logger()
        assert llm_logger is not None
        assert llm_logger.name == logger_module.LLM_LOGGER_NAME
        assert len(llm_logger.handlers) > 0

    def test_creates_event_logger(self, tmp_path: Path):
        """测试 Event 日志器创建。"""
        config = GameConfig(data_dir=tmp_path)
        setup_logging(config)

        event_logger = get_event_logger()
        assert event_logger is not None
        assert event_logger.name == logger_module.EVENT_LOGGER_NAME
        assert len(event_logger.handlers) > 0

    def test_log_rotation_configured(self, tmp_path: Path):
        """测试日志轮转配置。"""
        config = GameConfig(data_dir=tmp_path)
        setup_logging(config)

        llm_logger = get_llm_logger()
        handler = llm_logger.handlers[0]
        assert isinstance(handler, logging.handlers.RotatingFileHandler)
        assert handler.maxBytes == 10 * 1024 * 1024  # 10MB
        assert handler.backupCount == 5


class TestLogLlmRequest:
    """测试 log_llm_request 函数。"""

    def test_logs_request_basic(self, tmp_path: Path, caplog):
        """测试基本请求日志。"""
        config = GameConfig(data_dir=tmp_path)
        setup_logging(config)

        with caplog.at_level(logging.INFO, logger=logger_module.LLM_LOGGER_NAME):
            log_llm_request(
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                messages=[{"role": "user", "content": "test"}],
            )

        assert "REQUEST" in caplog.text
        assert "provider=anthropic" in caplog.text
        assert "model=claude-sonnet-4-20250514" in caplog.text
        assert "messages=1" in caplog.text

    def test_logs_request_with_agent_id(self, tmp_path: Path, caplog):
        """测试带 agent_id 的请求日志。"""
        config = GameConfig(data_dir=tmp_path)
        setup_logging(config)

        with caplog.at_level(logging.INFO, logger=logger_module.LLM_LOGGER_NAME):
            log_llm_request(
                provider="mock",
                model="mock-model",
                messages=[],
                agent_id="governor_zhili",
            )

        assert "agent=governor_zhili" in caplog.text

    def test_returns_timestamp(self, tmp_path: Path):
        """测试返回时间戳。"""
        config = GameConfig(data_dir=tmp_path)
        setup_logging(config)

        start_time = log_llm_request(
            provider="mock",
            model="mock-model",
            messages=[],
        )
        assert isinstance(start_time, float)
        assert start_time > 0


class TestLogLlmResponse:
    """测试 log_llm_response 函数。"""

    def test_logs_response_basic(self, tmp_path: Path, caplog):
        """测试基本响应日志。"""
        config = GameConfig(data_dir=tmp_path)
        setup_logging(config)

        with caplog.at_level(logging.INFO, logger=logger_module.LLM_LOGGER_NAME):
            log_llm_response(
                provider="anthropic",
                tokens=100,
                latency_ms=150.5,
            )

        assert "RESPONSE" in caplog.text
        assert "provider=anthropic" in caplog.text
        assert "tokens=100" in caplog.text
        assert "latency_ms=150" in caplog.text  # :.0f 格式化

    def test_logs_response_with_agent_id(self, tmp_path: Path, caplog):
        """测试带 agent_id 的响应日志。"""
        config = GameConfig(data_dir=tmp_path)
        setup_logging(config)

        with caplog.at_level(logging.INFO, logger=logger_module.LLM_LOGGER_NAME):
            log_llm_response(
                provider="mock",
                tokens=50,
                latency_ms=10.0,
                agent_id="minister_of_revenue",
            )

        assert "agent=minister_of_revenue" in caplog.text


class TestLogEvent:
    """测试 log_event 函数。"""

    def test_logs_player_event(self, tmp_path: Path, caplog):
        """测试 PlayerEvent 日志。"""
        config = GameConfig(data_dir=tmp_path)
        setup_logging(config)

        from simu_emperor.engine.models.effects import EventEffect
        from simu_emperor.engine.models.events import PlayerEvent

        event = PlayerEvent(
            event_id="evt_001",
            turn_created=1,
            command_type="tax_adjustment",
            description="调整税率",
            effects=[EventEffect(target="taxation.tax_rate", operation="add", value=0.1)],
        )

        with caplog.at_level(logging.INFO, logger=logger_module.EVENT_LOGGER_NAME):
            log_event(event, action="applied")

        assert "EVENT" in caplog.text
        assert "action=applied" in caplog.text
        assert "type=PlayerEvent" in caplog.text
        assert "id=evt_001" in caplog.text
        assert "effects=1" in caplog.text

    def test_logs_agent_event(self, tmp_path: Path, caplog):
        """测试 AgentEvent 日志。"""
        config = GameConfig(data_dir=tmp_path)
        setup_logging(config)

        from decimal import Decimal

        from simu_emperor.engine.models.events import AgentEvent

        event = AgentEvent(
            event_id="evt_002",
            turn_created=1,
            agent_id="governor_zhili",
            agent_event_type="tax_collection",
            description="征收商税",
            fidelity=Decimal("0.9"),
        )

        with caplog.at_level(logging.INFO, logger=logger_module.EVENT_LOGGER_NAME):
            log_event(event, action="generated")

        assert "EVENT" in caplog.text
        assert "action=generated" in caplog.text
        assert "agent=governor_zhili" in caplog.text

    def test_logs_event_without_effects(self, tmp_path: Path, caplog):
        """测试无 effects 属性的事件日志。"""
        config = GameConfig(data_dir=tmp_path)
        setup_logging(config)

        # 创建一个没有 effects 属性的简单对象
        class SimpleEvent:
            pass

        event = SimpleEvent()

        with caplog.at_level(logging.INFO, logger=logger_module.EVENT_LOGGER_NAME):
            log_event(event, action="test")

        assert "EVENT" in caplog.text
        assert "effects=0" in caplog.text
