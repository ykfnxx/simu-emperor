"""LLM 调用封装：统一入口，预留重试/日志/限流扩展点。"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel

from simu_emperor.agents.context_builder import AgentContext
from simu_emperor.agents.llm.providers import LLMProvider
from simu_emperor.infrastructure.logging import get_logger

if TYPE_CHECKING:
    from simu_emperor.infrastructure.llm_audit import LLMAuditLogger

T = TypeVar("T", bound=BaseModel)

logger = get_logger(__name__)


class LLMClient:
    """LLM 调用客户端，委托给具体 Provider。"""

    def __init__(
        self,
        provider: LLMProvider,
        audit_logger: LLMAuditLogger | None = None,
        game_id_getter: callable | None = None,
        turn_getter: callable | None = None,
    ) -> None:
        self.provider = provider
        self._audit_logger = audit_logger
        self._game_id_getter = game_id_getter
        self._turn_getter = turn_getter

    async def generate(self, context: AgentContext) -> str:
        """调用 LLM 生成文本。"""
        start_time = time.time()
        provider_name = type(self.provider).__name__
        model = getattr(self.provider, "model", "unknown")

        logger.info(
            "llm_call_started",
            provider=provider_name,
            model=model,
            agent_id=context.agent_id,
            call_type="generate",
        )

        try:
            response = await self.provider.generate(context)
            duration_ms = (time.time() - start_time) * 1000

            logger.info(
                "llm_call_completed",
                provider=provider_name,
                model=model,
                agent_id=context.agent_id,
                duration_ms=round(duration_ms, 2),
                response_length=len(response),
            )

            # 审计日志
            if self._audit_logger:
                await self._write_audit_log(
                    context=context,
                    response=response,
                    duration_ms=duration_ms,
                    phase="generate",
                )

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "llm_call_failed",
                provider=provider_name,
                model=model,
                agent_id=context.agent_id,
                duration_ms=round(duration_ms, 2),
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    async def generate_stream(self, context: AgentContext) -> AsyncIterator[str]:
        """流式调用 LLM 生成文本。"""
        start_time = time.time()
        provider_name = type(self.provider).__name__
        model = getattr(self.provider, "model", "unknown")
        chunk_count = 0
        total_chars = 0

        logger.info(
            "llm_stream_started",
            provider=provider_name,
            model=model,
            agent_id=context.agent_id,
        )

        try:
            response_chunks = []
            async for chunk in self.provider.generate_stream(context):
                chunk_count += 1
                total_chars += len(chunk)
                response_chunks.append(chunk)
                yield chunk

            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "llm_stream_completed",
                provider=provider_name,
                model=model,
                agent_id=context.agent_id,
                duration_ms=round(duration_ms, 2),
                chunk_count=chunk_count,
                total_chars=total_chars,
            )

            # 审计日志
            if self._audit_logger:
                await self._write_audit_log(
                    context=context,
                    response="".join(response_chunks),
                    duration_ms=duration_ms,
                    phase="stream",
                )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "llm_stream_failed",
                provider=provider_name,
                model=model,
                agent_id=context.agent_id,
                duration_ms=round(duration_ms, 2),
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    async def generate_structured(self, context: AgentContext, response_model: type[T]) -> T:
        """调用 LLM 生成结构化输出。"""
        start_time = time.time()
        provider_name = type(self.provider).__name__
        model = getattr(self.provider, "model", "unknown")

        logger.info(
            "llm_structured_started",
            provider=provider_name,
            model=model,
            agent_id=context.agent_id,
            response_model=response_model.__name__,
        )

        try:
            response = await self.provider.generate_structured(context, response_model)
            duration_ms = (time.time() - start_time) * 1000

            logger.info(
                "llm_structured_completed",
                provider=provider_name,
                model=model,
                agent_id=context.agent_id,
                duration_ms=round(duration_ms, 2),
                response_model=response_model.__name__,
            )

            # 审计日志
            if self._audit_logger:
                await self._write_audit_log(
                    context=context,
                    response=response.model_dump(),
                    duration_ms=duration_ms,
                    phase="structured",
                )

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "llm_structured_failed",
                provider=provider_name,
                model=model,
                agent_id=context.agent_id,
                duration_ms=round(duration_ms, 2),
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    async def _write_audit_log(
        self,
        context: AgentContext,
        response: str | dict,
        duration_ms: float,
        phase: str,
    ) -> None:
        """写入 LLM 审计日志。"""
        from datetime import datetime

        from simu_emperor.infrastructure.llm_audit import LLMAuditRecord

        if not self._audit_logger:
            return

        game_id = self._game_id_getter() if self._game_id_getter else "unknown"
        turn = self._turn_getter() if self._turn_getter else 0

        record = LLMAuditRecord(
            timestamp=datetime.now(),
            game_id=game_id,
            turn=turn,
            agent_id=context.agent_id,
            phase=phase,
            provider=type(self.provider).__name__,
            model=getattr(self.provider, "model", "unknown"),
            system_prompt=context.soul,
            user_prompt=context.skill + "\n" + context.data,
            response=response,
            duration_ms=duration_ms,
        )

        await self._audit_logger.log(record)
