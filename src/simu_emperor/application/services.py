"""Application Services Container.

This module provides the ApplicationServices container that manages
all application service instances and their lifecycle.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from simu_emperor.common import DEFAULT_WEB_SESSION_ID
from simu_emperor.config import GameConfig

if TYPE_CHECKING:
    from simu_emperor.application.game_service import GameService
    from simu_emperor.application.session_service import SessionService
    from simu_emperor.application.agent_service import AgentService
    from simu_emperor.application.group_chat_service import GroupChatService
    from simu_emperor.application.message_service import MessageService
    from simu_emperor.application.tape_service import TapeService


@dataclass
class ApplicationServices:
    """Application services container.

    Manages all application service instances and provides
    dependency injection and lifecycle management.

    Services are initialized in dependency order:
    1. Infrastructure (Database, EventBus, LLM)
    2. Core services (GameService, AgentService)
    3. Dependent services (SessionService, GroupChatService, etc.)
    """

    game_service: "GameService | None" = None
    session_service: "SessionService | None" = None
    agent_service: "AgentService | None" = None
    group_chat_service: "GroupChatService | None" = None
    message_service: "MessageService | None" = None
    tape_service: "TapeService | None" = None

    # Infrastructure components
    settings: GameConfig = field(default_factory=GameConfig)
    memory_dir: Path = field(default_factory=lambda: Path("data/memory"))

    @classmethod
    async def create(cls, settings: GameConfig) -> "ApplicationServices":
        """Create and initialize all application services.

        Args:
            settings: Game configuration

        Returns:
            Initialized ApplicationServices container
        """
        from simu_emperor.persistence import init_database
        from simu_emperor.persistence.repositories import GameRepository
        from simu_emperor.event_bus.core import EventBus
        from simu_emperor.event_bus.logger import FileEventLogger, DatabaseEventLogger
        from simu_emperor.llm.anthropic import AnthropicProvider
        from simu_emperor.llm.openai import OpenAIProvider
        from simu_emperor.llm.mock import MockProvider
        from simu_emperor.memory.tape_metadata import TapeMetadataManager
        from simu_emperor.memory.tape_writer import TapeWriter
        from simu_emperor.session.manager import SessionManager

        from simu_emperor.application.game_service import GameService
        from simu_emperor.application.session_service import SessionService
        from simu_emperor.application.agent_service import AgentService
        from simu_emperor.application.group_chat_service import GroupChatService
        from simu_emperor.application.message_service import MessageService
        from simu_emperor.application.tape_service import TapeService
        from simu_emperor.agents.agent_generator import AgentGenerator

        # Resolve memory directory
        memory_dir = cls._resolve_memory_dir(settings)

        # 1. Initialize LLM Provider
        llm_config = settings.llm
        if llm_config.provider == "anthropic":
            llm_provider = AnthropicProvider(api_key=llm_config.api_key)
        elif llm_config.provider == "openai":
            llm_provider = OpenAIProvider(
                api_key=llm_config.api_key,
                model=llm_config.get_model(),
                base_url=llm_config.api_base,
            )
        else:
            llm_provider = MockProvider()

        # Initialize AgentGenerator (for dynamic agent creation)
        agent_generator = AgentGenerator(
            llm_provider=llm_provider,
            data_dir=settings.data_dir,
        )

        # 2. Initialize Database
        db_path = str(settings.data_dir / "game.db")
        conn = await init_database(db_path)
        repository = GameRepository(conn)

        # 3. Initialize EventBus
        log_dir = settings.log_dir / "events"
        log_dir.mkdir(parents=True, exist_ok=True)

        file_logger = FileEventLogger(log_dir)
        db_logger = DatabaseEventLogger(conn)
        event_bus = EventBus(file_logger=file_logger, db_logger=db_logger)

        # 4. Initialize memory components
        tape_metadata_mgr = TapeMetadataManager(memory_dir=memory_dir)
        tape_writer = TapeWriter(
            memory_dir=memory_dir,
            tape_metadata_mgr=tape_metadata_mgr,
            llm_provider=llm_provider,
        )

        # 5. Initialize SessionManager
        session_manager = SessionManager(
            memory_dir=memory_dir,
            llm_provider=llm_provider,
            tape_metadata_mgr=tape_metadata_mgr,
            tape_writer=tape_writer,
        )

        # 6. Create main session
        main_session_id = DEFAULT_WEB_SESSION_ID
        if not await session_manager.get_session(main_session_id):
            await session_manager.create_session(
                session_id=main_session_id,
                created_by="system:web",
                status="ACTIVE",
            )

        # 7. Initialize services in dependency order
        game_service = GameService(
            settings=settings,
            repository=repository,
            event_bus=event_bus,
            llm_provider=llm_provider,
            memory_dir=memory_dir,
        )

        agent_service = AgentService(
            settings=settings,
            event_bus=event_bus,
            llm_provider=llm_provider,
            repository=repository,
            session_manager=session_manager,
            session_id=main_session_id,
            agent_generator=agent_generator,
        )

        session_service = SessionService(
            session_manager=session_manager,
            memory_dir=memory_dir,
            agent_service=agent_service,
        )

        group_chat_service = GroupChatService(
            session_manager=session_manager,
            memory_dir=memory_dir,
        )

        message_service = MessageService(
            event_bus=event_bus,
            session_manager=session_manager,
        )

        # Set message service reference for group chat
        group_chat_service.set_message_service(message_service)

        tape_service = TapeService(
            session_manager=session_manager,
            tape_writer=tape_writer,
            memory_dir=memory_dir,
        )

        return cls(
            game_service=game_service,
            session_service=session_service,
            agent_service=agent_service,
            group_chat_service=group_chat_service,
            message_service=message_service,
            tape_service=tape_service,
            settings=settings,
            memory_dir=memory_dir,
        )

    @staticmethod
    def _resolve_memory_dir(settings: GameConfig) -> Path:
        """Resolve memory directory path."""
        configured = getattr(getattr(settings, "memory", None), "memory_dir", None)
        if configured:
            path = Path(configured)
            return path if path.is_absolute() else path.resolve()
        return settings.data_dir / "memory"

    async def start(self) -> None:
        """Start all services."""
        if self.game_service:
            await self.game_service.initialize()
        if self.agent_service:
            await self.agent_service.initialize_agents()

    async def shutdown(self) -> None:
        """Shutdown all services in reverse order."""
        from simu_emperor.persistence import close_database

        # Shutdown game service (includes tick coordinator)
        if self.game_service:
            await self.game_service.shutdown()

        # Stop all agents
        if self.agent_service:
            await self.agent_service.stop_all()

        # Close database
        await close_database()

    @property
    def event_bus(self):
        """Get the event bus instance."""
        if self.game_service:
            return self.game_service.event_bus
        return None

    @property
    def repository(self):
        """Get the repository instance."""
        if self.game_service:
            return self.game_service.repository
        return None

    @property
    def agent_manager(self):
        """Get the agent manager instance."""
        if self.agent_service:
            return self.agent_service.agent_manager
        return None

    @property
    def session_manager(self):
        """Get the session manager instance."""
        if self.session_service:
            return self.session_service.session_manager
        return None
