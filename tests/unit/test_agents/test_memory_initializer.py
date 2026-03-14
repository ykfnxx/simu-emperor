"""Tests for MemoryInitializer（V4 更新：移除 manifest 测试）"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from simu_emperor.agents.memory_initializer import MemoryInitializer
from simu_emperor.llm.mock import MockProvider


@pytest.mark.asyncio
async def test_initialize_creates_components(tmp_path):
    """测试初始化创建所有必要组件"""
    llm = MockProvider()
    # V4.1: 创建 mock tape_writer
    tape_writer = AsyncMock()
    tape_writer._get_tape_path = MagicMock(return_value=tmp_path / "tape.jsonl")

    initializer = MemoryInitializer(
        agent_id="test_agent",
        memory_dir=tmp_path,
        llm_provider=llm,
        tape_writer=tape_writer,
    )

    context_manager, memory_tools = await initializer.initialize(session_id="test_session", turn=1)

    assert context_manager is not None
    assert memory_tools is not None
    assert context_manager.session_id == "test_session"
    assert context_manager.agent_id == "test_agent"


@pytest.mark.asyncio
async def test_initialize_with_tape_metadata_mgr(tmp_path):
    """测试初始化使用 TapeMetadataManager（V4 新测试）"""
    from simu_emperor.memory.tape_metadata import TapeMetadataManager

    llm = MockProvider()
    tape_metadata_mgr = TapeMetadataManager(memory_dir=tmp_path)
    # V4.1: 创建 mock tape_writer
    tape_writer = AsyncMock()
    tape_writer._get_tape_path = MagicMock(return_value=tmp_path / "tape.jsonl")

    initializer = MemoryInitializer(
        agent_id="test_agent",
        memory_dir=tmp_path,
        llm_provider=llm,
        tape_writer=tape_writer,
        tape_metadata_mgr=tape_metadata_mgr,
    )

    context_manager, memory_tools = await initializer.initialize(session_id="test_session", turn=5)

    # V4: tape_meta.jsonl 不会在 initialize() 时自动创建
    # 它会在首次事件写入时或 TICK_COMPLETED 时创建
    metadata_path = tmp_path / "agents" / "test_agent" / "tape_meta.jsonl"
    assert not metadata_path.exists()

    # 调用 append_or_update_entry 创建元数据条目（模拟 TICK_COMPLETED）
    await tape_metadata_mgr.append_or_update_entry(
        agent_id="test_agent",
        session_id="test_session",
        first_event=None,
        llm=llm,
        current_tick=5,
    )

    # 验证 tape_meta.jsonl 被创建
    assert metadata_path.exists()

    # 验证 entry 被创建
    entries = await tape_metadata_mgr.get_all_entries("test_agent")
    assert len(entries) == 1
    assert entries[0].session_id == "test_session"


@pytest.mark.asyncio
async def test_initialize_loads_from_tape(tmp_path):
    """测试初始化从tape加载历史事件"""
    llm = MockProvider()
    tape_writer = AsyncMock()
    tape_writer._get_tape_path = MagicMock(return_value=tmp_path / "tape.jsonl")

    initializer = MemoryInitializer(
        agent_id="test_agent",
        memory_dir=tmp_path,
        llm_provider=llm,
        tape_writer=tape_writer,
    )

    # 首先初始化创建tape
    await initializer.initialize(session_id="test_session", turn=1)

    # 再次初始化应该从tape加载
    context_manager, memory_tools = await initializer.initialize(session_id="test_session", turn=2)

    assert context_manager is not None
    assert memory_tools is not None


@pytest.mark.asyncio
async def test_initialize_handles_missing_tape(tmp_path):
    """测试初始化处理不存在的tape文件"""
    llm = MockProvider()
    tape_writer = AsyncMock()
    tape_writer._get_tape_path = MagicMock(return_value=tmp_path / "tape.jsonl")

    initializer = MemoryInitializer(
        agent_id="test_agent",
        memory_dir=tmp_path,
        llm_provider=llm,
        tape_writer=tape_writer,
    )

    # 初始化一个不存在的session应该正常工作
    context_manager, memory_tools = await initializer.initialize(
        session_id="nonexistent_session", turn=1
    )

    assert context_manager is not None
    assert memory_tools is not None
    # 没有历史事件，events列表应该为空
    assert len(context_manager.events) == 0
