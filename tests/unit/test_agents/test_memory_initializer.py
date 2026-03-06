"""Tests for MemoryInitializer"""

import pytest
from pathlib import Path
from simu_emperor.agents.memory_initializer import MemoryInitializer
from simu_emperor.llm.mock import MockProvider


@pytest.mark.asyncio
async def test_initialize_creates_components(tmp_path):
    """测试初始化创建所有必要组件"""
    llm = MockProvider()
    initializer = MemoryInitializer(
        agent_id="test_agent",
        memory_dir=tmp_path,
        llm_provider=llm,
    )

    context_manager, memory_tools = await initializer.initialize(session_id="test_session", turn=1)

    assert context_manager is not None
    assert memory_tools is not None
    assert context_manager.session_id == "test_session"
    assert context_manager.agent_id == "test_agent"


@pytest.mark.asyncio
async def test_initialize_registers_session(tmp_path):
    """测试初始化注册session到manifest"""
    llm = MockProvider()
    initializer = MemoryInitializer(
        agent_id="test_agent",
        memory_dir=tmp_path,
        llm_provider=llm,
    )

    await initializer.initialize(session_id="test_session", turn=5)

    # 验证manifest.json被创建
    manifest_path = tmp_path / "manifest.json"
    assert manifest_path.exists()

    # 验证session被注册
    from simu_emperor.common import FileOperationsHelper

    manifest = await FileOperationsHelper.read_json_file(manifest_path)
    assert manifest is not None
    assert "test_session" in manifest["sessions"]
    assert "test_agent" in manifest["sessions"]["test_session"]["agents"]


@pytest.mark.asyncio
async def test_initialize_loads_from_tape(tmp_path):
    """测试初始化从tape加载历史事件"""
    llm = MockProvider()
    initializer = MemoryInitializer(
        agent_id="test_agent",
        memory_dir=tmp_path,
        llm_provider=llm,
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
    initializer = MemoryInitializer(
        agent_id="test_agent",
        memory_dir=tmp_path,
        llm_provider=llm,
    )

    # 初始化一个不存在的session应该正常工作
    context_manager, memory_tools = await initializer.initialize(
        session_id="nonexistent_session", turn=1
    )

    assert context_manager is not None
    assert memory_tools is not None
    # 没有历史事件，events列表应该为空
    assert len(context_manager.events) == 0
