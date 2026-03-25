"""Integration tests for task session Plan-Execute behavior."""

import asyncio
import json
from pathlib import Path

import pytest

from simu_emperor.agents.agent import Agent
from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.llm.mock import MockProvider
from simu_emperor.memory.tape_metadata import TapeMetadataManager
from simu_emperor.memory.tape_writer import TapeWriter
from simu_emperor.session.manager import SessionManager


@pytest.mark.asyncio
async def test_task_timeout_event_processed_while_waiting_reply(tmp_path: Path):
    """Agent in WAITING_REPLY should process TASK_TIMEOUT events."""
    from simu_emperor.config import settings

    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    original_memory_dir = settings.memory.memory_dir
    settings.memory.memory_dir = str(memory_dir)

    try:
        event_bus = EventBus()
        llm = MockProvider(response="超时已收到", tool_calls=[])
        tape_metadata_mgr = TapeMetadataManager(memory_dir=memory_dir)
        tape_writer = TapeWriter(memory_dir=memory_dir)
        session_manager = SessionManager(
            memory_dir=memory_dir,
            llm_provider=llm,
            tape_metadata_mgr=tape_metadata_mgr,
            tape_writer=tape_writer,
        )

        data_dir = tmp_path / "agent" / "test_agent"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "soul.md").write_text("# Test Soul\nYou are a test agent.", encoding="utf-8")
        (data_dir / "data_scope.yaml").write_text("query: []\n", encoding="utf-8")

        agent = Agent(
            agent_id="test_agent",
            event_bus=event_bus,
            llm_provider=llm,
            data_dir=data_dir,
            session_manager=session_manager,
            tape_writer=tape_writer,
            tape_metadata_mgr=tape_metadata_mgr,
        )

        main_session_id = "session:main"
        task_session_id = "task:test_agent:202603240001:abcd1234"
        await session_manager.create_session(
            session_id=main_session_id,
            created_by="player",
        )
        await session_manager.create_session(
            session_id=task_session_id,
            parent_id=main_session_id,
            created_by="agent:test_agent",
        )
        await session_manager.set_agent_state(task_session_id, "test_agent", "WAITING_REPLY")

        agent.start()
        timeout_event = Event(
            src="system:task_monitor",
            dst=["agent:test_agent"],
            type=EventType.TASK_TIMEOUT,
            payload={"task_session_id": task_session_id},
            session_id=task_session_id,
        )
        await event_bus.send_event(timeout_event)

        await asyncio.sleep(0.2)
        agent.stop()

        tape_path = memory_dir / "agents" / "test_agent" / "sessions" / task_session_id / "tape.jsonl"
        assert tape_path.exists()

        with open(tape_path, "r", encoding="utf-8") as f:
            tape_events = [json.loads(line) for line in f]

        assert any(event.get("type") == EventType.TASK_TIMEOUT for event in tape_events)
    finally:
        settings.memory.memory_dir = original_memory_dir
