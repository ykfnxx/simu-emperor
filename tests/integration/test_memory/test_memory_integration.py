"""Integration tests for V3 memory system."""

from unittest.mock import AsyncMock

import pytest

from simu_emperor.memory.tape_writer import TapeWriter
from simu_emperor.memory.manifest_index import ManifestIndex
from simu_emperor.memory.context_manager import ContextManager, ContextConfig
from simu_emperor.memory.query_parser import QueryParser
from simu_emperor.memory.tape_searcher import TapeSearcher
from simu_emperor.memory.structured_retriever import StructuredRetriever
from simu_emperor.agents.tools.memory_tools import MemoryTools


class TestMemoryIntegration:
    """Integration tests for memory system components working together"""

    @pytest.mark.asyncio
    async def test_write_and_retrieve_cycle(self, tmp_path):
        """Test complete cycle: write events to tape, then retrieve them"""
        # Step 1: Write events to tape
        tape_writer = TapeWriter(memory_dir=tmp_path)

        await tape_writer.write_event(
            {
                "session_id": "session:cli:default",
                "agent_id": "revenue_minister",
                "event_type": "USER_QUERY",
                "content": {"query": "拨款给直隶"},
                "tokens": 10,
            }
        )

        await tape_writer.write_event(
            {
                "session_id": "session:cli:default",
                "agent_id": "revenue_minister",
                "event_type": "TOOL_CALL",
                "content": {
                    "tool": "allocate_funds",
                    "args": {"province": "zhili", "amount": 50000},
                },
                "tokens": 25,
            }
        )

        await tape_writer.write_event(
            {
                "session_id": "session:cli:default",
                "agent_id": "revenue_minister",
                "event_type": "AGENT_RESPONSE",
                "content": {"response": "好的，已拨款50000两给直隶。"},
                "tokens": 20,
            }
        )

        # Step 2: Register session in manifest
        manifest_index = ManifestIndex(memory_dir=tmp_path)
        await manifest_index.register_session("session:cli:default", "revenue_minister", 5)
        await manifest_index.update_session(
            "session:cli:default",
            "revenue_minister",
            key_topics=["拨款", "直隶"],
            summary="玩家询问拨款，已执行。",
            event_count=3,
        )

        # Step 3: Search for events
        tape_searcher = TapeSearcher(memory_dir=tmp_path)
        results = await tape_searcher.search(
            agent_id="revenue_minister",
            session_ids=["session:cli:default"],
            entities={"action": ["拨款"], "target": ["直隶"]},
            max_results=10,
        )

        # Step 4: Verify results
        assert len(results) > 0
        assert any("拨款" in str(r.get("content", {})) for r in results)

    @pytest.mark.asyncio
    async def test_cross_session_retrieval(self, tmp_path):
        """Test retrieving memories across multiple sessions"""
        # Setup: Create two sessions with different topics
        tape_writer = TapeWriter(memory_dir=tmp_path)
        manifest_index = ManifestIndex(memory_dir=tmp_path)

        # Session 1: About funding
        await tape_writer.write_event(
            {
                "session_id": "session:day1",
                "agent_id": "revenue_minister",
                "event_type": "USER_QUERY",
                "content": {"query": "拨款给直隶"},
                "tokens": 10,
            }
        )

        await manifest_index.register_session("session:day1", "revenue_minister", 5)
        await manifest_index.update_session(
            "session:day1",
            "revenue_minister",
            key_topics=["拨款", "直隶"],
            summary="讨论拨款事宜",
            event_count=1,
        )

        # Session 2: About taxation
        await tape_writer.write_event(
            {
                "session_id": "session:day2",
                "agent_id": "revenue_minister",
                "event_type": "USER_QUERY",
                "content": {"query": "调整江南税率"},
                "tokens": 10,
            }
        )

        await manifest_index.register_session("session:day2", "revenue_minister", 6)
        await manifest_index.update_session(
            "session:day2",
            "revenue_minister",
            key_topics=["税率", "江南"],
            summary="讨论税收调整",
            event_count=1,
        )

        # Query: Should match session 1 better
        mock_llm = AsyncMock()
        mock_llm.call = AsyncMock(
            return_value='{"intent": "query_history", "entities": {"action": ["拨款"], "target": ["直隶"]}, "scope": "cross_session", "depth": "tape"}'
        )

        query_parser = QueryParser(llm_provider=mock_llm)
        tape_searcher = TapeSearcher(memory_dir=tmp_path)
        retriever = StructuredRetriever(
            memory_dir=tmp_path,
            query_parser=query_parser,
            manifest_index=manifest_index,
            tape_searcher=tape_searcher,
        )

        result = await retriever.retrieve(
            raw_query="我之前给直隶拨过款吗？",
            agent_id="revenue_minister",
            current_session_id="session:current",
            max_results=5,
        )

        # Should find session:day1 with higher relevance
        assert result.scope == "cross_session"
        assert result.depth == "tape"
        assert result.sessions_searched is not None
        assert len(result.sessions_searched) > 0

    @pytest.mark.asyncio
    async def test_context_manager_sliding_window(self, tmp_path):
        """Test that ContextManager triggers summarization when threshold exceeded"""
        mock_llm = AsyncMock()
        mock_llm.call = AsyncMock(return_value="总结：玩家多次询问拨款和税收问题。")
        mock_llm.get_context_window_size = lambda: 8000

        tape_writer = TapeWriter(memory_dir=tmp_path)
        manifest_index = ManifestIndex(memory_dir=tmp_path)

        # 注册 session
        await manifest_index.register_session(
            session_id="session:cli:default", agent_id="revenue_minister", turn=1
        )

        # 写入一些测试数据到 tape（使用正确的路径）
        await tape_writer.write_event(
            {
                "session_id": "session:cli:default",
                "agent_id": "revenue_minister",
                "event_type": "USER_QUERY",
                "content": {"query": "Q1"},
                "tokens": 15,
            }
        )
        await tape_writer.write_event(
            {
                "session_id": "session:cli:default",
                "agent_id": "revenue_minister",
                "event_type": "AGENT_RESPONSE",
                "content": {"response": "A1"},
                "tokens": 15,
            }
        )
        await tape_writer.write_event(
            {
                "session_id": "session:cli:default",
                "agent_id": "revenue_minister",
                "event_type": "USER_QUERY",
                "content": {"query": "Q2"},
                "tokens": 15,
            }
        )

        # 使用正确的 tape 路径
        tape_path = (
            tmp_path
            / "agents"
            / "revenue_minister"
            / "sessions"
            / "session:cli:default"
            / "tape.jsonl"
        )

        # 使用低阈值触发滑动窗口（禁用锚点感知以测试基本滑动窗口）
        config = ContextConfig(
            max_tokens=100, threshold_ratio=0.95, keep_recent_events=2, enable_anchor_aware=False
        )
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tape_path,
            config=config,
            llm_provider=mock_llm,
            manifest_index=manifest_index,
        )

        # 添加事件直到超过阈值 (100 * 0.95 = 95)
        context_mgr.add_event({"event_type": "USER_QUERY", "content": {"query": "Q1"}}, tokens=30)
        context_mgr.add_event(
            {"event_type": "AGENT_RESPONSE", "content": {"response": "A1"}}, tokens=30
        )
        context_mgr.add_event({"event_type": "USER_QUERY", "content": {"query": "Q2"}}, tokens=30)
        context_mgr.add_event(
            {"event_type": "AGENT_RESPONSE", "content": {"response": "A2"}}, tokens=30
        )

        # 触发滑动窗口（会从 tape 读取并生成总结）
        await context_mgr.slide_window()

        # 应该生成总结
        assert context_mgr.summary is not None
        assert "总结" in context_mgr.summary

        # Should keep only recent events
        assert len(context_mgr.events) <= 2  # keep_recent_events

    @pytest.mark.asyncio
    async def test_memory_tools_end_to_end(self, tmp_path):
        """Test MemoryTools with full retrieval workflow"""
        # Setup: Create sample data
        tape_writer = TapeWriter(memory_dir=tmp_path)
        manifest_index = ManifestIndex(memory_dir=tmp_path)

        await tape_writer.write_event(
            {
                "session_id": "session:history",
                "agent_id": "revenue_minister",
                "event_type": "USER_QUERY",
                "content": {"query": "给直隶拨款5万两"},
                "tokens": 15,
            }
        )

        await manifest_index.register_session("session:history", "revenue_minister", 5)
        await manifest_index.update_session(
            "session:history",
            "revenue_minister",
            key_topics=["拨款", "直隶"],
            summary="玩家给直隶拨款5万两",
            event_count=1,
        )

        # Create MemoryTools
        mock_llm = AsyncMock()
        mock_llm.call = AsyncMock(
            return_value='{"intent": "query_history", "entities": {"action": ["拨款"], "target": ["直隶"]}, "scope": "cross_session", "depth": "tape"}'
        )

        memory_tools = MemoryTools(
            agent_id="revenue_minister", memory_dir=tmp_path, llm_provider=mock_llm
        )

        # Create mock event
        from simu_emperor.event_bus.event import Event

        event = Event(
            src="player",
            dst=["agent:revenue_minister"],
            type="query",
            payload={"query": "我之前给直隶拨过款吗？"},
            session_id="session:current",
        )

        # Retrieve memory
        result = await memory_tools.retrieve_memory(
            args={"query": "我之前给直隶拨过款吗？", "max_results": 5}, event=event
        )

        # Verify formatted result
        assert "检索结果" in result
        assert "我之前给直隶拨过款吗？" in result
