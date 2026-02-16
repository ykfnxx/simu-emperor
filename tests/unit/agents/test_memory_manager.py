"""MemoryManager 单元测试。"""

from pathlib import Path

import pytest

from simu_emperor.agents.file_manager import FileManager
from simu_emperor.agents.memory_manager import RECENT_MEMORY_WINDOW, MemoryContext, MemoryManager


@pytest.fixture
def fm(tmp_path: Path) -> FileManager:
    agent_base = tmp_path / "agent"
    template_base = tmp_path / "default_agents"
    skills_dir = tmp_path / "skills"
    agent_base.mkdir()
    template_base.mkdir()
    skills_dir.mkdir()
    return FileManager(agent_base, template_base, skills_dir)


@pytest.fixture
def mm(fm: FileManager) -> MemoryManager:
    return MemoryManager(fm)


@pytest.fixture
def agent_id(fm: FileManager) -> str:
    aid = "test_agent"
    agent_dir = fm.agent_base / aid
    agent_dir.mkdir()
    (agent_dir / "soul.md").write_text("# Test", encoding="utf-8")
    fm.ensure_agent_dirs(aid)
    return aid


class TestReadContext:
    def test_empty_context(self, mm: MemoryManager, agent_id: str) -> None:
        ctx = mm.read_context(agent_id)
        assert ctx.summary is None
        assert ctx.recent == []

    def test_with_summary_only(self, mm: MemoryManager, agent_id: str) -> None:
        mm.update_summary(agent_id, "Summary content")
        ctx = mm.read_context(agent_id)
        assert ctx.summary == "Summary content"
        assert ctx.recent == []

    def test_with_summary_and_recent(self, mm: MemoryManager, agent_id: str) -> None:
        mm.update_summary(agent_id, "Summary")
        mm.write_recent(agent_id, 1, "Turn 1")
        mm.write_recent(agent_id, 2, "Turn 2")
        ctx = mm.read_context(agent_id)
        assert ctx.summary == "Summary"
        assert len(ctx.recent) == 2
        assert ctx.recent[0] == (1, "Turn 1")
        assert ctx.recent[1] == (2, "Turn 2")


class TestWriteRecent:
    def test_write_single(self, mm: MemoryManager, agent_id: str) -> None:
        mm.write_recent(agent_id, 1, "Turn 1 content")
        ctx = mm.read_context(agent_id)
        assert ctx.recent == [(1, "Turn 1 content")]

    def test_window_cleanup(self, mm: MemoryManager, agent_id: str) -> None:
        """写入 turn 4 时应删除 turn 1。"""
        mm.write_recent(agent_id, 1, "Turn 1")
        mm.write_recent(agent_id, 2, "Turn 2")
        mm.write_recent(agent_id, 3, "Turn 3")
        mm.write_recent(agent_id, 4, "Turn 4")

        ctx = mm.read_context(agent_id)
        turns = [t for t, _ in ctx.recent]
        assert 1 not in turns
        assert turns == [2, 3, 4]

    def test_window_cleanup_sequential(self, mm: MemoryManager, agent_id: str) -> None:
        """连续写入多个回合，验证窗口始终保持 3 回合。"""
        for turn in range(1, 7):
            mm.write_recent(agent_id, turn, f"Turn {turn}")

        ctx = mm.read_context(agent_id)
        turns = [t for t, _ in ctx.recent]
        assert turns == [4, 5, 6]

    def test_no_cleanup_for_early_turns(self, mm: MemoryManager, agent_id: str) -> None:
        """前 3 回合不应删除任何记忆。"""
        mm.write_recent(agent_id, 1, "Turn 1")
        mm.write_recent(agent_id, 2, "Turn 2")
        mm.write_recent(agent_id, 3, "Turn 3")

        ctx = mm.read_context(agent_id)
        assert len(ctx.recent) == 3

    def test_cleanup_nonexistent_turn(self, mm: MemoryManager, agent_id: str) -> None:
        """删除不存在的旧回合不应报错。"""
        mm.write_recent(agent_id, 10, "Turn 10")
        ctx = mm.read_context(agent_id)
        assert ctx.recent == [(10, "Turn 10")]


class TestUpdateSummary:
    def test_update_summary(self, mm: MemoryManager, agent_id: str) -> None:
        mm.update_summary(agent_id, "First summary")
        assert mm.read_context(agent_id).summary == "First summary"

        mm.update_summary(agent_id, "Updated summary")
        assert mm.read_context(agent_id).summary == "Updated summary"


class TestConstants:
    def test_window_size(self) -> None:
        assert RECENT_MEMORY_WINDOW == 3

    def test_memory_context_defaults(self) -> None:
        ctx = MemoryContext()
        assert ctx.summary is None
        assert ctx.recent == []
