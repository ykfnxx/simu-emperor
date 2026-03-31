"""Tests for _should_do_memory_reflection logic in Agent"""

import pytest
from unittest.mock import MagicMock, patch

from simu_emperor.agents.agent import Agent
from simu_emperor.agents.config import AgentConfig
from simu_emperor.event_bus.core import EventBus
from simu_emperor.llm.mock import MockProvider


@pytest.fixture
def mock_event_bus():
    event_bus = MagicMock(spec=EventBus)
    event_bus.subscribe = MagicMock()
    event_bus.unsubscribe = MagicMock()
    return event_bus


@pytest.fixture
def agent(mock_event_bus, tmp_path):
    """Create Agent with minimal setup"""
    soul_path = tmp_path / "soul.md"
    soul_path.write_text("# Test Agent\n", encoding="utf-8")

    return Agent(
        AgentConfig(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            llm_provider=MockProvider(),
            data_dir=tmp_path,
            session_manager=None,
            tape_writer=MagicMock(),
            tape_metadata_mgr=MagicMock(),
        )
    )


class TestShouldDoMemoryReflection:
    """Test _should_do_memory_reflection interval logic"""

    def test_triggers_at_interval(self, agent):
        """Test reflection triggers at check_interval_ticks"""
        with patch("simu_emperor.agents.agent.settings") as mock_settings:
            mock_settings.autonomous_memory.enabled = True
            mock_settings.autonomous_memory.check_interval_ticks = 4

            # Counter at 0 → 0 % 4 == 0 → True
            agent._memory_tick_counter = 0
            assert agent._should_do_memory_reflection() is True

            # Counter at 1 → 1 % 4 != 0 → False
            agent._memory_tick_counter = 1
            assert agent._should_do_memory_reflection() is False

            # Counter at 4 → 4 % 4 == 0 → True
            agent._memory_tick_counter = 4
            assert agent._should_do_memory_reflection() is True

            # Counter at 7 → 7 % 4 != 0 → False
            agent._memory_tick_counter = 7
            assert agent._should_do_memory_reflection() is False

            # Counter at 8 → 8 % 4 == 0 → True
            agent._memory_tick_counter = 8
            assert agent._should_do_memory_reflection() is True

    def test_disabled_returns_false(self, agent):
        """Test that disabled config always returns False"""
        with patch("simu_emperor.agents.agent.settings") as mock_settings:
            mock_settings.autonomous_memory.enabled = False
            mock_settings.autonomous_memory.check_interval_ticks = 4

            agent._memory_tick_counter = 4
            assert agent._should_do_memory_reflection() is False

    def test_interval_of_one(self, agent):
        """Test that interval=1 triggers every tick"""
        with patch("simu_emperor.agents.agent.settings") as mock_settings:
            mock_settings.autonomous_memory.enabled = True
            mock_settings.autonomous_memory.check_interval_ticks = 1

            for i in range(5):
                agent._memory_tick_counter = i
                assert agent._should_do_memory_reflection() is True

    def test_counter_initialized_to_zero(self, agent):
        """Test that counter starts at 0"""
        assert agent._memory_tick_counter == 0
