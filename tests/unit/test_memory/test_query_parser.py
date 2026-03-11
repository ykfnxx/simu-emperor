"""Test QueryParser for natural language query parsing."""

from unittest.mock import AsyncMock

import pytest

from simu_emperor.memory.query_parser import QueryParser


class TestQueryParser:
    """Test QueryParser class"""

    @pytest.mark.asyncio
    async def test_parse_history_query(self):
        """Test parsing a history query"""
        llm = AsyncMock()
        llm.call = AsyncMock(
            return_value='{"intent": "query_history", "entities": {"action": ["拨款"], "target": ["直隶"], "time": "history"}, "scope": "cross_session", "depth": "tape"}'
        )

        parser = QueryParser(llm_provider=llm)
        result = await parser.parse("我之前给直隶拨过款吗？")

        assert result.structured.intent == "query_history"
        assert result.structured.entities["action"] == ["拨款"]
        assert result.structured.entities["target"] == ["直隶"]
        assert result.structured.scope == "cross_session"
        assert result.structured.depth == "tape"
        assert result.parsed_by == "llm"
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_parse_status_query(self):
        """Test parsing a status query"""
        llm = AsyncMock()
        llm.call = AsyncMock(
            return_value='{"intent": "query_status", "entities": {"time": "current"}, "scope": "current_session", "depth": "overview"}'
        )

        parser = QueryParser(llm_provider=llm)
        result = await parser.parse("现在的国库情况？")

        assert result.structured.intent == "query_status"
        assert result.structured.scope == "current_session"
        assert result.structured.depth == "overview"
