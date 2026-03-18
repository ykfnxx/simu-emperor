"""Tests for autonomous memory tools: write_long_term_memory, update_soul"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from simu_emperor.agents.tools.action_tools import ActionTools
from simu_emperor.event_bus.event import Event


@pytest.fixture
def mock_event_bus():
    """Mock EventBus"""
    event_bus = MagicMock()
    event_bus.send_event = AsyncMock()
    return event_bus


@pytest.fixture
def sample_tick_event():
    """Create sample TICK_COMPLETED Event"""
    return Event(
        src="system:tick_coordinator",
        dst=["*"],
        type="tick_completed",
        payload={"tick": 8},
        session_id="test_session",
    )


class TestWriteLongTermMemory:
    """Test write_long_term_memory method"""

    @pytest.fixture
    def action_tools(self, mock_event_bus, tmp_path):
        return ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
        )

    @pytest.mark.asyncio
    async def test_creates_memory_file(self, action_tools, sample_tick_event, tmp_path):
        """Test that MEMORY.md is created when it doesn't exist"""
        result = await action_tools.write_long_term_memory(
            {"content": "直隶产值持续增长"},
            sample_tick_event,
        )

        assert "✅" in result
        memory_file = tmp_path / "memory" / "MEMORY.md"
        assert memory_file.exists()
        content = memory_file.read_text(encoding="utf-8")
        assert "# test_agent 长期记忆" in content
        assert "## Tick 8" in content
        assert "直隶产值持续增长" in content

    @pytest.mark.asyncio
    async def test_appends_to_existing(self, action_tools, sample_tick_event, tmp_path):
        """Test that new entries are appended to existing MEMORY.md"""
        # Write first entry
        await action_tools.write_long_term_memory(
            {"content": "第一条记忆"},
            sample_tick_event,
        )

        # Write second entry with different tick
        event2 = Event(
            src="system:tick_coordinator",
            dst=["*"],
            type="tick_completed",
            payload={"tick": 12},
            session_id="test_session",
        )
        await action_tools.write_long_term_memory(
            {"content": "第二条记忆"},
            event2,
        )

        content = (tmp_path / "memory" / "MEMORY.md").read_text(encoding="utf-8")
        assert "第一条记忆" in content
        assert "第二条记忆" in content
        assert "## Tick 8" in content
        assert "## Tick 12" in content

    @pytest.mark.asyncio
    async def test_rejects_empty_content(self, action_tools, sample_tick_event):
        """Test that empty content is rejected"""
        result = await action_tools.write_long_term_memory(
            {"content": ""},
            sample_tick_event,
        )
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_rejects_whitespace_content(self, action_tools, sample_tick_event):
        """Test that whitespace-only content is rejected"""
        result = await action_tools.write_long_term_memory(
            {"content": "   \n  "},
            sample_tick_event,
        )
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_format_includes_timestamp(self, action_tools, sample_tick_event, tmp_path):
        """Test that entries include timestamp"""
        await action_tools.write_long_term_memory(
            {"content": "测试记忆"},
            sample_tick_event,
        )

        content = (tmp_path / "memory" / "MEMORY.md").read_text(encoding="utf-8")
        # Format: ## Tick 8 - 2026-03-18 12:00
        assert "## Tick 8 - " in content


class TestUpdateSoul:
    """Test update_soul method"""

    @pytest.fixture
    def action_tools_with_soul(self, mock_event_bus, tmp_path):
        # Create a soul.md file
        soul_path = tmp_path / "soul.md"
        soul_path.write_text("# 李卫\n\n你是直隶巡抚李卫。\n", encoding="utf-8")
        return ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
        )

    @pytest.mark.asyncio
    async def test_creates_evolution_section(self, action_tools_with_soul, sample_tick_event, tmp_path):
        """Test that 性格变化记录 section is created"""
        result = await action_tools_with_soul.update_soul(
            {"content": "经历斥责后变得谨慎"},
            sample_tick_event,
        )

        assert "✅" in result
        content = (tmp_path / "soul.md").read_text(encoding="utf-8")
        assert "## 性格变化记录" in content
        assert "### Tick 8" in content
        assert "经历斥责后变得谨慎" in content

    @pytest.mark.asyncio
    async def test_preserves_original_content(self, action_tools_with_soul, sample_tick_event, tmp_path):
        """Test that original soul.md content is preserved"""
        await action_tools_with_soul.update_soul(
            {"content": "性格变化"},
            sample_tick_event,
        )

        content = (tmp_path / "soul.md").read_text(encoding="utf-8")
        assert "# 李卫" in content
        assert "你是直隶巡抚李卫。" in content

    @pytest.mark.asyncio
    async def test_appends_to_existing_section(self, action_tools_with_soul, sample_tick_event, tmp_path):
        """Test that multiple entries append under the same section"""
        await action_tools_with_soul.update_soul(
            {"content": "第一次变化"},
            sample_tick_event,
        )

        event2 = Event(
            src="system:tick_coordinator",
            dst=["*"],
            type="tick_completed",
            payload={"tick": 16},
            session_id="test_session",
        )
        await action_tools_with_soul.update_soul(
            {"content": "第二次变化"},
            event2,
        )

        content = (tmp_path / "soul.md").read_text(encoding="utf-8")
        # Section header should appear only once
        assert content.count("## 性格变化记录") == 1
        assert "### Tick 8" in content
        assert "### Tick 16" in content
        assert "第一次变化" in content
        assert "第二次变化" in content

    @pytest.mark.asyncio
    async def test_rejects_empty_content(self, action_tools_with_soul, sample_tick_event):
        """Test that empty content is rejected"""
        result = await action_tools_with_soul.update_soul(
            {"content": ""},
            sample_tick_event,
        )
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_rejects_missing_soul_file(self, mock_event_bus, tmp_path, sample_tick_event):
        """Test that missing soul.md returns error"""
        tools = ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
        )
        result = await tools.update_soul(
            {"content": "变化"},
            sample_tick_event,
        )
        assert "❌" in result
        assert "soul.md 不存在" in result

    @pytest.mark.asyncio
    async def test_triggers_callback(self, mock_event_bus, tmp_path, sample_tick_event):
        """Test that on_soul_updated callback is triggered"""
        soul_path = tmp_path / "soul.md"
        soul_path.write_text("# Test Soul\n", encoding="utf-8")

        callback = MagicMock()
        tools = ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
            on_soul_updated=callback,
        )

        await tools.update_soul(
            {"content": "性格变化"},
            sample_tick_event,
        )

        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_callback_when_not_set(self, action_tools_with_soul, sample_tick_event):
        """Test that no error when callback is not set"""
        # action_tools_with_soul has no callback set
        result = await action_tools_with_soul.update_soul(
            {"content": "性格变化"},
            sample_tick_event,
        )
        assert "✅" in result
