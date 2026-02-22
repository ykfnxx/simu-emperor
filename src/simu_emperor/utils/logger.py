"""日志系统：LLM 请求/响应日志 + Event 日志（带轮转）。"""

import logging
import time
from logging.handlers import RotatingFileHandler
from typing import Any

from simu_emperor.config import GameConfig


# 日志器名称常量
LLM_LOGGER_NAME = "simu_emperor.llm"
EVENT_LOGGER_NAME = "simu_emperor.event"

# 全局配置引用
_log_sensitive_data: bool = False


def setup_logging(config: GameConfig) -> None:
    """初始化日志系统，带轮转。

    Args:
        config: 游戏配置，包含 LOG_DIR 和 LOG_SENSITIVE_DATA
    """
    global _log_sensitive_data

    log_dir = config.data_dir / "log"
    log_dir.mkdir(parents=True, exist_ok=True)

    _log_sensitive_data = getattr(config, "log_sensitive_data", False)

    # LLM 日志 (10MB, 5 个备份)
    llm_handler = RotatingFileHandler(
        log_dir / "llm.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    llm_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    llm_logger = logging.getLogger(LLM_LOGGER_NAME)
    llm_logger.setLevel(logging.INFO)
    llm_logger.addHandler(llm_handler)

    # Event 日志 (10MB, 5 个备份)
    event_handler = RotatingFileHandler(
        log_dir / "event.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    event_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    event_logger = logging.getLogger(EVENT_LOGGER_NAME)
    event_logger.setLevel(logging.INFO)
    event_logger.addHandler(event_handler)


def get_llm_logger() -> logging.Logger:
    """获取 LLM 日志器。"""
    return logging.getLogger(LLM_LOGGER_NAME)


def get_event_logger() -> logging.Logger:
    """获取 Event 日志器。"""
    return logging.getLogger(EVENT_LOGGER_NAME)


def log_llm_request(
    provider: str,
    model: str,
    messages: list[Any],
    agent_id: str | None = None,
    **kwargs: Any,
) -> float:
    """记录 LLM 请求。

    Args:
        provider: LLM 提供商名称
        model: 模型名称
        messages: 消息列表
        agent_id: Agent ID（可选）
        **kwargs: 其他元数据

    Returns:
        请求开始时间戳（用于计算延迟）
    """
    logger = get_llm_logger()
    # 敏感信息处理：只记录消息数量，不记录内容
    msg_count = len(messages) if messages else 0
    agent_str = f"agent={agent_id} | " if agent_id else ""
    logger.info(f"REQUEST | {agent_str}provider={provider} | model={model} | messages={msg_count}")
    return time.time()


def log_llm_response(
    provider: str,
    tokens: int,
    latency_ms: float,
    agent_id: str | None = None,
    **kwargs: Any,
) -> None:
    """记录 LLM 响应。

    Args:
        provider: LLM 提供商名称
        tokens: 使用的 token 数量
        latency_ms: 延迟（毫秒）
        agent_id: Agent ID（可选）
        **kwargs: 其他元数据
    """
    logger = get_llm_logger()
    agent_str = f"agent={agent_id} | " if agent_id else ""
    logger.info(f"RESPONSE | {agent_str}provider={provider} | tokens={tokens} | latency_ms={latency_ms:.0f}")


def log_event(event: Any, action: str = "applied") -> None:
    """记录游戏事件。

    Args:
        event: 游戏事件对象
        action: 事件动作（applied/generated）
    """
    logger = get_event_logger()
    event_type = type(event).__name__
    agent_id = getattr(event, "agent_id", "N/A")
    effects_count = len(event.effects) if hasattr(event, "effects") else 0
    event_id = getattr(event, "event_id", "N/A")
    logger.info(
        f"EVENT | action={action} | type={event_type} | id={event_id} | agent={agent_id} | effects={effects_count}"
    )
