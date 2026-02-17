"""读写 agent 目录的文件操作。"""

from pathlib import Path
from typing import Any

import yaml


class FileManager:
    """Agent 文件 I/O 薄封装。

    所有路径由构造参数控制，便于 tmp_path 测试。
    """

    def __init__(
        self,
        agent_base: Path,
        template_base: Path,
        skills_dir: Path,
    ) -> None:
        self.agent_base = agent_base
        self.template_base = template_base
        self.skills_dir = skills_dir

    # ── 读取 ──

    def read_soul(self, agent_id: str) -> str:
        """读取 agent 的 soul.md 内容。"""
        path = self.agent_base / agent_id / "soul.md"
        return path.read_text(encoding="utf-8")

    def read_data_scope_raw(self, agent_id: str) -> dict[str, Any]:
        """读取并解析 agent 的 data_scope.yaml。"""
        path = self.agent_base / agent_id / "data_scope.yaml"
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def read_skill(self, skill_name: str) -> str:
        """读取通用 skill 模板。"""
        path = self.skills_dir / f"{skill_name}.md"
        return path.read_text(encoding="utf-8")

    def read_memory_summary(self, agent_id: str) -> str | None:
        """读取长期记忆 summary.md，不存在则返回 None。"""
        path = self.agent_base / agent_id / "memory" / "summary.md"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def list_recent_memories(self, agent_id: str) -> list[tuple[int, str]]:
        """列出短期记忆，返回 [(turn, content)] 按 turn 排序。

        文件命名规范：turn_{NNN:03d}.md
        """
        recent_dir = self.agent_base / agent_id / "memory" / "recent"
        if not recent_dir.exists():
            return []

        memories: list[tuple[int, str]] = []
        for path in recent_dir.glob("turn_*.md"):
            # 从文件名提取 turn 号：turn_006.md -> 6
            stem = path.stem  # turn_006
            turn_str = stem.split("_", 1)[1]  # 006
            turn = int(turn_str)
            content = path.read_text(encoding="utf-8")
            memories.append((turn, content))

        memories.sort(key=lambda x: x[0])
        return memories

    def read_workspace_file(self, agent_id: str, filename: str) -> str:
        """读取 workspace 中的指定文件。"""
        path = self.agent_base / agent_id / "workspace" / filename
        return path.read_text(encoding="utf-8")

    def list_workspace_files(self, agent_id: str) -> list[str]:
        """列出 workspace 中的所有文件名（排序）。"""
        workspace_dir = self.agent_base / agent_id / "workspace"
        if not workspace_dir.exists():
            return []
        return sorted(f.name for f in workspace_dir.iterdir() if f.is_file())

    # ── 写入 ──

    def write_memory_summary(self, agent_id: str, content: str) -> None:
        """写入长期记忆 summary.md。"""
        path = self.agent_base / agent_id / "memory" / "summary.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def write_recent_memory(self, agent_id: str, turn: int, content: str) -> None:
        """写入短期记忆 turn_{NNN:03d}.md。"""
        recent_dir = self.agent_base / agent_id / "memory" / "recent"
        recent_dir.mkdir(parents=True, exist_ok=True)
        path = recent_dir / f"turn_{turn:03d}.md"
        path.write_text(content, encoding="utf-8")

    def delete_recent_memory(self, agent_id: str, turn: int) -> None:
        """删除指定 turn 的短期记忆（若存在）。"""
        path = self.agent_base / agent_id / "memory" / "recent" / f"turn_{turn:03d}.md"
        if path.exists():
            path.unlink()

    def write_workspace_file(self, agent_id: str, filename: str, content: str) -> None:
        """写入 workspace 文件。"""
        workspace_dir = self.agent_base / agent_id / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        path = workspace_dir / filename
        path.write_text(content, encoding="utf-8")

    # ── 目录操作 ──

    def agent_dir(self, agent_id: str) -> Path:
        """返回 agent 的根目录路径。"""
        return self.agent_base / agent_id

    def list_agents(self) -> list[str]:
        """列出所有活跃 agent 目录名。"""
        if not self.agent_base.exists():
            return []
        return sorted(
            d.name for d in self.agent_base.iterdir() if d.is_dir() and (d / "soul.md").exists()
        )

    def list_templates(self) -> list[str]:
        """列出所有 agent 模板目录名。"""
        if not self.template_base.exists():
            return []
        return sorted(
            d.name for d in self.template_base.iterdir() if d.is_dir() and (d / "soul.md").exists()
        )

    def ensure_agent_dirs(self, agent_id: str) -> None:
        """创建 agent 的 memory/ 和 workspace/ 目录。"""
        agent = self.agent_base / agent_id
        (agent / "memory" / "recent").mkdir(parents=True, exist_ok=True)
        (agent / "workspace").mkdir(parents=True, exist_ok=True)

    def agent_exists(self, agent_id: str) -> bool:
        """检查 agent 是否存在（有 soul.md）。"""
        return (self.agent_base / agent_id / "soul.md").exists()
