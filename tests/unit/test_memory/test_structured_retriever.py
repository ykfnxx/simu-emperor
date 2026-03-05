"""Test StructuredRetriever for coordinating retrieval."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from simu_emperor.memory.structured_retriever import StructuredRetriever
from simu_emperor.memory.query_parser import QueryParser
from simu_emperor.memory.manifest_index import ManifestIndex
from simu_emperor.memory.tape_searcher import TapeSearcher
from simu_emperor.memory.context_manager import ContextManager, ContextConfig


class TestStructuredRetriever:
    """Test StructuredRetriever class"""

    @pytest.mark.asyncio
    async def test_retrieve_current_session(self, tmp_path):
        """Test retrieving from current session"""
        # Mock components
        mock_llm = AsyncMock()
        mock_llm.call = AsyncMock(
            return_value='{"intent": "query_status", "entities": {"time": "current"}, "scope": "current_session", "depth": "overview"}'
        )

        query_parser = QueryParser(llm_provider=mock_llm)
        manifest_index = ManifestIndex(memory_dir=tmp_path)
        tape_searcher = TapeSearcher(memory_dir=tmp_path)

        retriever = StructuredRetriever(
            memory_dir=tmp_path,
            query_parser=query_parser,
            manifest_index=manifest_index,
            tape_searcher=tape_searcher,
        )

        # Mock context manager
        mock_context_mgr = AsyncMock()
        mock_context_mgr.get_messages = AsyncMock(
            return_value=[{"role": "user", "content": "现在的国库情况？"}]
        )

        result = await retriever.retrieve(
            raw_query="现在的国库情况？",
            agent_id="revenue_minister",
            current_session_id="session:cli:default",
            context_manager=mock_context_mgr,
            max_results=5,
        )

        assert result.query == "现在的国库情况？"
        assert result.scope == "current_session"
        assert result.depth == "overview"
        assert isinstance(result.results, list)

    @pytest.mark.asyncio
    async def test_retrieve_cross_session(self, tmp_path):
        """Test retrieving across sessions"""
        mock_llm = AsyncMock()
        mock_llm.call = AsyncMock(
            return_value='{"intent": "query_history", "entities": {"action": ["拨款"], "target": ["直隶"], "time": "history"}, "scope": "cross_session", "depth": "tape"}'
        )

        query_parser = QueryParser(llm_provider=mock_llm)
        manifest_index = ManifestIndex(memory_dir=tmp_path)
        tape_searcher = TapeSearcher(memory_dir=tmp_path)

        # Register a session
        await manifest_index.register_session("session:cli:default", "revenue_minister", 5)
        await manifest_index.update_session(
            "session:cli:default",
            "revenue_minister",
            key_topics=["拨款", "直隶"],
            summary="拨款给直隶",
            event_count=3,
        )

        retriever = StructuredRetriever(
            memory_dir=tmp_path,
            query_parser=query_parser,
            manifest_index=manifest_index,
            tape_searcher=tape_searcher,
        )

        result = await retriever.retrieve(
            raw_query="我之前给直隶拨过款吗？",
            agent_id="revenue_minister",
            current_session_id="session:new",
            max_results=5,
        )

        assert result.query == "我之前给直隶拨过款吗？"
        assert result.scope == "cross_session"
        assert result.depth == "tape"
        assert result.sessions_searched is not None
