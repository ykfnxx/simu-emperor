"""Agent Service - Agent lifecycle and availability management."""

import logging
from typing import TYPE_CHECKING, Any

from simu_emperor.common import DEFAULT_WEB_SESSION_ID, strip_agent_prefix
from simu_emperor.config import GameConfig

if TYPE_CHECKING:
    from simu_emperor.event_bus.core import EventBus
    from simu_emperor.llm.base import LLMProvider
    from simu_emperor.persistence.repositories import GameRepository
    from simu_emperor.session.manager import SessionManager
    from simu_emperor.agents.manager import AgentManager
    from simu_emperor.agents.agent_generator import AgentGenerator
    from simu_emperor.application.task_tracker import TaskTracker  # noqa: F401
    from simu_emperor.memory.tape_metadata import TapeMetadataManager
    from simu_emperor.memory.tape_writer import TapeWriter


logger = logging.getLogger(__name__)


class AgentService:
    """Agent business service.

    Responsibilities:
    - Agent lifecycle management
    - Agent availability checking
    - Agent list queries
    """

    # Default agents to initialize
    DEFAULT_AGENTS = [
        "governor_zhili",
        "governor_fujian",
        "governor_huguang",
        "governor_jiangnan",
        "governor_jiangxi",
        "governor_shaanxi",
        "governor_shandong",
        "governor_sichuan",
        "governor_zhejiang",
        "minister_of_revenue",
    ]

    def __init__(
        self,
        settings: GameConfig,
        event_bus: "EventBus",
        llm_provider: "LLMProvider",
        repository: "GameRepository",
        session_manager: "SessionManager",
        session_id: str = DEFAULT_WEB_SESSION_ID,
        agent_generator: "AgentGenerator | None" = None,
        # V4.1: 注入全局共享实例
        tape_writer: "TapeWriter | None" = None,
        tape_metadata_mgr: "TapeMetadataManager | None" = None,
    ) -> None:
        """Initialize AgentService.

        Args:
            settings: Game configuration
            event_bus: Event bus for pub/sub
            llm_provider: LLM provider for AI
            repository: Game state repository
            session_manager: Session lifecycle manager
            session_id: Main session ID
            agent_generator: Optional agent generator for dynamic agent creation
            tape_writer: V4.1 全局共享的 TapeWriter 实例
            tape_metadata_mgr: V4.1 全局共享的 TapeMetadataManager 实例
        """
        self.settings = settings
        self.event_bus = event_bus
        self.llm_provider = llm_provider
        self.repository = repository
        self.session_manager = session_manager
        self.session_id = session_id
        self.tape_writer = tape_writer
        self.tape_metadata_mgr = tape_metadata_mgr

        # Agent manager (lazy initialized)
        self.agent_manager: "AgentManager | None" = None
        # Agent generator (optional)
        self._agent_generator: "AgentGenerator | None" = agent_generator
        # Task tracker for background jobs (lazy initialized)
        self._task_tracker: "TaskTracker | None" = None

    async def initialize_agents(self, agent_ids: list[str] | None = None) -> None:
        """Initialize and start agents.

        Args:
            agent_ids: List of agent IDs to initialize (defaults to DEFAULT_AGENTS)
        """
        from simu_emperor.agents.manager import AgentManager

        if self.agent_manager is not None:
            logger.warning("AgentManager already initialized")
            return

        # Create agent directory
        agent_dir = self.settings.data_dir / "agent" / "web"
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Create agent manager
        self.agent_manager = AgentManager(
            event_bus=self.event_bus,
            llm_provider=self.llm_provider,
            template_dir=self.settings.data_dir / "default_agents",
            agent_dir=str(agent_dir),
            repository=self.repository,
            session_id=self.session_id,
            session_manager=self.session_manager,
            tape_writer=self.tape_writer,
            tape_metadata_mgr=self.tape_metadata_mgr,
        )

        # Initialize and start agents
        agents_to_start = agent_ids or self.DEFAULT_AGENTS
        for agent_id in agents_to_start:
            if self.agent_manager.initialize_agent(agent_id):
                self.agent_manager.add_agent(agent_id)
                logger.info(f"Agent {agent_id} started")

        logger.info(f"AgentManager initialized with {len(agents_to_start)} agents")

    async def get_available_agents(self) -> list[str]:
        """Get list of available (initialized and active) agents.

        Returns:
            List of agent IDs
        """
        if self.agent_manager:
            return self.agent_manager.get_active_agents()
        return []

    async def get_active_agents(self) -> list[str]:
        """Get list of active agents.

        Returns:
            List of agent IDs
        """
        return await self.get_available_agents()

    async def is_agent_available(self, agent_id: str) -> bool:
        """Check if an agent is available.

        Args:
            agent_id: Agent to check

        Returns:
            True if agent is available
        """
        normalized = strip_agent_prefix(agent_id)
        available = await self.get_available_agents()
        return normalized in available

    def get_agent(self, agent_id: str):
        """Get agent instance by ID.

        Args:
            agent_id: Agent to retrieve

        Returns:
            Agent instance or None
        """
        if self.agent_manager:
            return self.agent_manager.get_agent(agent_id)
        return None

    async def stop_all(self) -> None:
        """Stop all agents."""
        if self.agent_manager:
            self.agent_manager.stop_all()
            logger.info("All agents stopped")

    @property
    def is_initialized(self) -> bool:
        """Check if agent manager is initialized."""
        return self.agent_manager is not None

    # ========================================================================
    # Dynamic Agent Generation (NEW)
    # ========================================================================

    async def generate_agent(
        self,
        agent_id: str,
        title: str,
        name: str,
        duty: str,
        personality: str,
        province: str | None = None,
    ) -> dict:
        """LLM 生成 agent 配置并创建文件

        Args:
            agent_id: Agent 唯一标识符（如 governor_zhili）
            title: 官职（如 "直隶巡抚"）
            name: 姓名（如 "蔡珽"）
            duty: 职责描述（如 "直隶省民政、农桑、商贸、治安"）
            personality: 为人描述（如 "行事果断，忠心耿耿"）
            province: 管辖省份（可选，如 "zhili"）

        Returns:
            {
                "success": bool,
                "agent_id": str,
                "soul_md": str,
                "data_scope": str,
                "role_map_entry": str,
            }

        Raises:
            RuntimeError: AgentGenerator not initialized
        """
        from simu_emperor.agents.agent_generator import AgentConfig

        if not self._agent_generator:
            raise RuntimeError("AgentGenerator not initialized")

        config = AgentConfig(
            agent_id=agent_id,
            title=title,
            name=name,
            duty=duty,
            personality=personality,
            province=province,
        )

        # LLM 生成配置
        generated = await self._agent_generator.generate_config(config)

        # 创建 agent 目录（运行时目录，不是 default_agents 模板目录）
        agent_dir = self.settings.data_dir / "agent" / "web" / agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)

        # 写入 soul.md
        (agent_dir / "soul.md").write_text(generated.soul_md, encoding="utf-8")

        # 写入 data_scope.yaml
        (agent_dir / "data_scope.yaml").write_text(generated.data_scope, encoding="utf-8")

        # 追加到 role_map.md
        self._append_to_role_map(generated.role_map_entry)

        logger.info(f"Agent {agent_id} config generated and files written")

        return {
            "success": True,
            "agent_id": agent_id,
            "soul_md": generated.soul_md,
            "data_scope": generated.data_scope,
            "role_map_entry": generated.role_map_entry,
        }

    async def add_generated_agent(
        self,
        agent_id: str,
        title: str,
        name: str,
        duty: str,
        personality: str,
        province: str | None = None,
    ) -> dict:
        """生成配置并启动 agent（完整流程）

        Args:
            agent_id: Agent 唯一标识符
            title: 官职
            name: 姓名
            duty: 职责描述
            personality: 为人描述
            province: 管辖省份（可选）

        Returns:
            {
                "success": bool,
                "agent_id": str,
                "message": str,
                "soul_md": str,
                "data_scope": str,
                "role_map_entry": str,
            }
        """
        # 1. 生成配置文件
        result = await self.generate_agent(
            agent_id=agent_id,
            title=title,
            name=name,
            duty=duty,
            personality=personality,
            province=province,
        )

        # 2. 初始化并启动
        if self.agent_manager:
            if self.agent_manager.initialize_agent(agent_id):
                self.agent_manager.add_agent(agent_id)
                result["message"] = f"Agent {agent_id} 生成并启动成功"
            else:
                result["message"] = f"Agent {agent_id} 配置已生成，但初始化失败"
                result["success"] = False
        else:
            result["message"] = f"Agent {agent_id} 配置已生成，但 AgentManager 未初始化"
            result["success"] = False

        return result

    def _append_to_role_map(self, entry: str) -> None:
        """追加条目到 role_map.md

        Args:
            entry: 要追加的条目内容
        """
        role_map_path = self.settings.data_dir / "role_map.md"

        # 如果文件不存在，从默认备份恢复
        if not role_map_path.exists():
            self._restore_role_map_from_default()

        # 追加条目
        with open(role_map_path, "a", encoding="utf-8") as f:
            f.write("\n" + entry + "\n")

        logger.info("Appended entry to role_map.md")

    def _restore_role_map_from_default(self) -> None:
        """从默认备份恢复 role_map.md"""
        role_map_path = self.settings.data_dir / "role_map.md"
        default_role_map = self.settings.data_dir / "default_agents" / "role_map.md"

        role_map_path.parent.mkdir(parents=True, exist_ok=True)

        if default_role_map.exists():
            # 从默认备份复制
            import shutil

            shutil.copy(default_role_map, role_map_path)
            logger.info("Restored role_map.md from default backup")
        else:
            # 创建最小默认文件
            role_map_path.write_text(
                "# 大清帝国官员职责表\n\n",
                encoding="utf-8",
            )
            logger.warning("Default role_map.md not found, created minimal file")

    def set_agent_generator(self, agent_generator: "AgentGenerator") -> None:
        """设置 AgentGenerator（用于依赖注入）

        Args:
            agent_generator: AgentGenerator 实例
        """
        self._agent_generator = agent_generator

    def _get_task_tracker(self) -> "TaskTracker":
        """获取或创建 TaskTracker 实例"""
        if self._task_tracker is None:
            from simu_emperor.application.task_tracker import get_task_tracker

            self._task_tracker = get_task_tracker()
        return self._task_tracker

    async def add_generated_agent_async(
        self,
        agent_id: str,
        title: str,
        name: str,
        duty: str,
        personality: str,
        province: str | None = None,
    ) -> dict[str, Any]:
        """生成配置并启动 agent（异步后台任务）

        此方法在后台任务中执行，返回完整结果。

        Args:
            agent_id: Agent 唯一标识符
            title: 官职
            name: 姓名
            duty: 职责描述
            personality: 为人描述
            province: 管辖省份（可选）

        Returns:
            包含 success, agent_id, message 等字段的字典
        """
        from simu_emperor.application.task_tracker import TaskTracker  # noqa: F401

        task_tracker = self._get_task_tracker()

        # 更新进度：开始生成配置
        task_tracker.update_progress(agent_id, 10)

        # 1. 生成配置文件
        result = await self.generate_agent(
            agent_id=agent_id,
            title=title,
            name=name,
            duty=duty,
            personality=personality,
            province=province,
        )

        # 更新进度：配置生成完成
        task_tracker.update_progress(agent_id, 50)

        # 2. 初始化并启动
        if self.agent_manager:
            if self.agent_manager.initialize_agent(agent_id):
                self.agent_manager.add_agent(agent_id)
                result["message"] = f"Agent {agent_id} 生成并启动成功"
                result["success"] = True
            else:
                result["message"] = f"Agent {agent_id} 配置已生成，但初始化失败"
                result["success"] = False
        else:
            result["message"] = f"Agent {agent_id} 配置已生成，但 AgentManager 未初始化"
            result["success"] = False

        # 更新进度：完成
        task_tracker.update_progress(agent_id, 100)

        return result
