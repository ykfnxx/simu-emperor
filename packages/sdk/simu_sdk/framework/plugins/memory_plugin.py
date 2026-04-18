"""SimuMemoryPlugin — vector retrieval and memory management."""

from __future__ import annotations

import logging
from typing import Any

from bub.hookspecs import hookimpl
from simu_sdk.memory.retriever import MemoryRetriever

logger = logging.getLogger(__name__)


class SimuMemoryPlugin:
    """Retrieves relevant memories during load_state.

    Memory stays agent-local (not MCP-ified) — ChromaDB vector search
    and tape metadata are managed within the agent process.
    """

    def __init__(self, retriever: MemoryRetriever) -> None:
        self._retriever = retriever

    @hookimpl
    async def load_state(self, message: Any, session_id: str) -> dict:
        """Retrieve relevant memories for the current event."""
        content = ""
        if hasattr(message, "payload") and isinstance(message.payload, dict):
            content = message.payload.get("content", "")

        if not content:
            return {}

        try:
            memories = await self._retriever.search(content, max_results=5)
            return {"relevant_memories": memories}
        except Exception:
            logger.warning("Memory retrieval failed", exc_info=True)
            return {}
