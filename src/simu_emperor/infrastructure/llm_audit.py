"""LLM 调用审计日志。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles
import structlog


@dataclass
class LLMAuditRecord:
    """LLM 调用审计记录。"""

    timestamp: datetime
    game_id: str
    turn: int
    agent_id: str
    phase: str  # summarize / respond / execute
    provider: str
    model: str
    system_prompt: str
    user_prompt: str
    response: str | dict[str, Any]  # dict for structured output
    duration_ms: float
    tokens_prompt: int | None = None
    tokens_completion: int | None = None
    success: bool = True
    error: str | None = None


@dataclass
class LLMAuditLogger:
    """LLM 调用审计日志器（按游戏 ID 分目录存储）。"""

    audit_dir: Path

    def __post_init__(self) -> None:
        self._logger = structlog.get_logger(__name__)

    async def log(self, record: LLMAuditRecord) -> Path | None:
        """记录 LLM 调用到 JSON 文件。

        文件路径: {audit_dir}/{game_id}/turn{NNN}_{agent_id}_{phase}_{timestamp}.json

        失败时降级到主日志，不抛出异常。

        Args:
            record: 审计记录

        Returns:
            写入的文件路径，失败时返回 None
        """
        try:
            # 按游戏 ID 分目录
            game_dir = self.audit_dir / record.game_id
            game_dir.mkdir(parents=True, exist_ok=True)

            timestamp_str = record.timestamp.strftime("%Y%m%d_%H%M%S_%f")
            filename = (
                f"turn{record.turn:03d}_"
                f"{record.agent_id}_{record.phase}_{timestamp_str}.json"
            )
            filepath = game_dir / filename

            data = {
                "version": 1,
                "timestamp": record.timestamp.isoformat(),
                "game_id": record.game_id,
                "turn": record.turn,
                "agent_id": record.agent_id,
                "phase": record.phase,
                "provider": record.provider,
                "model": record.model,
                "duration_ms": round(record.duration_ms, 2),
                "tokens": {
                    "prompt": record.tokens_prompt,
                    "completion": record.tokens_completion,
                    "total": (
                        record.tokens_prompt + record.tokens_completion
                        if record.tokens_prompt is not None and record.tokens_completion is not None
                        else None
                    ),
                },
                "success": record.success,
                "error": record.error,
                "request": {
                    "system": record.system_prompt,
                    "user": record.user_prompt,
                },
                "response": record.response,
            }

            async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))

            return filepath

        except Exception as e:
            # 降级：记录到主日志
            self._logger.error(
                "llm_audit_write_failed",
                error=str(e),
                game_id=record.game_id,
                turn=record.turn,
                agent_id=record.agent_id,
            )
            return None

    def list_audit_files(
        self,
        game_id: str | None = None,
        turn: int | None = None,
        agent_id: str | None = None,
    ) -> list[Path]:
        """列出审计文件（支持过滤）。

        Args:
            game_id: 按游戏 ID 过滤
            turn: 按回合数过滤
            agent_id: 按 Agent ID 过滤

        Returns:
            匹配的文件路径列表
        """
        if game_id:
            search_dir = self.audit_dir / game_id
            if not search_dir.exists():
                return []
            files = sorted(search_dir.glob("*.json"))
        else:
            files = sorted(self.audit_dir.rglob("*.json"))

        if turn is not None:
            files = [f for f in files if f"turn{turn:03d}" in f.name]
        if agent_id:
            files = [f for f in files if agent_id in f.name]

        return files
