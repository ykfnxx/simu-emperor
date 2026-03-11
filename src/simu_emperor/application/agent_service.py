"""Agent Service - Agent lifecycle and availability management."""

import logging
from typing import TYPE_CHECKING

from simu_emperor.config import GameConfig

if TYPE_CHECKING:
    from simu_emperor.event_bus.core import EventBus
    from simu_emperor.llm.base import LLMProvider
    from simu_emperor.persistence.repositories import GameRepository
    from simu_emperor.session.manager import SessionManager
    from simu_emperor.agents.manager import AgentManager


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
        session_id: str = "session:web:main",
    ) -> None:
        """Initialize AgentService.

        Args:
            settings: Game configuration
            event_bus: Event bus for pub/sub
            llm_provider: LLM provider for AI
            repository: Game state repository
            session_manager: Session lifecycle manager
            session_id: Main session ID
        """
        self.settings = settings
        self.event_bus = event_bus
        self.llm_provider = llm_provider
        self.repository = repository
        self.session_manager = session_manager
        self.session_id = session_id

        # Agent manager (lazy initialized)
        self.agent_manager: "AgentManager | None" = None

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
        normalized = self._normalize_agent_id(agent_id)
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

    def _normalize_agent_id(self, agent_id: str) -> str:
        """Normalize agent ID (remove agent: prefix)."""
        if agent_id.startswith("agent:"):
            return agent_id.replace("agent:", "", 1)
        return agent_id

    @property
    def is_initialized(self) -> bool:
        """Check if agent manager is initialized."""
        return self.agent_manager is not None
