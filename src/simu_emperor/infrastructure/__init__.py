"""基础设施模块：日志、审计、指标等。"""

from simu_emperor.infrastructure.logging import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
    log_context,
    unbind_context,
)
from simu_emperor.infrastructure.llm_audit import LLMAuditLogger, LLMAuditRecord
from simu_emperor.infrastructure.metrics import (
    record_llm_call,
    set_game_turn,
)

__all__ = [
    # logging
    "configure_logging",
    "get_logger",
    "bind_context",
    "unbind_context",
    "clear_context",
    "log_context",
    # llm_audit
    "LLMAuditLogger",
    "LLMAuditRecord",
    # metrics
    "record_llm_call",
    "set_game_turn",
]
