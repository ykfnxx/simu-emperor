"""Test memory module data models"""

from simu_emperor.memory.models import StructuredQuery, ParseResult, RetrievalResult
from simu_emperor.memory.exceptions import ParseError, RetrievalError


class TestStructuredQuery:
    """Test StructuredQuery dataclass"""

    def test_structured_query_creation(self):
        """Test creating StructuredQuery with all fields"""
        query = StructuredQuery(
            raw_query="我之前给直隶拨过款吗？",
            intent="query_history",
            entities={"action": ["拨款"], "target": ["直隶"], "time": "history"},
            scope="cross_session",
            depth="tape",
        )

        assert query.raw_query == "我之前给直隶拨过款吗？"
        assert query.intent == "query_history"
        assert query.entities == {"action": ["拨款"], "target": ["直隶"], "time": "history"}
        assert query.scope == "cross_session"
        assert query.depth == "tape"


class TestParseResult:
    """Test ParseResult dataclass"""

    def test_parse_result_creation(self):
        """Test creating ParseResult with all fields"""
        structured_query = StructuredQuery(
            raw_query="我之前给直隶拨过款吗？",
            intent="query_history",
            entities={"action": ["拨款"], "target": ["直隶"], "time": "history"},
            scope="cross_session",
            depth="tape",
        )

        result = ParseResult(structured=structured_query, parsed_by="llm", latency_ms=150.5)

        assert result.structured == structured_query
        assert result.parsed_by == "llm"
        assert result.latency_ms == 150.5


class TestRetrievalResult:
    """Test RetrievalResult dataclass"""

    def test_retrieval_result_creation(self):
        """Test creating RetrievalResult with all fields"""
        result = RetrievalResult(
            query="我之前给直隶拨过款吗？",
            scope="cross_session",
            depth="tape",
            results=[{"event_id": "evt_001", "type": "TOOL_CALL", "content": "拨款给直隶"}],
            sessions_searched=["session:cli:default"],
        )

        assert result.query == "我之前给直隶拨过款吗？"
        assert result.scope == "cross_session"
        assert result.depth == "tape"
        assert len(result.results) == 1
        assert result.sessions_searched == ["session:cli:default"]

    def test_retrieval_result_without_optional_fields(self):
        """Test creating RetrievalResult without optional sessions_searched"""
        result = RetrievalResult(
            query="现在的国库情况？", scope="current_session", depth="overview", results=[]
        )

        assert result.query == "现在的国库情况？"
        assert result.results == []
        assert result.sessions_searched is None


class TestParseError:
    """Test ParseError exception"""

    def test_parse_error_creation(self):
        """Test creating ParseError with message"""
        error = ParseError("Failed to parse query: Invalid JSON")

        assert str(error) == "Failed to parse query: Invalid JSON"
        assert isinstance(error, Exception)

    def test_parse_error_with_query(self):
        """Test creating ParseError with query details"""
        error = ParseError("Failed to parse", query="我之前给直隶拨过款吗？")

        assert "Failed to parse" in str(error)
        assert error.args[0] == "Failed to parse"


class TestRetrievalError:
    """Test RetrievalError exception"""

    def test_retrieval_error_creation(self):
        """Test creating RetrievalError with message"""
        error = RetrievalError("No sessions found for agent")

        assert str(error) == "No sessions found for agent"
        assert isinstance(error, Exception)

    def test_retrieval_error_with_details(self):
        """Test creating RetrievalError with details"""
        error = RetrievalError(
            "Search failed", agent_id="revenue_minister", session_ids=["session:cli:default"]
        )

        assert "Search failed" in str(error)
