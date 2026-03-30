"""Memory tool handlers for Agent

These handlers provide memory retrieval and storage capabilities.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType

if TYPE_CHECKING:
    from simu_emperor.llm.base import LLMProvider
    from simu_emperor.memory.context_manager import ContextManager


logger = logging.getLogger(__name__)


class MemoryTools:
    """Memory tool handlers - retrieve and store memories

    This class provides memory-related tools for agents to:
    - Retrieve historical memories across sessions
    - Query past events and decisions
    - Access conversation summaries

    Memory functions:
    - retrieve_memory: Search historical memories
    """

    def __init__(
        self,
        agent_id: str,
        memory_dir: Path,
        llm_provider: "LLMProvider",
        context_manager: "ContextManager" = None,
    ):
        """
        Initialize MemoryTools.

        Args:
            agent_id: Agent unique identifier
            memory_dir: Base memory directory path
            llm_provider: LLM provider for query parsing
            context_manager: Optional ContextManager for current session
        """
        self.agent_id = agent_id
        self.memory_dir = memory_dir
        self.llm = llm_provider
        self.context_manager = context_manager

        # Lazy import to avoid circular dependencies
        # V4: Use TwoLevelSearcher instead of TapeSearcher
        from simu_emperor.memory.structured_retriever import StructuredRetriever
        from simu_emperor.memory.query_parser import QueryParser
        from simu_emperor.memory.tape_metadata_index import TapeMetadataIndex
        from simu_emperor.memory.segment_searcher import SegmentSearcher
        from simu_emperor.memory.two_level_searcher import TwoLevelSearcher
        from simu_emperor.memory.vector_searcher import VectorSearcher

        # Initialize two-level search components
        tape_metadata_index = TapeMetadataIndex(memory_dir=memory_dir)
        segment_searcher = SegmentSearcher(memory_dir=memory_dir)

        # Initialize vector searcher if enabled
        vector_searcher = None
        from simu_emperor.config import settings

        if settings.embedding.enabled:
            try:
                vector_searcher = VectorSearcher(
                    memory_dir=memory_dir,
                    config=settings.embedding,
                )
                logger.info(f"Vector search enabled for agent {agent_id}")
            except Exception as e:
                logger.warning(f"Failed to initialize vector search: {e}")

        two_level_searcher = TwoLevelSearcher(
            tape_metadata_index=tape_metadata_index,
            segment_searcher=segment_searcher,
            vector_searcher=vector_searcher,
        )

        # Initialize retriever with two-level search
        self.retriever = StructuredRetriever(
            memory_dir=memory_dir,
            query_parser=QueryParser(llm_provider=llm_provider),
            two_level_searcher=two_level_searcher,
        )

    async def retrieve_memory(self, args: dict, event: Event) -> str:
        """
        Retrieve historical memories.

        Use this tool when the player asks about historical information,
        past decisions, or previous events.

        Args:
            args: {"query": str, "max_results": int}
            event: Current event (for session_id and agent_id)

        Returns:
            Formatted retrieval results for LLM consumption

        Examples:
            - "我之前给直隶拨过款吗？"
            - "上次我们讨论了什么？"
            - "之前做过的税收政策有哪些？"
        """
        query = args.get("query", "")
        max_results = args.get("max_results", 5)

        if not query:
            return "❌ 查询不能为空"

        try:
            # Perform retrieval
            result = await self.retriever.retrieve(
                raw_query=query,
                agent_id=self.agent_id,
                current_session_id=event.session_id,
                context_manager=self.context_manager,
                max_results=max_results,
            )

            # Inject MEMORY_INJECTED event into context for LLM awareness
            if result.results and self.context_manager:
                memory_event = {
                    "type": EventType.MEMORY_INJECTED,
                    "payload": {
                        "query": query,
                        "source": "retrieve_memory",
                        "results": [
                            {
                                "summary": r.get("summary", ""),
                                "tick_range": r.get("tick_range"),
                                "entities": r.get("entities", []),
                            }
                            for r in result.results[:5]
                        ],
                    },
                }
                try:
                    await self.context_manager.add_event_and_maybe_compact(
                        memory_event, tokens=self.context_manager._calc_event_tokens(memory_event)
                    )
                except Exception as e:
                    logger.debug(f"Failed to inject MEMORY_INJECTED event: {e}")

            # Format results for LLM
            return self._format_retrieval_result(result)

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error retrieving memory: {e}")
            return f"❌ 记忆检索失败：{str(e)}"

    def _format_retrieval_result(self, result) -> str:
        """
        Format retrieval result for LLM consumption (V4: handles TapeView).

        Args:
            result: RetrievalResult from StructuredRetriever

        Returns:
            Formatted markdown string
        """
        if not result.results:
            return f"## 检索结果：{result.query}\n\n未找到相关记录。"

        lines = [
            f"## 检索结果：{result.query}",
            "",
            f"找到 {len(result.results)} 条相关记录：",
            "",
        ]

        # Group results by session
        sessions = {}
        for item in result.results:
            session_id = item.get("session_id", "unknown")
            if session_id not in sessions:
                sessions[session_id] = []
            sessions[session_id].append(item)

        # Format each session's results
        for idx, (session_id, items) in enumerate(sessions.items(), 1):
            lines.append(f"### 记录 {idx} (会话: {session_id})")

            for item in items:
                item_type = item.get("type")

                if item_type == "summary":
                    lines.append(f"**摘要**: {item.get('content', '')}")
                    if item.get("turn_start"):
                        lines.append(
                            f"- 回合范围: {item['turn_start']} - {item.get('turn_end', '?')}"
                        )
                elif item_type == "event":
                    event_type = item.get("event_type", "UNKNOWN")
                    content = item.get("content", {})
                    timestamp = item.get("timestamp", "")

                    lines.append(f"**事件**: {event_type}")
                    if timestamp:
                        lines.append(f"- 时间: {timestamp}")

                    # Format content based on type
                    if isinstance(content, dict):
                        if "query" in content:
                            lines.append(f"- 查询: {content['query']}")
                        if "response" in content:
                            lines.append(f"- 响应: {content['response']}")
                        if "tool" in content:
                            lines.append(f"- 工具: {content['tool']}")
                            if "args" in content:
                                lines.append(f"- 参数: {content['args']}")
                    else:
                        lines.append(f"- 内容: {content}")

                elif item_type == "segment_summary":
                    # V4: TapeView summary format
                    lines.append(f"**片段摘要** (相关度: {item.get('relevance_score', 0):.2f})")
                    if item.get("tick_start") is not None:
                        lines.append(
                            f"- Tick范围: {item['tick_start']} - {item.get('tick_end', '?')}"
                        )
                    lines.append(f"- 事件数: {item.get('event_count', 0)}")

                elif item_type == "segment":
                    # V4: Full TapeView format
                    lines.append(f"**事件片段** (相关度: {item.get('relevance_score', 0):.2f})")
                    lines.append(
                        f"- 位置: {item.get('start_position', '?')} - {item.get('end_position', '?')}"
                    )
                    lines.append(f"- 事件数: {item.get('event_count', 0)}")

                    if item.get("tick_start") is not None:
                        lines.append(
                            f"- Tick范围: {item['tick_start']} - {item.get('tick_end', '?')}"
                        )

                    if item.get("timestamp_start"):
                        lines.append(
                            f"- 时间: {item.get('timestamp_start', '')} - {item.get('timestamp_end', '')}"
                        )

                    # Show event summary
                    event_summary = item.get("event_summary", "")
                    if event_summary:
                        lines.append(f"- 摘要: {event_summary}")

                lines.append("")  # Blank line between items

        return "\n".join(lines)
