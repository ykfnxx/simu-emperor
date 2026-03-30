"""Unit tests for MEMORY_INJECTED event formatting."""

from simu_emperor.memory.context_manager import ContextManager, ContextConfig
from simu_emperor.event_bus.event_types import EventType
from unittest.mock import AsyncMock, MagicMock


def test_memory_injected_event_formatting():
    config = ContextConfig()
    cm = ContextManager(
        session_id="s1",
        agent_id="a1",
        tape_path=MagicMock(),
        config=config,
        llm_provider=AsyncMock(),
    )
    event = {
        "type": EventType.MEMORY_INJECTED,
        "payload": {
            "query": "拨款记录",
            "source": "vector_search",
            "results": [
                {"summary": "直隶拨款5000两", "tick_range": [10, 12], "entities": ["直隶", "国库"]},
            ],
        },
    }
    messages = cm.event_to_messages(event)
    assert len(messages) == 1
    assert "记忆回忆" in messages[0]["content"]
    assert "拨款记录" in messages[0]["content"]
    assert "直隶拨款5000两" in messages[0]["content"]
