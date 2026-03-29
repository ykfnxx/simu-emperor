"""Unit tests for VectorStore (V4.2 Phase 3)."""

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from simu_emperor.memory.models import TapeSegment
from simu_emperor.memory.vector_store import VectorStore

if TYPE_CHECKING:
    pass


@pytest.fixture
def sample_segment():
    return TapeSegment(
        session_id="session_test",
        agent_id="agent_test",
        start_position=0,
        end_position=5,
        event_count=6,
        events=[{"type": "chat", "payload": {"message": f"msg{i}"}} for i in range(6)],
        tick_start=10,
        tick_end=15,
    )


@pytest.fixture
def mock_searcher():
    return MagicMock()


@pytest.fixture
def mock_settings():
    mock_emb = MagicMock()
    mock_emb.enabled = True
    mock_emb.max_retries = 3
    mock_emb.retry_delay = 0.1
    mock_chroma = MagicMock()
    mock_chroma.enabled = True
    return mock_emb, mock_chroma


class TestVectorStoreEnabled:
    """Test VectorStore enabled property."""

    def test_enabled_when_all_conditions_met(self, mock_searcher, mock_settings):
        with patch("simu_emperor.memory.vector_store.settings") as mock_cfg:
            mock_cfg.embedding = mock_settings[0]
            mock_cfg.chromadb = mock_settings[1]

            store = VectorStore(vector_searcher=mock_searcher)
            assert store.enabled is True

    def test_disabled_when_no_searcher(self, mock_settings):
        with patch("simu_emperor.memory.vector_store.settings") as mock_cfg:
            mock_cfg.embedding = mock_settings[0]
            mock_cfg.chromadb = mock_settings[1]

            store = VectorStore(vector_searcher=None)
            assert store.enabled is False

    def test_disabled_when_embedding_disabled(self, mock_searcher):
        mock_emb = MagicMock()
        mock_emb.enabled = False
        mock_emb.max_retries = 3
        mock_emb.retry_delay = 0.1
        mock_chroma = MagicMock()
        mock_chroma.enabled = True

        with patch("simu_emperor.memory.vector_store.settings") as mock_cfg:
            mock_cfg.embedding = mock_emb
            mock_cfg.chromadb = mock_chroma

            store = VectorStore(vector_searcher=mock_searcher)
            assert store.enabled is False

    def test_disabled_when_chromadb_disabled(self, mock_searcher):
        mock_emb = MagicMock()
        mock_emb.enabled = True
        mock_emb.max_retries = 3
        mock_emb.retry_delay = 0.1
        mock_chroma = MagicMock()
        mock_chroma.enabled = False

        with patch("simu_emperor.memory.vector_store.settings") as mock_cfg:
            mock_cfg.embedding = mock_emb
            mock_cfg.chromadb = mock_chroma

            store = VectorStore(vector_searcher=mock_searcher)
            assert store.enabled is False


