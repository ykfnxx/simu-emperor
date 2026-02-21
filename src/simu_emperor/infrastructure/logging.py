"""Structlog 配置模块。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog
from structlog.types import Processor

if TYPE_CHECKING:
    from simu_emperor.config import LoggingConfig


def configure_logging(config: LoggingConfig) -> None:
    """配置结构化日志系统。

    Args:
        config: 日志配置对象
    """
    # 共享处理器：上下文合并、日志级别、时间戳
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,  # 自动注入 contextvars
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
    ]

    if config.log_json_format:
        # 生产环境：JSON 格式 + 异常字典化
        processors = shared_processors + [
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ]
    else:
        # 开发环境：彩色控制台输出
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, config.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """获取配置好的 logger。

    Args:
        name: logger 名称，通常使用 __name__

    Returns:
        配置好的 structlog logger
    """
    return structlog.get_logger(name)


def bind_context(**kwargs) -> None:
    """绑定日志上下文字段（自动传递给后续所有日志）。"""
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys) -> None:
    """解绑日志上下文字段。"""
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """清除所有日志上下文。"""
    structlog.contextvars.clear_contextvars()


@asynccontextmanager
async def log_context(**kwargs):
    """自动管理上下文绑定的上下文管理器。

    使用示例:
        async with log_context(game_id="game_001", turn=5):
            await game_loop.advance()
    """
    structlog.contextvars.bind_contextvars(**kwargs)
    try:
        yield
    finally:
        structlog.contextvars.unbind_contextvars(*kwargs.keys())
