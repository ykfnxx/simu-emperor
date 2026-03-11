"""StructuredRetriever for coordinating memory retrieval (V4)."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simu_emperor.memory.context_manager import ContextManager
    from simu_emperor.memory.two_level_searcher import TwoLevelSearcher

from simu_emperor.memory.models import RetrievalResult
from simu_emperor.memory.query_parser import QueryParser


class StructuredRetriever:
    """
    Coordinates memory retrieval across multiple sources (V4).

    Routes queries based on scope (current_session vs cross_session)
    and depth (overview vs tape).

    V4: Uses TwoLevelSearcher for cross-session retrieval.
    """

    def __init__(
        self,
        memory_dir: Path,
        query_parser: QueryParser,
        two_level_searcher: "TwoLevelSearcher",
    ):
        """
        Initialize StructuredRetriever.

        Args:
            memory_dir: Base memory directory path
            query_parser: QueryParser instance
            two_level_searcher: TwoLevelSearcher instance (V4)
        """
        self.memory_dir = memory_dir
        self.parser = query_parser
        self.two_level_searcher = two_level_searcher

    async def retrieve(
        self,
        raw_query: str,
        agent_id: str,
        current_session_id: str,
        context_manager: "ContextManager" = None,
        max_results: int = 5,
    ) -> RetrievalResult:
        """
        Main retrieval entry point.

        Args:
            raw_query: Natural language query
            agent_id: Agent identifier
            current_session_id: Current session ID
            context_manager: Optional ContextManager for current_session scope
            max_results: Maximum results to return

        Returns:
            RetrievalResult with formatted results
        """
        # Step 1: Parse query
        parse_result = await self.parser.parse(raw_query)
        structured = parse_result.structured

        results = []
        sessions_searched = None

        # Step 2: Route based on scope
        if structured.scope == "current_session":
            results = await self._retrieve_current_session(context_manager, structured)

        elif structured.scope == "cross_session":
            results, sessions_searched = await self._retrieve_cross_session(
                agent_id, structured, current_session_id, max_results
            )

        # Step 3: Filter based on depth
        if structured.depth == "overview":
            # Return summaries only
            results = self._format_overview_results(results)
        else:  # depth == "tape"
            # Return full event details
            results = self._format_tape_results(results)

        return RetrievalResult(
            query=raw_query,
            scope=structured.scope,
            depth=structured.depth,
            results=results,
            sessions_searched=sessions_searched,
        )

    async def _retrieve_current_session(
        self, context_manager: "ContextManager", structured_query
    ) -> list[dict]:
        """
        Retrieve from current session via ContextManager.

        Args:
            context_manager: ContextManager instance
            structured_query: Parsed query

        Returns:
            List of event dicts
        """
        if not context_manager:
            return []

        messages = context_manager.get_context_messages()

        # Convert messages to result format
        results = []
        for msg in messages:
            results.append({"role": msg["role"], "content": msg["content"]})

        return results

    async def _retrieve_cross_session(
        self,
        agent_id: str,
        query,  # StructuredQuery
        exclude_session: str,
        max_results: int,
    ) -> tuple[list[dict], list[str]]:
        """
        Retrieve across sessions via TwoLevelSearcher (V4).

        Args:
            agent_id: Agent identifier
            query: StructuredQuery from QueryParser
            exclude_session: Session ID to exclude (current session)
            max_results: Max results

        Returns:
            Tuple of (results list, session_ids searched)

        V4: Uses TwoLevelSearcher for two-level search
        """
        # Use two-level search
        segments = await self.two_level_searcher.search(
            query=query,
            agent_id=agent_id,
            exclude_session=exclude_session,
            max_results=max_results,
        )

        # Extract unique session IDs
        session_ids = list(set(s.session_id for s in segments))

        # Convert TapeSegments to result dicts
        results = [s.to_dict() for s in segments]

        return results, session_ids

    def _format_overview_results(self, results: list[dict]) -> list[dict]:
        """
        Format results for overview depth.

        Args:
            results: Raw results

        Returns:
            Formatted overview results
        """
        # For tape segments, show segment-level summary
        formatted = []
        for result in results:
            # Check if this is a TapeSegment result
            if "events" in result and result["events"]:
                # Extract summary from first event or segment-level metadata
                formatted.append(
                    {
                        "type": "segment_summary",
                        "session_id": result.get("session_id"),
                        "tick_start": result.get("tick_start"),
                        "tick_end": result.get("tick_end"),
                        "event_count": result.get("event_count"),
                        "relevance_score": result.get("relevance_score", 0),
                    }
                )
            else:
                formatted.append(result)
        return formatted

    def _format_tape_results(self, results: list[dict]) -> list[dict]:
        """
        Format results for tape depth (V4: handles TapeSegment format).

        Args:
            results: Raw results (TapeSegment dicts)

        Returns:
            Formatted tape results with event details
        """
        formatted = []
        for result in results:
            # Check if this is a TapeSegment result
            if "events" in result:
                # Format as segment with events
                formatted.append(
                    {
                        "type": "segment",
                        "session_id": result.get("session_id"),
                        "agent_id": result.get("agent_id"),
                        "start_position": result.get("start_position"),
                        "end_position": result.get("end_position"),
                        "event_count": result.get("event_count"),
                        "tick_start": result.get("tick_start"),
                        "tick_end": result.get("tick_end"),
                        "timestamp_start": result.get("timestamp_start"),
                        "timestamp_end": result.get("timestamp_end"),
                        "relevance_score": result.get("relevance_score", 0),
                        # Include condensed event info
                        "event_summary": self._summarize_segment_events(result.get("events", [])),
                    }
                )
            else:
                # Legacy format
                formatted.append(
                    {
                        "type": "event",
                        "event_id": result.get("event_id"),
                        "event_type": result.get("event_type"),
                        "content": result.get("content"),
                        "timestamp": result.get("timestamp"),
                        "session_id": result.get("session_id"),
                        "relevance_score": result.get("relevance_score", 0),
                    }
                )
        return formatted

    def _summarize_segment_events(self, events: list[dict]) -> str:
        """
        Create a brief summary of segment events.

        Args:
            events: List of event dicts

        Returns:
            Summary string
        """
        if not events:
            return ""

        summaries = []
        for event in events[:5]:  # Limit to first 5 events
            event_type = event.get("type", "")
            payload = event.get("payload", {})
            if isinstance(payload, dict):
                query = payload.get("query", "")
                intent = payload.get("intent", "")
                if query:
                    summaries.append(f"{event_type}: {query[:30]}")
                elif intent:
                    summaries.append(f"{event_type}: {intent}")

        return "; ".join(summaries) + ("..." if len(events) > 5 else "")
