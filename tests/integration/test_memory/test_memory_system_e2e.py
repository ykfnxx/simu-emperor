"""End-to-end test for V3 memory system in Agent."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.agents.agent import Agent
from simu_emperor.agents.config import AgentConfig
from simu_emperor.llm.mock import MockProvider
from simu_emperor.config import MemoryConfig
from simu_emperor.memory.tape_writer import TapeWriter
from simu_emperor.memory.tape_metadata import TapeMetadataManager


class TestMemorySystemE2E:
    """End-to-end tests for memory system integration"""

    @pytest.mark.asyncio
    async def test_memory_system_creates_files_on_query(self, tmp_path, monkeypatch):
        """Test that memory system creates files when agent receives a query"""
        # Setup: Create required agent files
        # Agent expects data_dir to be the agent-specific directory (e.g., data/agent/revenue_minister)
        data_dir = tmp_path / "data"
        agent_dir = data_dir / "test_agent"
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Create soul.md and data_scope.yaml in the agent directory
        (agent_dir / "soul.md").write_text("# Test Agent\nYou are a test agent.\n")
        (agent_dir / "data_scope.yaml").write_text("query_data:\n  allow: []\n")

        # Patch memory config to use tmp_path
        test_memory_dir = tmp_path / "data" / "memory"
        test_memory_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "simu_emperor.config.settings.memory",
            MemoryConfig(enabled=True, memory_dir=str(test_memory_dir)),
        )

        event_bus = EventBus()
        llm = MockProvider(response="这是测试响应")

        # Create mock session_manager with proper async methods
        mock_session_manager = MagicMock()
        mock_session_manager.get_session = AsyncMock(return_value=None)
        mock_session_manager.get_agent_state = AsyncMock(return_value="ACTIVE")
        mock_session_manager.set_agent_state = AsyncMock()

        # Create TapeWriter and TapeMetadataManager for V4 memory system
        # Note: memory_dir must be a Path object for TapeWriter
        tape_writer = TapeWriter(memory_dir=test_memory_dir)
        tape_metadata_mgr = TapeMetadataManager(memory_dir=test_memory_dir)

        # Pass agent_dir as data_dir (Agent expects agent-specific directory)
        agent = Agent(
            AgentConfig(
                agent_id="test_agent",
                event_bus=event_bus,
                llm_provider=llm,
                data_dir=agent_dir,  # Changed from data_dir to agent_dir
                session_id="test_session",
                session_manager=mock_session_manager,
                tape_writer=tape_writer,
                tape_metadata_mgr=tape_metadata_mgr,
            )
        )
        agent.start()

        # Create a query event (should trigger TapeWriter)
        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.USER_QUERY,
            payload={"query": "测试查询"},
            session_id="test_session",
        )

        # Process event
        await agent._on_event(event)

        # Verify memory files were created
        memory_dir = tmp_path / "data" / "memory"
        agents_dir = memory_dir / "agents" / "test_agent"
        session_dir = agents_dir / "sessions" / "test_session"
        tape_file = session_dir / "tape.jsonl"

        assert memory_dir.exists(), f"Memory directory not created: {memory_dir}"
        assert agents_dir.exists(), f"Agents directory not created: {agents_dir}"
        assert session_dir.exists(), f"Session directory not created: {session_dir}"
        assert tape_file.exists(), f"Tape file not created: {tape_file}"

        # Verify tape.jsonl has content
        content = tape_file.read_text()
        assert len(content) > 0, "Tape file is empty"
        assert "user_query" in content, "User query event not found in tape"

        print("✅ Memory files created successfully!")
        print(f"   Tape file: {tape_file}")

        # Cleanup
        agent.stop()
