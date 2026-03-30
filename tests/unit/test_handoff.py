"""Unit tests for execute_handoff protocol."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from simu_emperor.memory.context_manager import ContextManager, ContextConfig


@pytest.fixture
def mock_cm():
    config = ContextConfig(max_tokens=8000, threshold_ratio=0.95)
    cm = ContextManager(
        session_id="test_sess",
        agent_id="test_agent",
        tape_path=MagicMock(),
        config=config,
        llm_provider=AsyncMock(),
    )
    cm._tape_metadata_mgr = AsyncMock()
    cm._vector_searcher = AsyncMock()
    cm._current_anchor_id = None
    return cm


@pytest.mark.asyncio
async def test_execute_handoff_creates_anchor(mock_cm):
    mock_cm.llm.call = AsyncMock(return_value="摘要文本")
    events = [{"event_id": "e1", "type": "chat", "payload": {"message": "test"}}]

    anchor = await mock_cm.execute_handoff(events, reason="conversation_end")

    assert anchor.name == "handoff/conversation_end"
    assert anchor.state["summary"] == "摘要文本"
    assert mock_cm._current_anchor_id == anchor.anchor_id


@pytest.mark.asyncio
async def test_execute_handoff_compaction_reason(mock_cm):
    mock_cm.llm.call = AsyncMock(return_value="compacted")
    events = [{"event_id": "e2", "type": "observation", "payload": {}}]

    anchor = await mock_cm.execute_handoff(events, reason="compaction")
    assert anchor.name == "handoff/compaction"
