"""Memory tools — retrieve_memory for cross-session memory search."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simu_sdk.tools.registry import tool

if TYPE_CHECKING:
    from simu_shared.models import TapeEvent

    from simu_sdk.memory.retriever import MemoryRetriever


class MemoryTools:
    """Agent-callable memory retrieval tools."""

    def __init__(self, retriever: MemoryRetriever) -> None:
        self._retriever = retriever

    @tool(
        name="retrieve_memory",
        description=(
            "Search your past conversation memories. Returns relevant "
            "summaries from previous sessions. Use when you need to recall "
            "past decisions, commands, or events."
        ),
        parameters={
            "query": {
                "type": "string",
                "description": "What to search for, e.g. '直隶拨款', '上次税率调整'.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results to return (default: 5).",
                "default": 5,
            },
        },
        category="memory",
    )
    async def retrieve_memory(self, args: dict, event: TapeEvent) -> str:
        results = await self._retriever.search(
            query=args["query"],
            current_session_id=event.session_id,
            max_views=args.get("max_results", 5),
        )
        if not results:
            return "未找到相关记忆。"
        return self._format_results(results)

    @staticmethod
    def _format_results(results: list) -> str:
        parts = [f"找到 {len(results)} 条相关记忆：\n"]
        for i, r in enumerate(results, 1):
            title = r.session_title or r.session_id
            parts.append(f"[{i}] 会话: {title}")
            parts.append(f"    摘要: {r.view_summary}")
            parts.append("")
        return "\n".join(parts)
