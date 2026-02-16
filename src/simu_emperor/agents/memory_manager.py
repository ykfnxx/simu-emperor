"""记忆管理：短期写入/清理（保留 3 回合）+ 长期读取。"""

from dataclasses import dataclass, field

from simu_emperor.agents.file_manager import FileManager

RECENT_MEMORY_WINDOW = 3


@dataclass
class MemoryContext:
    """Agent 记忆上下文。"""

    summary: str | None = None
    recent: list[tuple[int, str]] = field(default_factory=list)  # sorted by turn


class MemoryManager:
    """封装 FileManager，管理 3 回合窗口清理。"""

    def __init__(self, file_manager: FileManager) -> None:
        self.file_manager = file_manager

    def read_context(self, agent_id: str) -> MemoryContext:
        """读取 agent 的完整记忆上下文。"""
        summary = self.file_manager.read_memory_summary(agent_id)
        recent = self.file_manager.list_recent_memories(agent_id)
        return MemoryContext(summary=summary, recent=recent)

    def write_recent(self, agent_id: str, turn: int, content: str) -> None:
        """写入短期记忆并删除超出窗口的旧记忆。

        write_recent(agent_id, turn=6, ...) → 写入 turn_006.md，删除 turn_003.md（若存在）。
        """
        self.file_manager.write_recent_memory(agent_id, turn, content)
        old_turn = turn - RECENT_MEMORY_WINDOW
        if old_turn > 0:
            self.file_manager.delete_recent_memory(agent_id, old_turn)

    def update_summary(self, agent_id: str, content: str) -> None:
        """更新长期记忆 summary。"""
        self.file_manager.write_memory_summary(agent_id, content)
