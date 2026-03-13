"""Test that task_created events are written to tape."""

import asyncio
import json
from pathlib import Path

import pytest

from simu_emperor.agents.agent import Agent
from simu_emperor.config import settings
from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.llm.mock import MockProvider
from simu_emperor.session.manager import SessionManager
from simu_emperor.memory.manifest_index import ManifestIndex
from simu_emperor.memory.tape_writer import TapeWriter


@pytest.mark.asyncio
async def test_task_created_event_written_to_tape(tmp_path: Path):
    """Test that TASK_CREATED events are written to tape."""
    # Setup - use settings.memory.memory_dir as the base since Agent uses that
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    # Mock the settings to use our test directory
    original_memory_dir = settings.memory.memory_dir
    settings.memory.memory_dir = str(memory_dir)

    try:
        event_bus = EventBus()

        mock_llm = MockProvider(response="Test response", tool_calls=None)
        manifest_index = ManifestIndex(memory_dir=memory_dir)
        tape_writer = TapeWriter(memory_dir=memory_dir)

        session_manager = SessionManager(
            memory_dir=memory_dir,
            llm_provider=mock_llm,
            manifest_index=manifest_index,
            tape_writer=tape_writer,
        )

        data_dir = tmp_path / "agents" / "test_agent"
        data_dir.mkdir(parents=True, exist_ok=True)

        # Create agent - will now use settings.memory.memory_dir
        agent_llm = MockProvider(response="Test response", tool_calls=None)
        agent = Agent(
            agent_id="test_agent",
            event_bus=event_bus,
            llm_provider=agent_llm,
            data_dir=data_dir,
            session_manager=session_manager,
        )

        # Create a main session
        main_session_id = "main:session:test"
        await session_manager.create_session(
            session_id=main_session_id,
            parent_id=None,
            created_by="player",
        )

        # Create task session
        task_session_id = "task:test_agent:20260313120000:abc12345"
        await session_manager.create_session(
            session_id=task_session_id,
            parent_id=main_session_id,
            created_by="agent:test_agent",
        )

        agent.start()

        # Send TASK_CREATED event
        task_created_event = Event(
            src="agent:test_agent",
            dst=["agent:test_agent"],
            type=EventType.TASK_CREATED,
            payload={
                "task_session_id": task_session_id,
                "parent_session_id": main_session_id,
                "description": "Test task",
            },
            session_id=task_session_id,
        )

        print(f"\n=== Sending TASK_CREATED event ===")
        print(f"  session_id: {task_created_event.session_id}")

        await event_bus.send_event(task_created_event)

        # Wait for event to be processed
        await asyncio.sleep(1.0)

        agent.stop()

        # Check tape file
        tape_path = memory_dir / "agents" / "test_agent" / "sessions" / task_session_id / "tape.jsonl"

        print(f"\n=== Tape path: {tape_path} ===")
        print(f"Tape exists: {tape_path.exists()}")

        if tape_path.exists():
            with open(tape_path, "r") as f:
                events = [json.loads(line) for line in f]

            print(f"\n=== Tape contains {len(events)} events ===")
            for i, event in enumerate(events):
                print(f"  [{i}] type={event['type']}, event_id={event.get('event_id', 'N/A')}")

            # Check for task_created event
            task_created_events = [e for e in events if e["type"] == "task_created"]
            print(f"\n=== Found {len(task_created_events)} task_created events ===")

            assert len(task_created_events) > 0, "task_created event should be written to tape"
        else:
            print(f"\n=== Tape file does not exist! ===")
            print(f"Expected path: {tape_path}")
            print(f"Parent directory exists: {tape_path.parent.exists()}")
            assert False, "Tape file should exist"

    finally:
        # Restore original memory_dir setting
        settings.memory.memory_dir = original_memory_dir
