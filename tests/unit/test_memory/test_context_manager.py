"""Test ContextManager for context window management."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from simu_emperor.memory.context_manager import ContextManager, ContextConfig


class TestContextManager:
    """Test ContextManager class"""

    @pytest.mark.asyncio
    async def test_add_event_increases_token_count(self, tmp_path):
        """Test that add_event increases total token count"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary of conversation.")
        llm.get_context_window_size = lambda: 8000

        config = ContextConfig(max_tokens=1000)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm
        )

        context_mgr.add_event(
            event={"event_type": "USER_QUERY", "content": {"query": "拨款给直隶"}},
            tokens=50
        )

        assert len(context_mgr.events) == 1

    @pytest.mark.asyncio
    async def test_add_event_multiple(self, tmp_path):
        """Test adding multiple events accumulates tokens"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary.")
        llm.get_context_window_size = lambda: 8000

        config = ContextConfig(max_tokens=1000)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm
        )

        context_mgr.add_event({"event_type": "USER_QUERY", "content": {"query": "Q1"}}, tokens=30)
        context_mgr.add_event({"event_type": "AGENT_RESPONSE", "content": {"response": "A1"}}, tokens=50)
        context_mgr.add_event({"event_type": "USER_QUERY", "content": {"query": "Q2"}}, tokens=20)

        assert len(context_mgr.events) == 3

    @pytest.mark.asyncio
    async def test_get_messages_returns_formatted_messages(self, tmp_path):
        """Test that get_messages returns properly formatted messages"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary.")
        llm.get_context_window_size = lambda: 8000

        config = ContextConfig(max_tokens=1000)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm
        )

        context_mgr.add_event({"event_type": "USER_QUERY", "content": {"query": "拨款给直隶"}}, tokens=15)
        context_mgr.add_event({"event_type": "AGENT_RESPONSE", "content": {"response": "好的，我将拨款。"}}, tokens=20)

        messages = context_mgr.build_messages()

        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert "拨款给直隶" in messages[0]["content"]
        assert messages[1]["role"] == "assistant"
        assert "好的，我将拨款。" in messages[1]["content"]

    @pytest.mark.asyncio
    async def test_slide_window_trigger(self, tmp_path):
        """Test that sliding window triggers when threshold exceeded"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary of conversation.")
        llm.get_context_window_size = lambda: 8000

        # 设置低阈值以便容易触发
        config = ContextConfig(max_tokens=100, threshold_ratio=0.95)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm
        )

        # 添加事件直到超过阈值 (100 * 0.95 = 95)
        need_slide = context_mgr.add_event({"event_type": "USER_QUERY", "content": {"query": "Q1"}}, tokens=30)
        assert not need_slide  # 30 < 95

        need_slide = context_mgr.add_event({"event_type": "AGENT_RESPONSE", "content": {"response": "A1"}}, tokens=30)
        assert not need_slide  # 60 < 95

        need_slide = context_mgr.add_event({"event_type": "USER_QUERY", "content": {"query": "Q2"}}, tokens=30)
        assert not need_slide  # 90 < 95

        # 再添加一个事件，超过阈值
        need_slide = context_mgr.add_event({"event_type": "AGENT_RESPONSE", "content": {"response": "A2"}}, tokens=30)
        assert need_slide  # 120 > 95
