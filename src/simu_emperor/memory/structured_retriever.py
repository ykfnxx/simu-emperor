"""StructuredRetriever for coordinating memory retrieval."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simu_emperor.memory.context_manager import ContextManager

from simu_emperor.memory.models import RetrievalResult
from simu_emperor.memory.query_parser import QueryParser
from simu_emperor.memory.manifest_index import ManifestIndex
from simu_emperor.memory.tape_searcher import TapeSearcher


class StructuredRetriever:
    """
    Coordinates memory retrieval across multiple sources.

    Routes queries based on scope (current_session vs cross_session)
    and depth (overview vs tape).
    """

    def __init__(
        self,
        memory_dir: Path,
        query_parser: QueryParser,
        manifest_index: ManifestIndex,
        tape_searcher: TapeSearcher
    ):
        """
        Initialize StructuredRetriever.

        Args:
            memory_dir: Base memory directory path
            query_parser: QueryParser instance
            manifest_index: ManifestIndex instance
            tape_searcher: TapeSearcher instance
        """
        self.memory_dir = memory_dir
        self.parser = query_parser
        self.manifest = manifest_index
        self.searcher = tape_searcher

    async def retrieve(
        self,
        raw_query: str,
        agent_id: str,
        current_session_id: str,
        context_manager: "ContextManager" = None,
        max_results: int = 5
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
            results = await self._retrieve_current_session(
                context_manager, structured
            )

        elif structured.scope == "cross_session":
            results, sessions_searched = await self._retrieve_cross_session(
                agent_id, structured.entities, current_session_id, max_results
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
            sessions_searched=sessions_searched
        )

    async def _retrieve_current_session(
        self,
        context_manager: "ContextManager",
        structured_query
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

        messages = await context_manager.get_messages()

        # Convert messages to result format
        results = []
        for msg in messages:
            results.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        return results

    async def _retrieve_cross_session(
        self,
        agent_id: str,
        entities: dict,
        exclude_session: str,
        max_results: int
    ) -> tuple[list[dict], list[str]]:
        """
        Retrieve across sessions via ManifestIndex and TapeSearcher.

        Args:
            agent_id: Agent identifier
            entities: Entity dict for matching
            exclude_session: Session ID to exclude
            max_results: Max results

        Returns:
            Tuple of (results list, session_ids searched)
        """
        # Get candidate sessions from manifest
        candidates = await self.manifest.get_candidate_sessions(
            agent_id=agent_id,
            entities=entities,
            exclude_session=exclude_session
        )

        if not candidates:
            return [], []

        # Extract session IDs
        session_ids = [c["session_id"] for c in candidates]

        # Search tapes
        results = await self.searcher.search(
            agent_id=agent_id,
            session_ids=session_ids,
            entities=entities,
            max_results=max_results
        )

        return results, session_ids

    def _format_overview_results(self, results: list[dict]) -> list[dict]:
        """
        Format results for overview depth.

        Args:
            results: Raw results

        Returns:
            Formatted overview results
        """
        # Group by session and show summaries
        formatted = []
        for result in results:
            if "summary" in result:
                formatted.append({
                    "type": "summary",
                    "content": result["summary"],
                    "session_id": result.get("session_id"),
                    "turn_start": result.get("turn_start"),
                    "turn_end": result.get("turn_end")
                })
        return formatted

    def _format_tape_results(self, results: list[dict]) -> list[dict]:
        """
        Format results for tape depth.

        Args:
            results: Raw results

        Returns:
            Formatted tape results with event details
        """
        formatted = []
        for result in results:
            formatted.append({
                "type": "event",
                "event_id": result.get("event_id"),
                "event_type": result.get("event_type"),
                "content": result.get("content"),
                "timestamp": result.get("timestamp"),
                "session_id": result.get("session_id"),
                "relevance_score": result.get("relevance_score", 0)
            })
        return formatted
