"""FileManager 单元测试。"""

from pathlib import Path

import pytest

from simu_emperor.agents.file_manager import FileManager


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[Path, Path, Path]:
    agent_base = tmp_path / "agent"
    template_base = tmp_path / "default_agents"
    skills_dir = tmp_path / "skills"
    agent_base.mkdir()
    template_base.mkdir()
    skills_dir.mkdir()
    return agent_base, template_base, skills_dir


@pytest.fixture
def fm(dirs: tuple[Path, Path, Path]) -> FileManager:
    return FileManager(*dirs)


@pytest.fixture
def setup_agent(dirs: tuple[Path, Path, Path]) -> str:
    """创建一个测试用 agent 目录结构。"""
    agent_base = dirs[0]
    agent_id = "test_agent"
    agent_dir = agent_base / agent_id
    agent_dir.mkdir()
    (agent_dir / "soul.md").write_text("# Test Agent", encoding="utf-8")
    (agent_dir / "data_scope.yaml").write_text(
        "display_name: Test\nskills:\n  query_data:\n    provinces: all\n    fields: []\n",
        encoding="utf-8",
    )
    (agent_dir / "memory").mkdir()
    (agent_dir / "memory" / "recent").mkdir()
    (agent_dir / "workspace").mkdir()
    return agent_id


class TestReadSoul:
    def test_read_soul(self, fm: FileManager, setup_agent: str) -> None:
        content = fm.read_soul(setup_agent)
        assert content == "# Test Agent"

    def test_read_soul_not_found(self, fm: FileManager) -> None:
        with pytest.raises(FileNotFoundError):
            fm.read_soul("nonexistent")


class TestReadDataScope:
    def test_read_data_scope_raw(self, fm: FileManager, setup_agent: str) -> None:
        raw = fm.read_data_scope_raw(setup_agent)
        assert raw["display_name"] == "Test"
        assert "skills" in raw


class TestReadSkill:
    def test_read_skill(self, fm: FileManager, dirs: tuple[Path, Path, Path]) -> None:
        skills_dir = dirs[2]
        (skills_dir / "query_data.md").write_text("# Query Data", encoding="utf-8")
        content = fm.read_skill("query_data")
        assert content == "# Query Data"

    def test_read_skill_not_found(self, fm: FileManager) -> None:
        with pytest.raises(FileNotFoundError):
            fm.read_skill("nonexistent")


class TestMemorySummary:
    def test_read_memory_summary_none(self, fm: FileManager, setup_agent: str) -> None:
        result = fm.read_memory_summary(setup_agent)
        assert result is None

    def test_write_and_read_memory_summary(self, fm: FileManager, setup_agent: str) -> None:
        fm.write_memory_summary(setup_agent, "Long term memory")
        result = fm.read_memory_summary(setup_agent)
        assert result == "Long term memory"


class TestRecentMemories:
    def test_list_recent_memories_empty(self, fm: FileManager, setup_agent: str) -> None:
        result = fm.list_recent_memories(setup_agent)
        assert result == []

    def test_write_and_list_recent_memories(self, fm: FileManager, setup_agent: str) -> None:
        fm.write_recent_memory(setup_agent, 1, "Turn 1 memory")
        fm.write_recent_memory(setup_agent, 3, "Turn 3 memory")
        fm.write_recent_memory(setup_agent, 2, "Turn 2 memory")

        result = fm.list_recent_memories(setup_agent)
        assert len(result) == 3
        assert result[0] == (1, "Turn 1 memory")
        assert result[1] == (2, "Turn 2 memory")
        assert result[2] == (3, "Turn 3 memory")

    def test_delete_recent_memory(self, fm: FileManager, setup_agent: str) -> None:
        fm.write_recent_memory(setup_agent, 5, "Turn 5")
        fm.delete_recent_memory(setup_agent, 5)
        result = fm.list_recent_memories(setup_agent)
        assert result == []

    def test_delete_recent_memory_nonexistent(self, fm: FileManager, setup_agent: str) -> None:
        # Should not raise
        fm.delete_recent_memory(setup_agent, 999)

    def test_recent_memory_file_naming(self, fm: FileManager, setup_agent: str) -> None:
        fm.write_recent_memory(setup_agent, 6, "content")
        path = fm.agent_dir(setup_agent) / "memory" / "recent" / "turn_006.md"
        assert path.exists()


class TestWorkspace:
    def test_list_workspace_files_empty(self, fm: FileManager, setup_agent: str) -> None:
        result = fm.list_workspace_files(setup_agent)
        assert result == []

    def test_write_and_read_workspace_file(self, fm: FileManager, setup_agent: str) -> None:
        fm.write_workspace_file(setup_agent, "001_report.md", "Report content")
        content = fm.read_workspace_file(setup_agent, "001_report.md")
        assert content == "Report content"

    def test_list_workspace_files_sorted(self, fm: FileManager, setup_agent: str) -> None:
        fm.write_workspace_file(setup_agent, "003_report.md", "c")
        fm.write_workspace_file(setup_agent, "001_report.md", "a")
        fm.write_workspace_file(setup_agent, "002_exec_tax.md", "b")
        result = fm.list_workspace_files(setup_agent)
        assert result == ["001_report.md", "002_exec_tax.md", "003_report.md"]


class TestDirectoryOps:
    def test_agent_dir(self, fm: FileManager) -> None:
        path = fm.agent_dir("some_agent")
        assert path.name == "some_agent"

    def test_list_agents(self, fm: FileManager, setup_agent: str) -> None:
        agents = fm.list_agents()
        assert setup_agent in agents

    def test_list_agents_empty(self, fm: FileManager) -> None:
        agents = fm.list_agents()
        assert agents == []

    def test_list_templates(self, fm: FileManager, dirs: tuple[Path, Path, Path]) -> None:
        template_base = dirs[1]
        tmpl = template_base / "my_template"
        tmpl.mkdir()
        (tmpl / "soul.md").write_text("template soul", encoding="utf-8")
        templates = fm.list_templates()
        assert "my_template" in templates

    def test_ensure_agent_dirs(self, fm: FileManager, setup_agent: str) -> None:
        fm.ensure_agent_dirs(setup_agent)
        agent = fm.agent_dir(setup_agent)
        assert (agent / "memory" / "recent").is_dir()
        assert (agent / "workspace").is_dir()

    def test_agent_exists(self, fm: FileManager, setup_agent: str) -> None:
        assert fm.agent_exists(setup_agent)
        assert not fm.agent_exists("nonexistent")
