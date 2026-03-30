"""Integration test: handoff → anchor → vector DB → search → MEMORY_INJECTED event.

Tests the full tape.systems handoff flow:
1. ContextManager.execute_handoff() creates anchor and TapeView
2. Anchor persisted to TapeMetadataManager
3. TapeView indexed in VectorSearcher (mock)
4. MEMORY_INJECTED event created on retrieval
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path

from simu_emperor.memory.context_manager import ContextManager, ContextConfig
from simu_emperor.memory.models import TapeAnchor, TapeView, TapeMetadataEntry
from simu_emperor.event_bus.event_types import EventType


@pytest.fixture
def mock_llm():
    """Mock LLM that returns summary first, then entities."""
    llm = AsyncMock()
    # execute_handoff calls llm.call twice: summary then entities
    llm.call = AsyncMock(
        side_effect=[
            "皇帝与户部尚书讨论了直隶拨款事宜",
            "直隶, 拨款, 户部",
        ]
    )
    return llm


@pytest.fixture
def mock_tape_metadata_mgr():
    mgr = AsyncMock()
    mgr.add_anchor = AsyncMock()
    return mgr


@pytest.fixture
def mock_vector_searcher():
    searcher = AsyncMock()
    searcher.add_segments = AsyncMock()
    return searcher


@pytest.fixture
def context_manager(mock_llm, mock_tape_metadata_mgr, mock_vector_searcher):
    config = ContextConfig(max_tokens=8000, threshold_ratio=0.95)
    cm = ContextManager(
        session_id="session:test_handoff",
        agent_id="revenue_minister",
        tape_path=MagicMock(spec=Path),
        config=config,
        llm_provider=mock_llm,
        tape_metadata_mgr=mock_tape_metadata_mgr,
        vector_searcher=mock_vector_searcher,
    )
    cm._tape_position_counter = 10
    cm._window_offset = 0
    cm._current_anchor_id = None
    return cm


@pytest.mark.asyncio
async def test_full_handoff_flow(
    context_manager, mock_llm, mock_tape_metadata_mgr, mock_vector_searcher
):
    """Test complete handoff flow: events → anchor → vector store."""
    events = [
        {"event_id": "evt_001", "type": "chat", "payload": {"message": "拨款给直隶"}, "tick": 5},
        {
            "event_id": "evt_002",
            "type": "tool_call",
            "payload": {"tool": "query_province_data"},
            "tick": 5,
        },
        {
            "event_id": "evt_003",
            "type": "observation",
            "payload": {"result": "直隶人口100万"},
            "tick": 5,
        },
        {
            "event_id": "evt_004",
            "type": "chat",
            "payload": {"message": "同意拨款5000两"},
            "tick": 6,
        },
    ]

    # Step 1: Execute handoff
    anchor = await context_manager.execute_handoff(events, reason="conversation_end")

    # Step 2: Verify anchor was created correctly
    assert isinstance(anchor, TapeAnchor)
    assert anchor.name == "handoff/conversation_end"
    assert anchor.tape_position == 10  # matches _tape_position_counter
    assert "summary" in anchor.state
    assert anchor.state["summary"] == "皇帝与户部尚书讨论了直隶拨款事宜"
    assert len(anchor.state["source_entry_ids"]) == 4
    assert anchor.state["tick_range"] == [5, 6]

    # Step 3: Verify current_anchor_id was set
    assert context_manager._current_anchor_id == anchor.anchor_id

    # Step 4: Verify anchor was persisted to metadata manager
    mock_tape_metadata_mgr.add_anchor.assert_called_once()
    call_kwargs = mock_tape_metadata_mgr.add_anchor.call_args.kwargs
    assert call_kwargs["agent_id"] == "revenue_minister"
    assert call_kwargs["session_id"] == "session:test_handoff"
    assert isinstance(call_kwargs["anchor"], TapeAnchor)

    # Step 5: Verify TapeView was indexed in vector store
    mock_vector_searcher.add_segments.assert_called_once()
    views = mock_vector_searcher.add_segments.call_args[0][0]
    assert len(views) == 1
    view = views[0]
    assert isinstance(view, TapeView)
    assert view.anchor_end_id == anchor.anchor_id
    assert view.session_id == "session:test_handoff"
    assert view.anchor_state == anchor.state


@pytest.mark.asyncio
async def test_memory_injected_event_format():
    """Test MEMORY_INJECTED event is properly formatted for LLM."""
    cm = ContextManager(
        session_id="s1",
        agent_id="a1",
        tape_path=MagicMock(spec=Path),
        config=ContextConfig(max_tokens=8000),
        llm_provider=AsyncMock(),
    )

    event = {
        "type": EventType.MEMORY_INJECTED,
        "payload": {
            "query": "直隶拨款记录",
            "source": "vector_search",
            "results": [
                {
                    "summary": "皇帝批准拨款5000两给直隶用于赈灾",
                    "tick_range": [5, 6],
                    "entities": ["直隶", "户部"],
                },
                {
                    "summary": "讨论税收调整方案",
                    "tick_range": [10, 12],
                    "entities": ["税收"],
                },
            ],
        },
    }

    messages = cm.event_to_messages(event)
    assert len(messages) == 1
    content = messages[0]["content"]
    assert "记忆回忆" in content
    assert "直隶拨款记录" in content
    assert "拨款5000两" in content
    assert "Tick 5-6" in content
    assert "直隶, 户部" in content


@pytest.mark.asyncio
async def test_handoff_with_empty_events_raises(context_manager):
    """Test execute_handoff raises on empty event list."""
    with pytest.raises(ValueError, match="Cannot handoff empty event list"):
        await context_manager.execute_handoff([], reason="test")


@pytest.mark.asyncio
async def test_handoff_entities_extraction(context_manager, mock_llm):
    """Test entity extraction during handoff."""
    # Reset side_effect: summary call returns something, entities returns entities
    mock_llm.call = AsyncMock(
        side_effect=[
            "讨论了拨款事宜",
            "直隶, 拨款, 户部",
        ]
    )

    events = [
        {"event_id": "e1", "type": "chat", "payload": {"message": "拨款给直隶"}, "tick": 5},
    ]

    anchor = await context_manager.execute_handoff(events, reason="test")
    assert "直隶" in anchor.state["entities"]
    assert "拨款" in anchor.state["entities"]
