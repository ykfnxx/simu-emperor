"""Integration tests for autonomous memory reflection flow"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from simu_emperor.agents.agent import Agent
from simu_emperor.agents.config import AgentConfig
from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.llm.mock import MockProvider


@pytest.fixture
def mock_event_bus():
    event_bus = MagicMock(spec=EventBus)
    event_bus.subscribe = MagicMock()
    event_bus.unsubscribe = MagicMock()
    event_bus.send_event = AsyncMock()
    return event_bus


@pytest.fixture
def mock_tape_metadata_mgr():
    mgr = MagicMock()
    mgr.append_or_update_entry = AsyncMock()
    return mgr


@pytest.fixture
def agent(mock_event_bus, mock_tape_metadata_mgr, tmp_path):
    """Create Agent with soul.md for integration testing"""
    soul_path = tmp_path / "soul.md"
    soul_path.write_text("# 李卫\n\n你是直隶巡抚李卫，性格刚直。\n", encoding="utf-8")

    return Agent(
        AgentConfig(
            agent_id="governor_zhili",
            event_bus=mock_event_bus,
            llm_provider=MockProvider(),
            data_dir=tmp_path,
            session_manager=None,
            tape_writer=MagicMock(),
            tape_metadata_mgr=mock_tape_metadata_mgr,
        )
    )


def make_tick_event(tick: int, session_id: str = "test_session") -> Event:
    return Event(
        src="system:tick_coordinator",
        dst=["*"],
        type=EventType.TICK_COMPLETED,
        payload={"tick": tick},
        session_id=session_id,
    )


class TestTickCounterIncrement:
    """Test that tick counter increments correctly through _on_event"""

    @pytest.mark.asyncio
    async def test_counter_increments_on_tick(self, agent, mock_tape_metadata_mgr):
        """Test that _memory_tick_counter increments on each TICK_COMPLETED"""
        with patch("simu_emperor.agents.agent.settings") as mock_settings:
            mock_settings.autonomous_memory.enabled = False  # Disable reflection
            mock_settings.autonomous_memory.check_interval_ticks = 4

            assert agent._memory_tick_counter == 0

            await agent._on_event(make_tick_event(1))
            assert agent._memory_tick_counter == 1

            await agent._on_event(make_tick_event(2))
            assert agent._memory_tick_counter == 2

            await agent._on_event(make_tick_event(3))
            assert agent._memory_tick_counter == 3

    @pytest.mark.asyncio
    async def test_reflection_triggered_at_interval(self, agent, mock_tape_metadata_mgr):
        """Test that LLM processing is triggered at the correct interval"""
        with patch("simu_emperor.agents.agent.settings") as mock_settings:
            mock_settings.autonomous_memory.enabled = True
            mock_settings.autonomous_memory.check_interval_ticks = 2
            mock_settings.memory.memory_dir = "data/memory"

            # Mock _react_loop.run to track calls (Phase 2: ReActLoop extracted)
            agent._react_loop.run = AsyncMock()
            agent._ensure_memory_components = AsyncMock()

            # Tick 1: counter becomes 1, 1 % 2 != 0 → no reflection
            await agent._on_event(make_tick_event(1))
            assert agent._memory_tick_counter == 1
            agent._react_loop.run.assert_not_called()

            # Tick 2: counter becomes 2, 2 % 2 == 0 → reflection!
            await agent._on_event(make_tick_event(2))
            assert agent._memory_tick_counter == 2
            agent._react_loop.run.assert_called_once()

            agent._react_loop.run.reset_mock()

            # Tick 3: counter becomes 3, 3 % 2 != 0 → no reflection
            await agent._on_event(make_tick_event(3))
            assert agent._memory_tick_counter == 3
            agent._react_loop.run.assert_not_called()

            # Tick 4: counter becomes 4, 4 % 2 == 0 → reflection!
            await agent._on_event(make_tick_event(4))
            assert agent._memory_tick_counter == 4
            agent._react_loop.run.assert_called_once()


class TestSoulEvolutionIntegration:
    """Test soul evolution through update_soul tool"""

    @pytest.mark.asyncio
    async def test_soul_updated_and_reloaded(self, agent, tmp_path):
        """Test that update_soul modifies soul.md and triggers reload"""
        tick_event = make_tick_event(8)
        original_soul = agent._soul

        result = await agent._action_tools.update_soul(
            {"content": "经历旱灾后变得更加关注民生"},
            tick_event,
        )

        assert "✅" in result

        # Verify soul.md was modified
        soul_content = (tmp_path / "soul.md").read_text(encoding="utf-8")
        assert "## 性格变化记录" in soul_content
        assert "经历旱灾后变得更加关注民生" in soul_content

        # Verify _load_soul was called (soul should be reloaded)
        assert agent._soul != original_soul
        assert "性格变化记录" in agent._soul


class TestLongTermMemoryIntegration:
    """Test long-term memory through write_long_term_memory tool"""

    @pytest.mark.asyncio
    async def test_memory_file_created(self, agent, tmp_path):
        """Test that MEMORY.md is created with correct content"""
        tick_event = make_tick_event(8)

        result = await agent._action_tools.write_long_term_memory(
            {"content": "直隶产值持续增长，库存充裕"},
            tick_event,
        )

        assert "✅" in result

        memory_file = tmp_path / "memory" / "MEMORY.md"
        assert memory_file.exists()
        content = memory_file.read_text(encoding="utf-8")
        assert "governor_zhili" in content
        assert "直隶产值持续增长" in content
