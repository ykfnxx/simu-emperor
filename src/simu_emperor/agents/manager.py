"""
AgentManager - Agent 生命周期管理器

负责 Agent 的初始化、添加、移除和管理。
"""

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from simu_emperor.event_bus.core import EventBus
from simu_emperor.llm.base import LLMProvider

if TYPE_CHECKING:
    from simu_emperor.memory.tape_metadata import TapeMetadataManager
    from simu_emperor.memory.tape_writer import TapeWriter
    from simu_emperor.persistence.tape_repository import TapeRepository


logger = logging.getLogger(__name__)


class AgentManager:
    """
    Agent 管理器

    负责：
    - 从模板初始化 Agent
    - 添加/移除活跃 Agent
    - 管理 Agent 生命周期（启动/停止）
    """

    def __init__(
        self,
        event_bus: EventBus,
        llm_provider: LLMProvider,
        template_dir: Path | str = Path("data/default_agents"),
        agent_dir: Path | str = Path("data/agent"),
        repository=None,
        session_id: str | None = None,
        session_manager=None,
        tape_writer: "TapeWriter | None" = None,
        tape_metadata_mgr: "TapeMetadataManager | None" = None,
        tape_repository: "TapeRepository | None" = None,
        engine=None,
    ):
        self.event_bus = event_bus
        self.llm_provider = llm_provider
        self.template_dir = Path(template_dir)
        self.agent_dir = Path(agent_dir)
        self.repository = repository
        self.session_id = session_id
        self.session_manager = session_manager
        self.tape_writer = tape_writer
        self.tape_metadata_mgr = tape_metadata_mgr
        self.tape_repository = tape_repository
        self.engine = engine

        self._active_agents: dict[str, Any] = {}

        logger.info("AgentManager initialized")

    def initialize_agent(self, agent_id: str) -> bool:
        """
        从模板初始化 Agent

        将 template_dir/{agent_id}/ 复制到 agent_dir/{agent_id}/

        如果 agent_dir/{agent_id}/ 已存在有效的 soul.md 和 data_scope.yaml，
        则跳过复制（支持动态生成的 agent）。

        Args:
            agent_id: Agent 标识符

        Returns:
            是否成功初始化
        """
        template_path = self.template_dir / agent_id
        agent_path = self.agent_dir / agent_id

        if agent_path.exists():
            soul_md = agent_path / "soul.md"
            data_scope = agent_path / "data_scope.yaml"
            if soul_md.exists() and data_scope.exists():
                (agent_path / "memory").mkdir(parents=True, exist_ok=True)
                (agent_path / "memory" / "recent").mkdir(exist_ok=True)
                (agent_path / "workspace").mkdir(exist_ok=True)
                logger.info(f"Agent {agent_id} already exists in runtime directory, skipping copy")
                return True

        if not template_path.exists():
            logger.error(f"Template not found: {template_path}")
            return False

        if agent_path.exists():
            shutil.rmtree(agent_path)

        shutil.copytree(template_path, agent_path)

        (agent_path / "memory").mkdir(parents=True, exist_ok=True)
        (agent_path / "memory" / "recent").mkdir(exist_ok=True)
        (agent_path / "workspace").mkdir(exist_ok=True)

        logger.info(f"Agent {agent_id} initialized from template")
        return True

    def add_agent(self, agent_id: str) -> bool:
        """
        添加并启动 Agent

        Args:
            agent_id: Agent 标识符

        Returns:
            是否成功添加
        """
        if agent_id in self._active_agents:
            logger.warning(f"Agent {agent_id} already active")
            return False

        from simu_emperor.agents.agent import Agent

        agent_path = self.agent_dir / agent_id

        if not agent_path.exists():
            logger.error(f"Agent directory not found: {agent_path}")
            return False

        agent = Agent(
            agent_id=agent_id,
            event_bus=self.event_bus,
            llm_provider=self.llm_provider,
            data_dir=agent_path,
            repository=self.repository,
            session_id=self.session_id,
            session_manager=self.session_manager,
            tape_writer=self.tape_writer,
            tape_metadata_mgr=self.tape_metadata_mgr,
            tape_repository=self.tape_repository,
            engine=self.engine,
        )

        agent.start()
        agent.start_queue_consumer()

        self._active_agents[agent_id] = agent

        logger.info(f"Agent {agent_id} added and started")
        return True

    async def remove_agent(self, agent_id: str) -> bool:
        if agent_id not in self._active_agents:
            logger.warning(f"Agent {agent_id} not active")
            return False

        agent = self._active_agents[agent_id]
        await agent.stop_queue_consumer()
        agent.stop()
        del self._active_agents[agent_id]

        logger.info(f"Agent {agent_id} removed and stopped")
        return True

    def get_all_agents(self) -> list[str]:
        if not self.agent_dir.exists():
            return []

        agents = []
        for path in self.agent_dir.iterdir():
            if path.is_dir() and (path / "soul.md").exists():
                agents.append(path.name)

        return sorted(agents)

    def get_active_agents(self) -> list[str]:
        return list(self._active_agents.keys())

    def start_agent(self, agent_id: str) -> bool:
        if agent_id in self._active_agents:
            logger.warning(f"Agent {agent_id} already active")
            return False

        return self.add_agent(agent_id)

    async def stop_agent(self, agent_id: str) -> bool:
        if agent_id not in self._active_agents:
            logger.warning(f"Agent {agent_id} not active")
            return False

        agent = self._active_agents[agent_id]
        await agent.stop_queue_consumer()
        agent.stop()
        del self._active_agents[agent_id]

        logger.info(f"Agent {agent_id} stopped")
        return True

    async def stop_all(self) -> None:
        for agent_id in list(self._active_agents.keys()):
            await self.stop_agent(agent_id)

        logger.info("All agents stopped")

    def get_agent(self, agent_id: str) -> Any | None:
        return self._active_agents.get(agent_id)
