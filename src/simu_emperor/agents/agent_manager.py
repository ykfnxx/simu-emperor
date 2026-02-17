"""动态管理：初始化/增删/存档/恢复。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from simu_emperor.agents.file_manager import FileManager

if TYPE_CHECKING:
    from simu_emperor.persistence.repositories import AgentReportRepository

_DISMISSED_MARKER = "\n\n---\n**已被罢免**\n"


class AgentManager:
    """Agent 动态管理器。"""

    def __init__(
        self,
        file_manager: FileManager,
        saves_dir: Path = Path("data/saves"),
    ) -> None:
        self.file_manager = file_manager
        self.saves_dir = saves_dir

    def initialize_game(self) -> list[str]:
        """从模板拷贝初始化新游戏。

        1. 清空 agent_base 目录
        2. 将 template_base 的全部内容拷贝到 agent_base
        3. 为每个 agent 创建空的 memory/ 和 workspace/ 目录

        Returns:
            初始化的 agent_id 列表
        """
        agent_base = self.file_manager.agent_base
        template_base = self.file_manager.template_base

        # 清空活跃工作区
        if agent_base.exists():
            shutil.rmtree(agent_base)
        agent_base.mkdir(parents=True, exist_ok=True)

        # 拷贝模板
        for template_dir in sorted(template_base.iterdir()):
            if template_dir.is_dir() and (template_dir / "soul.md").exists():
                dest = agent_base / template_dir.name
                shutil.copytree(template_dir, dest)
                self.file_manager.ensure_agent_dirs(template_dir.name)

        return self.file_manager.list_agents()

    def add_agent(self, agent_id: str, soul: str, data_scope_raw: str) -> None:
        """添加新 agent。

        Args:
            agent_id: Agent ID
            soul: soul.md 内容
            data_scope_raw: data_scope.yaml 原始内容字符串
        """
        agent_dir = self.file_manager.agent_base / agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "soul.md").write_text(soul, encoding="utf-8")
        (agent_dir / "data_scope.yaml").write_text(data_scope_raw, encoding="utf-8")
        self.file_manager.ensure_agent_dirs(agent_id)

    def remove_agent(self, agent_id: str) -> None:
        """罢免 agent（在 soul.md 追加罢免标记）。"""
        soul_path = self.file_manager.agent_base / agent_id / "soul.md"
        if not soul_path.exists():
            return
        content = soul_path.read_text(encoding="utf-8")
        if _DISMISSED_MARKER.strip() not in content:
            content += _DISMISSED_MARKER
            soul_path.write_text(content, encoding="utf-8")

    def list_active_agents(self) -> list[str]:
        """列出活跃（未罢免）的 agent。"""
        active: list[str] = []
        for agent_id in self.file_manager.list_agents():
            soul_path = self.file_manager.agent_base / agent_id / "soul.md"
            content = soul_path.read_text(encoding="utf-8")
            if _DISMISSED_MARKER.strip() not in content:
                active.append(agent_id)
        return active

    def save_snapshot(self, game_id: str, turn: int) -> Path:
        """保存 agent 文件系统快照（排除 workspace）。

        Returns:
            快照目录路径
        """
        snapshot_dir = self.saves_dir / game_id / f"turn_{turn:03d}" / "agent"
        if snapshot_dir.exists():
            shutil.rmtree(snapshot_dir)

        shutil.copytree(
            self.file_manager.agent_base,
            snapshot_dir,
            ignore=shutil.ignore_patterns("workspace"),
        )
        return snapshot_dir

    def load_snapshot(self, game_id: str, turn: int) -> list[str]:
        """从快照恢复 agent 文件系统。

        1. 清空 agent_base
        2. 从快照恢复 soul + data_scope + memory
        3. 为每个 agent 创建空 workspace

        Returns:
            恢复的 agent_id 列表
        """
        snapshot_dir = self.saves_dir / game_id / f"turn_{turn:03d}" / "agent"

        agent_base = self.file_manager.agent_base
        if agent_base.exists():
            shutil.rmtree(agent_base)

        shutil.copytree(snapshot_dir, agent_base)

        # 为每个 agent 创建空 workspace
        for agent_id in self.file_manager.list_agents():
            workspace = agent_base / agent_id / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)

        return self.file_manager.list_agents()

    async def rebuild_workspace(
        self,
        game_id: str,
        max_turn: int,
        report_repo: AgentReportRepository,
    ) -> None:
        """从 DB 重建 workspace 文件。

        按 id ASC 查询 agent_reports 表，重建 workspace/ 文件。

        Args:
            game_id: 游戏 ID
            max_turn: 最大回合数
            report_repo: AgentReportRepository 实例
        """
        reports = await report_repo.list_all_reports(game_id, max_turn)
        for agent_id, turn, report_type, markdown, file_name in reports:
            if not self.file_manager.agent_exists(agent_id):
                continue
            if file_name:
                self.file_manager.write_workspace_file(agent_id, file_name, markdown)
            else:
                # 没有 file_name 时按规范生成
                fname = f"{turn:03d}_{report_type}.md"
                self.file_manager.write_workspace_file(agent_id, fname, markdown)
