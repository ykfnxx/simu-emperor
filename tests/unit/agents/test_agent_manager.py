"""AgentManager 单元测试。"""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from simu_emperor.agents.agent_manager import AgentManager
from simu_emperor.agents.file_manager import FileManager


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    agent_base = tmp_path / "agent"
    template_base = tmp_path / "default_agents"
    skills_dir = tmp_path / "skills"
    saves_dir = tmp_path / "saves"
    agent_base.mkdir()
    template_base.mkdir()
    skills_dir.mkdir()
    saves_dir.mkdir()
    return agent_base, template_base, skills_dir, saves_dir


@pytest.fixture
def fm(dirs: tuple[Path, Path, Path, Path]) -> FileManager:
    return FileManager(dirs[0], dirs[1], dirs[2])


@pytest.fixture
def am(fm: FileManager, dirs: tuple[Path, Path, Path, Path]) -> AgentManager:
    return AgentManager(fm, saves_dir=dirs[3])


@pytest.fixture
def setup_templates(dirs: tuple[Path, Path, Path, Path]) -> None:
    """创建模板 agent 目录。"""
    template_base = dirs[1]
    for name in ["agent_a", "agent_b"]:
        d = template_base / name
        d.mkdir()
        (d / "soul.md").write_text(f"# {name} soul", encoding="utf-8")
        (d / "data_scope.yaml").write_text(
            f"display_name: {name}\nskills:\n  query_data:\n    provinces: all\n    fields: []\n",
            encoding="utf-8",
        )


class TestInitializeGame:
    def test_initialize_from_templates(self, am: AgentManager, setup_templates: None) -> None:
        agents = am.initialize_game()
        assert "agent_a" in agents
        assert "agent_b" in agents

    def test_initialize_creates_dirs(
        self, am: AgentManager, fm: FileManager, setup_templates: None
    ) -> None:
        am.initialize_game()
        for agent_id in ["agent_a", "agent_b"]:
            agent_dir = fm.agent_dir(agent_id)
            assert (agent_dir / "memory" / "recent").is_dir()
            assert (agent_dir / "workspace").is_dir()

    def test_initialize_clears_existing(
        self, am: AgentManager, fm: FileManager, setup_templates: None
    ) -> None:
        # 先初始化一次
        am.initialize_game()
        # 写入一些数据
        fm.write_workspace_file("agent_a", "test.md", "data")
        # 再次初始化应清空
        am.initialize_game()
        assert fm.list_workspace_files("agent_a") == []

    def test_initialize_ignores_non_agent_dirs(
        self,
        am: AgentManager,
        dirs: tuple[Path, Path, Path, Path],
        setup_templates: None,
    ) -> None:
        # 创建一个没有 soul.md 的目录
        (dirs[1] / "not_an_agent").mkdir()
        agents = am.initialize_game()
        assert "not_an_agent" not in agents


class TestAddRemoveAgent:
    def test_add_agent(self, am: AgentManager, fm: FileManager) -> None:
        am.add_agent("new_agent", "# New Soul", "display_name: New\nskills: {}\n")
        assert fm.agent_exists("new_agent")
        assert fm.read_soul("new_agent") == "# New Soul"

    def test_remove_agent(self, am: AgentManager, fm: FileManager, setup_templates: None) -> None:
        am.initialize_game()
        am.remove_agent("agent_a")
        active = am.list_active_agents()
        assert "agent_a" not in active
        assert "agent_b" in active

    def test_remove_nonexistent(self, am: AgentManager) -> None:
        # Should not raise
        am.remove_agent("nonexistent")

    def test_remove_idempotent(self, am: AgentManager, setup_templates: None) -> None:
        am.initialize_game()
        am.remove_agent("agent_a")
        am.remove_agent("agent_a")  # 不应重复追加
        soul = am.file_manager.read_soul("agent_a")
        assert soul.count("已被罢免") == 1


class TestListActiveAgents:
    def test_list_active(self, am: AgentManager, setup_templates: None) -> None:
        am.initialize_game()
        active = am.list_active_agents()
        assert sorted(active) == ["agent_a", "agent_b"]

    def test_list_after_remove(self, am: AgentManager, setup_templates: None) -> None:
        am.initialize_game()
        am.remove_agent("agent_a")
        active = am.list_active_agents()
        assert active == ["agent_b"]


class TestSaveLoadSnapshot:
    def test_save_snapshot(self, am: AgentManager, setup_templates: None) -> None:
        am.initialize_game()
        am.file_manager.write_workspace_file("agent_a", "report.md", "data")
        snapshot = am.save_snapshot("game1", 5)
        assert snapshot.exists()
        # workspace 不应被保存
        assert not (snapshot / "agent_a" / "workspace").exists()
        # soul.md 应被保存
        assert (snapshot / "agent_a" / "soul.md").exists()

    def test_load_snapshot(
        self,
        am: AgentManager,
        fm: FileManager,
        setup_templates: None,
    ) -> None:
        am.initialize_game()
        fm.write_memory_summary("agent_a", "Important memory")
        am.save_snapshot("game1", 3)

        # 修改工作区
        fm.write_memory_summary("agent_a", "Modified")

        # 恢复快照
        agents = am.load_snapshot("game1", 3)
        assert "agent_a" in agents
        assert fm.read_memory_summary("agent_a") == "Important memory"
        # workspace 应被重建为空
        assert (fm.agent_dir("agent_a") / "workspace").is_dir()


class TestRebuildWorkspace:
    async def test_rebuild_workspace(self, am: AgentManager, setup_templates: None) -> None:
        am.initialize_game()

        mock_repo = AsyncMock()
        mock_repo.list_all_reports.return_value = [
            ("agent_a", 1, "report", "# Report Turn 1", "001_report.md"),
            ("agent_a", 2, "exec", "# Exec Turn 2", "002_exec_tax.md"),
            ("agent_b", 1, "report", "# B Report", None),
        ]

        await am.rebuild_workspace("game1", 5, mock_repo)

        mock_repo.list_all_reports.assert_called_once_with("game1", 5)

        # 验证文件写入
        files_a = am.file_manager.list_workspace_files("agent_a")
        assert "001_report.md" in files_a
        assert "002_exec_tax.md" in files_a

        files_b = am.file_manager.list_workspace_files("agent_b")
        assert "001_report.md" in files_b

    async def test_rebuild_skips_nonexistent_agent(
        self, am: AgentManager, setup_templates: None
    ) -> None:
        am.initialize_game()

        mock_repo = AsyncMock()
        mock_repo.list_all_reports.return_value = [
            ("nonexistent_agent", 1, "report", "# Report", "001_report.md"),
        ]

        # Should not raise
        await am.rebuild_workspace("game1", 5, mock_repo)
