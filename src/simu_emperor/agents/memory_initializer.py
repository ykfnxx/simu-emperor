"""记忆系统初始化器"""

import logging
from pathlib import Path

from simu_emperor.agents.tools.memory_tools import MemoryTools
from simu_emperor.llm.base import LLMProvider
from simu_emperor.memory.context_manager import ContextManager, ContextConfig
from simu_emperor.memory.manifest_index import ManifestIndex
from simu_emperor.memory.tape_writer import TapeWriter

logger = logging.getLogger(__name__)


class MemoryInitializer:
    """记忆系统初始化器"""

    def __init__(
        self,
        agent_id: str,
        memory_dir: Path,
        llm_provider: LLMProvider,
    ):
        """初始化 MemoryInitializer"""
        self.agent_id = agent_id
        self.memory_dir = memory_dir
        self.llm_provider = llm_provider

        # 初始化记忆组件
        self._tape_writer = TapeWriter(memory_dir)
        self._manifest_index = ManifestIndex(memory_dir)

    async def initialize(
        self, session_id: str, turn: int = 1
    ) -> tuple[ContextManager, MemoryTools]:
        """初始化记忆组件"""
        logger.info(f"🧠 [Agent:{self.agent_id}] Initializing memory components...")

        # 1. 获取 tape 路径
        tape_path = self._tape_writer._get_tape_path(session_id, self.agent_id)

        # 2. 初始化 ContextManager
        context_manager = ContextManager(
            session_id=session_id,
            agent_id=self.agent_id,
            tape_path=tape_path,
            config=ContextConfig(),
            llm_provider=self.llm_provider,
            manifest_index=self._manifest_index,
        )

        # 3. 初始化 MemoryTools
        memory_tools = MemoryTools(
            agent_id=self.agent_id,
            memory_dir=self.memory_dir,
            llm_provider=self.llm_provider,
            context_manager=context_manager,
        )

        # 4. 注册 session
        await self._manifest_index.register_session(
            session_id=session_id,
            agent_id=self.agent_id,
            turn=turn,
        )

        # 5. 加载历史事件
        await context_manager.load_from_tape()

        logger.info(f"✅ [Agent:{self.agent_id}] Memory components initialized")

        return context_manager, memory_tools