class TestStoreWithRetry:
    """Test _store_with_retry method."""

    @pytest.mark.asyncio
    async def test_store_with_retry_success(self, mock_searcher, sample_segment, mock_settings):
        mock_searcher.add_segments = MagicMock()
        with patch("simu_emperor.memory.vector_store.settings") as mock_cfg:
            mock_cfg.embedding = mock_settings[0]
            mock_cfg.chromadb = mock_settings[1]

            store = VectorStore(vector_searcher=mock_searcher)
            await store._store_with_retry(
                "seg_test_0_5", "document text", {"tick": 10}, sample_segment
            )

            mock_searcher.add_segments.assert_called_once_with([sample_segment])

    @pytest.mark.asyncio
    async def test_store_with_retry_fails_all_attempts(
        self, mock_searcher, sample_segment, mock_settings
    ):
        mock_searcher.add_segments = MagicMock(side_effect=Exception("Connection error"))
        callback = AsyncMock()
        with patch("simu_emperor.memory.vector_store.settings") as mock_cfg:
            mock_cfg.embedding = mock_settings[0]
            mock_cfg.chromadb = mock_settings[1]

            store = VectorStore(
                vector_searcher=mock_searcher,
                on_embedding_failed=callback,
            )
            with pytest.raises(Exception, match="Connection error"):
                await store._store_with_retry(
                    "seg_test_0_5", "document text", {"tick": 10}, sample_segment
                )

            assert mock_searcher.add_segments.call_count == 3
            callback.assert_called_once()
            call_args = callback.call_args[0]
            assert call_args[0] == "seg_test_0_5"
            assert "Connection error" in call_args[3]

    @pytest.mark.asyncio
    async def test_store_with_retry_exponential_backoff(
        self, mock_searcher, sample_segment, mock_settings
    ):
        sleep_times = []

        async def fake_sleep(delay):
            sleep_times.append(delay)

        mock_searcher.add_segments.side_effect = Exception("Error")
        with patch("simu_emperor.memory.vector_store.settings") as mock_cfg:
            mock_cfg.embedding = mock_settings[0]
            mock_cfg.chromadb = mock_settings[1]

            store = VectorStore(vector_searcher=mock_searcher)
            store._retry_delay = 1.0

            with patch("asyncio.sleep", fake_sleep):
                with pytest.raises(Exception, match="Error"):
                    await store._store_with_retry(
                        "seg_test_0_5", "doc", {"tick": 10}, sample_segment
                    )

        assert sleep_times == [1.0, 2.0]

    @pytest.mark.asyncio
    async def test_store_with_retry_succeeds_on_second_attempt(
        self, mock_searcher, sample_segment, mock_settings
    ):
        call_count = 0

        def side_effect(segments):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First failure")
            return None

        mock_searcher.add_segments.side_effect = side_effect

        with patch("simu_emperor.memory.vector_store.settings") as mock_cfg:
            mock_cfg.embedding = mock_settings[0]
            mock_cfg.chromadb = mock_settings[1]

            store = VectorStore(vector_searcher=mock_searcher)
            await store._store_with_retry("seg_test_0_5", "document", {"tick": 10}, sample_segment)

            assert call_count == 2


class TestAddSegmentsWithRetry:
    """Test add_segments_with_retry method."""

    @pytest.mark.asyncio
    async def test_add_segments_with_retry_empty_list(
        self, mock_searcher, sample_segment, mock_settings
    ):
        with patch("simu_emperor.memory.vector_store.settings") as mock_cfg:
            mock_cfg.embedding = mock_settings[0]
            mock_cfg.chromadb = mock_settings[1]

            store = VectorStore(vector_searcher=mock_searcher)
            await store.add_segments_with_retry([])
            mock_searcher.add_segments.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_segments_with_retry_disabled(self, mock_searcher, sample_segment):
        mock_emb = MagicMock()
        mock_emb.enabled = False

        with patch("simu_emperor.memory.vector_store.settings") as mock_cfg:
            mock_cfg.embedding = mock_emb
            mock_cfg.chromadb = MagicMock()

            store = VectorStore(vector_searcher=mock_searcher)
            await store.add_segments_with_retry([sample_segment])
            mock_searcher.add_segments.assert_not_called()


class TestSearch:
    """Test search method."""

    @pytest.mark.asyncio
    async def test_search_degradation(self, mock_searcher, sample_segment, mock_settings):
        mock_searcher.search = MagicMock(side_effect=Exception("Search failed"))
        with patch("simu_emperor.memory.vector_store.settings") as mock_cfg:
            mock_cfg.embedding = mock_settings[0]
            mock_cfg.chromadb = mock_settings[1]

            store = VectorStore(vector_searcher=mock_searcher)
            results = await store.search("query", "agent_test")
            assert results == []

    @pytest.mark.asyncio
    async def test_search_disabled_returns_empty(self, mock_settings):
        with patch("simu_emperor.memory.vector_store.settings") as mock_cfg:
            mock_cfg.embedding = mock_settings[0]
            mock_cfg.chromadb = mock_settings[1]

            store = VectorStore(vector_searcher=None)
            results = await store.search("query", "agent_test")
            assert results == []

    @pytest.mark.asyncio
    async def test_search_success(self, mock_searcher, sample_segment, mock_settings):
        mock_searcher.search = AsyncMock(return_value=["seg_1", "seg_2"])
        with patch("simu_emperor.memory.vector_store.settings") as mock_cfg:
            mock_cfg.embedding = mock_settings[0]
            mock_cfg.chromadb = mock_settings[1]

            store = VectorStore(vector_searcher=mock_searcher)
            results = await store.search("query", "agent_test", n_results=5)
            mock_searcher.search.assert_called_once_with("query", "agent_test", 5)
            assert results == ["seg_1", "seg_2"]


