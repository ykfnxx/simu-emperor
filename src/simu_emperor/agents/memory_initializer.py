"""记忆系统初始化器（V4 重构）"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from simu_emperor.agents.tools.memory_tools import MemoryTools
from simu_emperor.config import settings
from simu_emperor.llm.base import LLMProvider
from simu_emperor.memory.context_manager import ContextManager, ContextConfig
from simu_emperor.memory.tape_writer import TapeWriter

if TYPE_CHECKING:
    from simu_emperor.memory.tape_metadata import TapeMetadataManager

logger = logging.getLogger(__name__)


class MemoryInitializer:
    """记忆系统初始化器（V4 重构）"""

    def __init__(
        self,
        agent_id: str,
        memory_dir: Path,
        llm_provider: LLMProvider,
        # V4.1: 注入全局共享实例，而不是创建自己的副本
        tape_writer: TapeWriter,
        tape_metadata_mgr: "TapeMetadataManager | None" = None,
    ):
        """
        初始化 MemoryInitializer

        Args:
            agent_id: Agent 标识符
            memory_dir: 内存目录路径
            llm_provider: LLM 提供者
            tape_writer: V4.1 全局共享的 TapeWriter 实例
            tape_metadata_mgr: V4.1 全局共享的 TapeMetadataManager 实例
        """
        self.agent_id = agent_id
        self.memory_dir = memory_dir
        self.llm_provider = llm_provider
        self._tape_writer = tape_writer  # 使用注入的实例
        self._tape_metadata_mgr = tape_metadata_mgr

    async def _on_event_written(self, agent_id: str, session_id: str) -> None:
        """
        事件写入后的回调（V4 新增）。

        触发 tape_metadata_mgr.increment_event_count() 更新事件计数。

        Args:
            agent_id: Agent 标识符
            session_id: Session 标识符
        """
        if self._tape_metadata_mgr:
            try:
                await self._tape_metadata_mgr.increment_event_count(agent_id, session_id)
            except Exception as e:
                logger.warning(f"Failed to increment event count: {e}")

    async def initialize(
        self, session_id: str, turn: int = 1, system_prompt: str | None = None
    ) -> tuple[ContextManager, MemoryTools]:
        """
        初始化记忆组件（V4 重构）。

        V4 变更：
        - 移除 manifest_index 注册
        - 注入 tape_writer 和 tape_metadata_mgr 到 ContextManager
        - 注入 system_prompt 到 ContextManager

        Args:
            session_id: Session 标识符
            turn: 回合数
            system_prompt: V4 新增：系统提示词

        Returns:
            (ContextManager, MemoryTools) 元组
        """
        logger.info(f"🧠 [Agent:{self.agent_id}] Initializing memory components...")

        # 1. 获取 tape 路径
        tape_path = self._tape_writer._get_tape_path(session_id, self.agent_id)

        # 2. V4: 初始化 ContextManager（注入所有依赖）
        # 从 settings 传递记忆上下文配置
        memory_context = settings.memory.context
        context_manager = ContextManager(
            session_id=session_id,
            agent_id=self.agent_id,
            tape_path=tape_path,
            config=ContextConfig(
                max_tokens=memory_context.max_tokens,
                threshold_ratio=memory_context.threshold_ratio,
                keep_recent_events=memory_context.keep_recent_events,
            ),
            llm_provider=self.llm_provider,
            tape_writer=self._tape_writer,  # V4 新增
            tape_metadata_mgr=self._tape_metadata_mgr,  # V4 新增
            system_prompt=system_prompt,  # V4 新增
        )

        # 3. V4: 初始化 MemoryTools
        memory_tools = MemoryTools(
            agent_id=self.agent_id,
            memory_dir=self.memory_dir,
            llm_provider=self.llm_provider,
            context_manager=context_manager,
        )

        # 4. V4: 移除 manifest 注册（不再需要）

        # 5. 加载历史事件
        await context_manager.load_from_tape()

        logger.info(f"✅ [Agent:{self.agent_id}] Memory components initialized")

        return context_manager, memory_tools
