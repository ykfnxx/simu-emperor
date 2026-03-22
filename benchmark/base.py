"""BaseEvaluator — shared base class for all benchmark evaluators."""

from __future__ import annotations

import asyncio
from typing import ClassVar

from benchmark.config import BenchmarkConfig
from benchmark.context import BenchmarkContext


class BaseEvaluator:
    """Base evaluator that lazily initialises a shared BenchmarkContext."""

    _context: ClassVar[BenchmarkContext | None] = None
    _context_lock: ClassVar[asyncio.Lock | None] = None

    def __init__(self, config: BenchmarkConfig | None = None):
        self.config = config or BenchmarkConfig.load()

    @classmethod
    async def get_context(cls, config: BenchmarkConfig) -> BenchmarkContext:
        """Return (and lazily create) the shared BenchmarkContext.

        Always stored on BaseEvaluator so all subclasses share one instance.
        """
        if BaseEvaluator._context_lock is None:
            BaseEvaluator._context_lock = asyncio.Lock()

        async with BaseEvaluator._context_lock:
            if BaseEvaluator._context is None:
                ctx = BenchmarkContext()
                await ctx.initialize(config)
                BaseEvaluator._context = ctx
        return BaseEvaluator._context

    @classmethod
    async def cleanup(cls) -> None:
        """Shutdown the shared context (call once at end of run)."""
        if BaseEvaluator._context is not None:
            await BaseEvaluator._context.shutdown()
            BaseEvaluator._context = None