class TestRetryFailedEmbeddings:
    """Test retry_failed_embeddings method."""

    @pytest.mark.asyncio
    async def test_retry_failed_embeddings_success(
        self, mock_searcher, sample_segment, mock_settings
    ):
        failed_records = [
            {
                "segment_id": "seg_1",
                "summary": "Summary 1",
                "metadata": json.dumps(
                    {
                        "session_id": "s1",
                        "agent_id": "a1",
                        "segment_start": 0,
                        "segment_end": 5,
                        "tick": 10,
                    }
                ),
            }
        ]
        get_failed = AsyncMock(return_value=failed_records)
        mark_retried = AsyncMock()
        remove_failed = AsyncMock()

        with patch("simu_emperor.memory.vector_store.settings") as mock_cfg:
            mock_cfg.embedding = mock_settings[0]
            mock_cfg.chromadb = mock_settings[1]

            store = VectorStore(vector_searcher=mock_searcher)
            count = await store.retry_failed_embeddings(get_failed, mark_retried, remove_failed)
            assert count == 1
            remove_failed.assert_called_once_with("seg_1")

    @pytest.mark.asyncio
    async def test_retry_failed_embeddings_marks_on_failure(
        self, mock_searcher, sample_segment, mock_settings
    ):
        mock_searcher.add_segments.side_effect = Exception("Still failing")
        failed_records = [
            {
                "segment_id": "seg_1",
                "summary": "Summary 1",
                "metadata": json.dumps(
                    {
                        "session_id": "s1",
                        "agent_id": "a1",
                        "segment_start": 0,
                        "segment_end": 5,
                        "tick": 10,
                    }
                ),
            }
        ]
        get_failed = AsyncMock(return_value=failed_records)
        mark_retried = AsyncMock()
        remove_failed = AsyncMock()

        with patch("simu_emperor.memory.vector_store.settings") as mock_cfg:
            mock_cfg.embedding = mock_settings[0]
            mock_cfg.chromadb = mock_settings[1]

            store = VectorStore(vector_searcher=mock_searcher)
            count = await store.retry_failed_embeddings(get_failed, mark_retried, remove_failed)
            assert count == 0
            mark_retried.assert_called_once_with("seg_1")


class TestSummarizeSegment:
    """Test summarize_segment action tool."""

    @pytest.mark.asyncio
    async def test_summarize_segment_success(self, tmp_path):
        from simu_emperor.agents.tools.action_tools import ActionTools
        from simu_emperor.event_bus.event import Event
        from simu_emperor.event_bus.event_types import EventType

        event_bus = MagicMock()
        event_bus.send_event = AsyncMock()
        tools = ActionTools(
            agent_id="test_agent",
            event_bus=event_bus,
            data_dir=tmp_path,
        )
        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.CHAT,
            payload={"message": "拨款给直隶"},
            session_id="session_test",
        )
        result = await tools.summarize_segment(
            {"start": 0, "end": 5, "summary": "这是一个测试摘要"},
            event,
        )
        assert "✅" in result
        assert "[0:5]" in result

    @pytest.mark.asyncio
    async def test_summarize_segment_empty_summary(self, tmp_path):
        from simu_emperor.agents.tools.action_tools import ActionTools
        from simu_emperor.event_bus.event import Event
        from simu_emperor.event_bus.event_types import EventType

        event_bus = MagicMock()
        event_bus.send_event = AsyncMock()
        tools = ActionTools(
            agent_id="test_agent",
            event_bus=event_bus,
            data_dir=tmp_path,
        )
        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.CHAT,
            payload={"message": "拨款给直隶"},
            session_id="session_test",
        )
        result = await tools.summarize_segment(
            {"start": 0, "end": 5, "summary": ""},
            event,
        )
        assert "❌" in result
        assert "不能为空" in result

    @pytest.mark.asyncio
    async def test_summarize_segment_whitespace_summary(self, tmp_path):
        from simu_emperor.agents.tools.action_tools import ActionTools
        from simu_emperor.event_bus.event import Event
        from simu_emperor.event_bus.event_types import EventType

        event_bus = MagicMock()
        event_bus.send_event = AsyncMock()
        tools = ActionTools(
            agent_id="test_agent",
            event_bus=event_bus,
            data_dir=tmp_path,
        )
        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.CHAT,
            payload={"message": "拨款给直隶"},
            session_id="session_test",
        )
        result = await tools.summarize_segment(
            {"start": 0, "end": 5, "summary": "   "},
            event,
        )
        assert "❌" in result
