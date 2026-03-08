"""
AgentManager - Agent 生命周期管理器

负责 Agent 的初始化、添加、移除和管理。
"""

import logging
import shutil
from pathlib import Path
from typing import Any

from simu_emperor.event_bus.core import EventBus
from simu_emperor.llm.base import LLMProvider


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
    ):
        """
        初始化 AgentManager

        Args:
            event_bus: 事件总线
            llm_provider: LLM 提供商
            template_dir: Agent 模板目录
            agent_dir: Agent 工作目录
            repository: GameRepository（用于数据查询）
            session_id: 会话标识符
            session_manager: SessionManager（用于 task sessions）
        """
        self.event_bus = event_bus
        self.llm_provider = llm_provider
        self.template_dir = Path(template_dir)
        self.agent_dir = Path(agent_dir)
        self.repository = repository
        self.session_id = session_id
        self.session_manager = session_manager

        self._active_agents: dict[str, Any] = {}

        logger.info("AgentManager initialized")

    def initialize_agent(self, agent_id: str) -> bool:
        """
        从模板初始化 Agent

        将 template_dir/{agent_id}/ 复制到 agent_dir/{agent_id}/

        Args:
            agent_id: Agent 标识符

        Returns:
            是否成功初始化
        """
        template_path = self.template_dir / agent_id
        agent_path = self.agent_dir / agent_id

        if not template_path.exists():
            logger.error(f"Template not found: {template_path}")
            return False

        # 如果已存在，先删除
        if agent_path.exists():
            shutil.rmtree(agent_path)

        # 复制模板
        shutil.copytree(template_path, agent_path)

        # 创建 memory 和 workspace 目录
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

        # 延迟导入避免循环依赖
        from simu_emperor.agents.agent import Agent

        agent_path = self.agent_dir / agent_id

        if not agent_path.exists():
            logger.error(f"Agent directory not found: {agent_path}")
            return False

        # 创建 Agent 实例
        agent = Agent(
            agent_id=agent_id,
            event_bus=self.event_bus,
            llm_provider=self.llm_provider,
            data_dir=agent_path,
            repository=self.repository,
            session_id=self.session_id,
            session_manager=self.session_manager,
        )

        # 启动 Agent
        agent.start()

        # 添加到活跃列表
        self._active_agents[agent_id] = agent

        logger.info(f"Agent {agent_id} added and started")
        return True

    def remove_agent(self, agent_id: str) -> bool:
        """
        移除并停止 Agent

        Args:
            agent_id: Agent 标识符

        Returns:
            是否成功移除
        """
        if agent_id not in self._active_agents:
            logger.warning(f"Agent {agent_id} not active")
            return False

        # 停止 Agent
        agent = self._active_agents[agent_id]
        agent.stop()

        # 从活跃列表移除
        del self._active_agents[agent_id]

        logger.info(f"Agent {agent_id} removed and stopped")
        return True

    def get_all_agents(self) -> list[str]:
        """
        获取所有可用的 Agent ID（包括未活跃的）

        Returns:
            Agent ID 列表
        """
        if not self.agent_dir.exists():
            return []

        agents = []
        for path in self.agent_dir.iterdir():
            if path.is_dir() and (path / "soul.md").exists():
                agents.append(path.name)

        return sorted(agents)

    def get_active_agents(self) -> list[str]:
        """
        获取所有活跃的 Agent ID

        Returns:
            活跃 Agent ID 列表
        """
        return list(self._active_agents.keys())

    def start_agent(self, agent_id: str) -> bool:
        """
        启动 Agent（如果已存在但未启动）

        Args:
            agent_id: Agent 标识符

        Returns:
            是否成功启动
        """
        if agent_id in self._active_agents:
            logger.warning(f"Agent {agent_id} already active")
            return False

        return self.add_agent(agent_id)

    def stop_agent(self, agent_id: str) -> bool:
        """
        停止 Agent（但不移除）

        Args:
            agent_id: Agent 标识符

        Returns:
            是否成功停止
        """
        if agent_id not in self._active_agents:
            logger.warning(f"Agent {agent_id} not active")
            return False

        agent = self._active_agents[agent_id]
        agent.stop()

        # 从活跃列表移除
        del self._active_agents[agent_id]

        logger.info(f"Agent {agent_id} stopped")
        return True

    def stop_all(self) -> None:
        """停止所有活跃 Agent"""
        for agent_id in list(self._active_agents.keys()):
            self.stop_agent(agent_id)

        logger.info("All agents stopped")

    def get_agent(self, agent_id: str) -> Any | None:
        """
        获取 Agent 实例

        Args:
            agent_id: Agent 标识符

        Returns:
            Agent 实例，如果不存在则返回 None
        """
        return self._active_agents.get(agent_id)
