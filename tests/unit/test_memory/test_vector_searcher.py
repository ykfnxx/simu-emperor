"""Tests for VectorSearcher."""

import pytest

from simu_emperor.config import EmbeddingConfig
from simu_emperor.memory.models import TapeView
from simu_emperor.memory.vector_searcher import VectorSearcher, CHROMADB_AVAILABLE


pytestmark = pytest.mark.skipif(not CHROMADB_AVAILABLE, reason="chromadb not installed")


@pytest.fixture
def temp_memory_dir(tmp_path):
    """Create temporary memory directory."""
    return tmp_path / "memory"


@pytest.fixture
def mock_embedding_config():
    """Create mock embedding config."""
    return EmbeddingConfig(provider="mock", enabled=True)


@pytest.fixture
def sample_segments():
    """Create sample segments for testing."""
    segment1 = TapeView(
        view_id="view:sess1:0:2",
        session_id="sess1",
        agent_id="revenue_minister",
        anchor_start_id=None,
        anchor_end_id=None,
        tape_position_start=0,
        tape_position_end=2,
        events=[
            {"type": "USER_QUERY", "payload": {"query": "给直隶拨款"}},
            {"type": "TOOL_CALL", "payload": {"intent": "adjust_funds"}},
            {"type": "RESPONSE", "payload": {"response": "已批准拨款"}},
        ],
        anchor_state=None,
        tick_start=10,
        tick_end=12,
        event_count=3,
    )

    segment2 = TapeView(
        view_id="view:sess1:3:5",
        session_id="sess1",
        agent_id="revenue_minister",
        anchor_start_id=None,
        anchor_end_id=None,
        tape_position_start=3,
        tape_position_end=5,
        events=[
            {"type": "USER_QUERY", "payload": {"query": "查看税收情况"}},
            {"type": "TOOL_CALL", "payload": {"intent": "query_tax"}},
            {"type": "RESPONSE", "payload": {"response": "税收正常"}},
        ],
        anchor_state=None,
        tick_start=13,
        tick_end=15,
        event_count=3,
    )

    return [segment1, segment2]


class TestVectorSearcher:
    """Test VectorSearcher functionality."""

    def test_init_with_mock_provider(self, temp_memory_dir, mock_embedding_config):
        """Test initialization with mock provider."""
        searcher = VectorSearcher(temp_memory_dir, mock_embedding_config)

        assert searcher.collection is not None
        assert searcher.collection.name == "segments"

    def test_init_with_openai_provider_missing_key(self, temp_memory_dir):
        """Test OpenAI provider raises error without API key."""
        config = EmbeddingConfig(provider="openai", api_key=None)

        with pytest.raises(ValueError, match="API key is required"):
            VectorSearcher(temp_memory_dir, config)

    @pytest.mark.asyncio
    async def test_add_segments(self, temp_memory_dir, mock_embedding_config, sample_segments):
        """Test adding segments to vector store."""
        searcher = VectorSearcher(temp_memory_dir, mock_embedding_config)

        await searcher.add_segments(sample_segments)

        # Verify segments were added
        count = searcher.collection.count()
        assert count == 2

    @pytest.mark.asyncio
    async def test_add_empty_segments(self, temp_memory_dir, mock_embedding_config):
        """Test adding empty list does nothing."""
        searcher = VectorSearcher(temp_memory_dir, mock_embedding_config)

        await searcher.add_segments([])

        count = searcher.collection.count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_search(self, temp_memory_dir, mock_embedding_config, sample_segments):
        """Test searching for segments."""
        searcher = VectorSearcher(temp_memory_dir, mock_embedding_config)

        await searcher.add_segments(sample_segments)

        results = await searcher.search("资金分配", "revenue_minister", n_results=5)

        # Mock embedding returns deterministic results, so we should get results
        assert isinstance(results, list)
        # Note: with mock embeddings, semantic matching doesn't work,
        # but we verify the search mechanism works

    @pytest.mark.asyncio
    async def test_search_empty_query(
        self, temp_memory_dir, mock_embedding_config, sample_segments
    ):
        """Test empty query returns empty list."""
        searcher = VectorSearcher(temp_memory_dir, mock_embedding_config)

        await searcher.add_segments(sample_segments)

        results = await searcher.search("", "revenue_minister")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_filter_by_agent(
        self, temp_memory_dir, mock_embedding_config, sample_segments
    ):
        """Test search filters by agent_id."""
        searcher = VectorSearcher(temp_memory_dir, mock_embedding_config)

        await searcher.add_segments(sample_segments)

        # Search with different agent_id should return no results
        results = await searcher.search("拨款", "other_agent")

        assert results == []

    def test_segment_to_text(self, temp_memory_dir, mock_embedding_config):
        """Test _segment_to_text extraction."""
        searcher = VectorSearcher(temp_memory_dir, mock_embedding_config)

        segment = TapeView(
            view_id="view:sess1:0:0",
            session_id="sess1",
            agent_id="agent1",
            anchor_start_id=None,
            anchor_end_id=None,
            tape_position_start=0,
            tape_position_end=0,
            events=[
                {
                    "type": "USER_QUERY",
                    "payload": {"message": "测试查询"},
                }
            ],
            anchor_state={"summary": "anchor summary"},
            tick_start=None,
            tick_end=None,
            event_count=1,
        )

        text = searcher._segment_to_text(segment)

        assert "测试查询" in text
        assert "anchor summary" in text

    def test_make_id(self, temp_memory_dir, mock_embedding_config):
        """Test _make_id generates unique IDs."""
        searcher = VectorSearcher(temp_memory_dir, mock_embedding_config)

        segment = TapeView(
            view_id="view:sess1:10:20",
            session_id="sess1",
            agent_id="agent1",
            anchor_start_id=None,
            anchor_end_id=None,
            tape_position_start=10,
            tape_position_end=20,
            events=[],
            anchor_state=None,
            tick_start=None,
            tick_end=None,
            event_count=1,
        )

        segment_id = searcher._make_id(segment)

        assert segment_id == "sess1:10:20"
