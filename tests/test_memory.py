"""Tests for the V5 memory system.

Covers:
  - TapeMetadataManager: CRUD, keyword search
  - ContextManager: compression with anchor-aware logic
  - MemoryStore: ChromaDB upsert and search
  - MemoryRetriever: two-level search
  - TapeManager: on_first_event callback, query_range
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from simu_shared.constants import EventType
from simu_shared.models import ContextConfig, MemoryConfig, TapeEvent
from simu_sdk.memory.metadata import TapeMetadataManager
from simu_sdk.memory.models import ViewSegment
from simu_sdk.memory.retriever import MemoryRetriever
from simu_sdk.memory.store import MemoryStore
from simu_sdk.tape.context import ContextManager
from simu_sdk.tape.manager import TapeManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(
    session_id: str = "test-session",
    event_type: str = EventType.CHAT,
    src: str = "player",
    content: str = "hello",
    event_id: str | None = None,
) -> TapeEvent:
    return TapeEvent(
        event_id=event_id or f"evt_{id(content)}",
        src=src,
        dst=["agent:test"],
        event_type=event_type,
        payload={"content": content},
        session_id=session_id,
        timestamp=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# TapeMetadataManager tests
# ---------------------------------------------------------------------------

class TestTapeMetadataManager:
    @pytest.fixture
    async def manager(self, tmp_path: Path):
        mgr = TapeMetadataManager(tmp_path / "metadata.db")
        await mgr.initialize()
        yield mgr
        await mgr.close()

    async def test_create_and_get_metadata(self, manager: TapeMetadataManager):
        await manager.create_metadata("session-1", "直隶赈灾讨论")
        meta = await manager.get_metadata("session-1")
        assert meta is not None
        assert meta.title == "直隶赈灾讨论"
        assert meta.session_id == "session-1"

    async def test_has_metadata(self, manager: TapeMetadataManager):
        assert not await manager.has_metadata("nonexistent")
        await manager.create_metadata("s1", "title")
        assert await manager.has_metadata("s1")

    async def test_update_summary(self, manager: TapeMetadataManager):
        await manager.create_metadata("s1", "title")
        await manager.update_summary("s1", "新摘要内容")
        meta = await manager.get_metadata("s1")
        assert meta.summary == "新摘要内容"

    async def test_add_view_and_retrieve(self, manager: TapeMetadataManager):
        await manager.create_metadata("s1", "title")
        view = ViewSegment(
            view_id="view_s1_0_10",
            session_id="s1",
            start_index=0,
            end_index=10,
            summary="前10条事件摘要",
            event_count=8,
        )
        await manager.add_view("s1", view)
        meta = await manager.get_metadata("s1")
        assert len(meta.views) == 1
        assert meta.views[0].summary == "前10条事件摘要"

    async def test_keyword_search(self, manager: TapeMetadataManager):
        await manager.create_metadata("s1", "直隶赈灾拨款")
        await manager.update_summary("s1", "讨论直隶洪灾后的赈灾拨款方案")
        await manager.create_metadata("s2", "江南税收报告")
        await manager.update_summary("s2", "江南地区今年税收增长情况")

        results = await manager.keyword_search("直隶")
        assert len(results) >= 1
        assert results[0][0] == "s1"  # s1 should rank first

    async def test_keyword_search_excludes_session(self, manager: TapeMetadataManager):
        await manager.create_metadata("s1", "直隶赈灾")
        results = await manager.keyword_search("直隶", exclude_session="s1")
        assert len(results) == 0

    async def test_advance_window(self, manager: TapeMetadataManager):
        await manager.create_metadata("s1", "title")
        await manager.advance_window("s1", 20)
        meta = await manager.get_metadata("s1")
        assert meta.window_offset == 20


# ---------------------------------------------------------------------------
# TapeManager callback and query_range tests
# ---------------------------------------------------------------------------

class TestTapeManagerExtensions:
    @pytest.fixture
    async def tape(self, tmp_path: Path):
        t = TapeManager(tmp_path / "tape")
        await t.initialize()
        yield t
        await t.close()

    async def test_on_first_event_callback(self, tape: TapeManager):
        called_with: list[TapeEvent] = []

        async def cb(event: TapeEvent) -> None:
            called_with.append(event)

        tape.on_first_event = cb

        evt1 = _make_event(content="first", event_id="evt_1")
        evt2 = _make_event(content="second", event_id="evt_2")
        await tape.append(evt1)
        await tape.append(evt2)
        # Yield to event loop so background callbacks complete
        await asyncio.sleep(0)

        # Callback should fire only once per session
        assert len(called_with) == 1
        assert called_with[0].event_id == "evt_1"

    async def test_on_first_event_per_session(self, tape: TapeManager):
        called_sessions: list[str] = []

        async def cb(event: TapeEvent) -> None:
            called_sessions.append(event.session_id)

        tape.on_first_event = cb

        await tape.append(_make_event(session_id="s1", event_id="e1"))
        await tape.append(_make_event(session_id="s2", event_id="e2"))
        await tape.append(_make_event(session_id="s1", event_id="e3"))
        # Yield to event loop so background callbacks complete
        await asyncio.sleep(0)

        assert called_sessions == ["s1", "s2"]

    async def test_query_range(self, tape: TapeManager):
        for i in range(10):
            await tape.append(
                _make_event(content=f"msg-{i}", event_id=f"evt_{i}")
            )

        # Get events 3-6 (offset=3, limit=4)
        results = await tape.query_range("test-session", offset=3, limit=4)
        assert len(results) == 4
        assert results[0].payload["content"] == "msg-3"
        assert results[3].payload["content"] == "msg-6"


# ---------------------------------------------------------------------------
# ContextManager compression tests
# ---------------------------------------------------------------------------

class TestContextManagerCompression:
    @pytest.fixture
    async def setup(self, tmp_path: Path):
        tape = TapeManager(tmp_path / "tape")
        await tape.initialize()

        metadata = TapeMetadataManager(tmp_path / "metadata.db")
        await metadata.initialize()

        mock_llm = MagicMock()
        mock_llm.call = AsyncMock(
            return_value=MagicMock(content="摘要：讨论了直隶赈灾方案")
        )

        config = ContextConfig(keep_recent_events=5)
        mem_config = MemoryConfig(anchor_buffer=1)

        ctx = ContextManager(
            tape,
            config,
            memory_config=mem_config,
            metadata_manager=metadata,
            llm=mock_llm,
        )

        yield tape, metadata, ctx, mock_llm

        await tape.close()
        await metadata.close()

    async def test_no_compression_when_all_events_are_anchors(self, setup):
        """P1 fix: when all events are anchors, do NOT advance window."""
        tape, metadata, ctx, mock_llm = setup
        session_id = "test-compress"

        await metadata.create_metadata(session_id, "test")

        # Insert 15 chat/response events (all anchors)
        for i in range(15):
            event_type = EventType.CHAT if i % 2 == 0 else EventType.RESPONSE
            src = "player" if event_type == EventType.CHAT else "agent:test"
            await tape.append(
                _make_event(
                    session_id=session_id,
                    event_type=event_type,
                    src=src,
                    content=f"msg-{i}",
                    event_id=f"evt_{i}_{session_id}",
                )
            )

        # Trigger context build
        await ctx.get_context(session_id)

        # Verify: LLM was NOT called (no compressible events)
        assert not mock_llm.call.called

        # Verify: window was NOT advanced, no views created
        meta = await metadata.get_metadata(session_id)
        assert meta.window_offset == 0
        assert len(meta.views) == 0

    async def test_compression_with_mixed_events(self, setup):
        """Mixed anchor + non-anchor events should compress non-anchors."""
        tape, metadata, ctx, mock_llm = setup
        session_id = "test-mixed"

        await metadata.create_metadata(session_id, "mixed test")

        # Pattern: 1 CHAT anchor, then 8 TOOL_CALL (non-anchor), then 1 RESPONSE anchor,
        # then 5 more TOOL_CALL. With buffer=1, many TOOL_CALL events are compressible.
        event_sequence = [
            (EventType.CHAT, "player"),        # 0 anchor
            (EventType.TOOL_CALL, "agent:test"),  # 1 buffer of 0
            (EventType.TOOL_CALL, "agent:test"),  # 2 compressible
            (EventType.TOOL_CALL, "agent:test"),  # 3 compressible
            (EventType.TOOL_CALL, "agent:test"),  # 4 compressible
            (EventType.TOOL_CALL, "agent:test"),  # 5 compressible
            (EventType.TOOL_CALL, "agent:test"),  # 6 compressible
            (EventType.TOOL_CALL, "agent:test"),  # 7 compressible
            (EventType.TOOL_CALL, "agent:test"),  # 8 buffer of 9
            (EventType.RESPONSE, "agent:test"),   # 9 anchor
            (EventType.TOOL_CALL, "agent:test"),  # 10 buffer of 9
            (EventType.TOOL_CALL, "agent:test"),  # 11
            (EventType.TOOL_CALL, "agent:test"),  # 12
            (EventType.TOOL_CALL, "agent:test"),  # 13
            (EventType.TOOL_CALL, "agent:test"),  # 14
        ]
        for i, (et, src) in enumerate(event_sequence):
            await tape.append(
                _make_event(
                    session_id=session_id,
                    event_type=et,
                    src=src,
                    content=f"msg-{i}",
                    event_id=f"evt_{i}_{session_id}",
                )
            )

        await ctx.get_context(session_id)

        # Should have compressed and created a view
        meta = await metadata.get_metadata(session_id)
        assert meta.window_offset > 0
        assert len(meta.views) >= 1

    async def test_no_compression_when_few_events(self, setup):
        """Should not compress when event count is below threshold."""
        tape, metadata, ctx, mock_llm = setup
        session_id = "test-few"

        await metadata.create_metadata(session_id, "few events")

        for i in range(5):
            await tape.append(
                _make_event(
                    session_id=session_id,
                    content=f"msg-{i}",
                    event_id=f"evt_{i}_{session_id}",
                )
            )

        context = await ctx.get_context(session_id)

        # No compression should happen
        assert not mock_llm.call.called
        assert len(context.events) == 5

    async def test_session_summary_update(self, setup):
        """update_session_summary should call LLM and persist."""
        tape, metadata, ctx, mock_llm = setup
        session_id = "test-summary"

        await metadata.create_metadata(session_id, "summary test")

        events = [
            _make_event(
                session_id=session_id,
                content="讨论赈灾",
                event_id="evt_sum_1",
            ),
        ]

        mock_llm.call = AsyncMock(
            return_value=MagicMock(content="本次讨论了赈灾方案")
        )
        result = await ctx.update_session_summary(session_id, events)

        assert result == "本次讨论了赈灾方案"
        meta = await metadata.get_metadata(session_id)
        assert meta.summary == "本次讨论了赈灾方案"

    async def test_title_generation(self, setup):
        """generate_title should call LLM."""
        tape, metadata, ctx, mock_llm = setup

        mock_llm.call = AsyncMock(
            return_value=MagicMock(content="直隶赈灾讨论")
        )
        event = _make_event(content="朕要讨论直隶赈灾一事")
        title = await ctx.generate_title(event)
        assert title == "直隶赈灾讨论"


# ---------------------------------------------------------------------------
# MemoryStore tests (ChromaDB)
# ---------------------------------------------------------------------------

class TestMemoryStore:
    @pytest.fixture
    async def store(self, tmp_path: Path):
        s = MemoryStore("test_agent", tmp_path / "chromadb")
        await s.initialize()
        yield s
        await s.close()

    async def test_upsert_and_search_view(self, store: MemoryStore):
        view = ViewSegment(
            view_id="view_s1_0_10",
            session_id="s1",
            start_index=0,
            end_index=10,
            summary="讨论了直隶洪灾后的赈灾拨款方案，决定拨银五十万两",
            event_count=8,
        )
        await store.upsert_view(view)

        results = await store.search_views("直隶赈灾拨款", n_results=5)
        assert len(results) >= 1
        assert results[0].session_id == "s1"

    async def test_upsert_and_search_session_summary(self, store: MemoryStore):
        await store.upsert_session_summary(
            "s1", "直隶赈灾讨论：决定拨银五十万两", title="直隶赈灾",
        )

        results = await store.search_sessions("赈灾拨款", n_results=5)
        assert len(results) >= 1
        assert results[0].session_id == "s1"

    async def test_search_views_filters_by_session(self, store: MemoryStore):
        v1 = ViewSegment(
            view_id="view_s1_0_10", session_id="s1",
            start_index=0, end_index=10,
            summary="直隶赈灾拨款讨论", event_count=5,
        )
        v2 = ViewSegment(
            view_id="view_s2_0_10", session_id="s2",
            start_index=0, end_index=10,
            summary="江南税收报告分析", event_count=5,
        )
        await store.upsert_view(v1)
        await store.upsert_view(v2)

        results = await store.search_views("赈灾", session_ids=["s1"])
        # Should only return s1 views
        for r in results:
            assert r.session_id == "s1"


# ---------------------------------------------------------------------------
# MemoryRetriever tests
# ---------------------------------------------------------------------------

class TestMemoryRetriever:
    @pytest.fixture
    async def setup(self, tmp_path: Path):
        metadata = TapeMetadataManager(tmp_path / "metadata.db")
        await metadata.initialize()
        store = MemoryStore("test_agent", tmp_path / "chromadb")
        await store.initialize()
        retriever = MemoryRetriever(metadata, store)

        # Seed data
        await metadata.create_metadata("s1", "直隶赈灾讨论")
        await metadata.update_summary("s1", "讨论了直隶洪灾后的赈灾拨款方案")
        await store.upsert_session_summary(
            "s1", "讨论了直隶洪灾后的赈灾拨款方案", title="直隶赈灾讨论",
        )

        view = ViewSegment(
            view_id="view_s1_0_10", session_id="s1",
            start_index=0, end_index=10,
            summary="决定拨银五十万两用于赈灾", event_count=8,
        )
        await metadata.add_view("s1", view)
        await store.upsert_view(view)

        await metadata.create_metadata("s2", "江南税收")
        await metadata.update_summary("s2", "江南地区税收增长情况汇报")
        await store.upsert_session_summary(
            "s2", "江南地区税收增长情况汇报", title="江南税收",
        )

        yield retriever, metadata, store

        await metadata.close()
        await store.close()

    async def test_two_level_search(self, setup):
        retriever, _, _ = setup
        results = await retriever.search("直隶赈灾", current_session_id="s-current")
        assert len(results) >= 1
        # s1 should be the top result
        assert any(r.session_id == "s1" for r in results)

    async def test_excludes_current_session(self, setup):
        retriever, _, _ = setup
        results = await retriever.search("直隶赈灾", current_session_id="s1")
        # Should not include s1 since it's the current session
        for r in results:
            assert r.session_id != "s1"

    async def test_empty_query_returns_empty(self, setup):
        retriever, _, _ = setup
        results = await retriever.search("", current_session_id="s-current")
        assert results == []
