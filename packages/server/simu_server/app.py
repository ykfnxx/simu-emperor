"""FastAPI application factory and lifespan management."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from simu_server.agents.generator import AgentGenerator
from simu_server.agents.registry import AgentRegistry
from simu_server.config import settings
from simu_server.engine.game_engine import GameEngine
from simu_server.routes import callback, client
from simu_server.routes.client import WSManager, ws_manager
from simu_server.services.event_router import EventRouter
from simu_server.services.group_store import GroupStore
from simu_server.services.invocation_manager import InvocationManager
from simu_server.services.message_store import MessageStore
from simu_server.services.process_manager import ProcessManager
from simu_server.services.queue_controller import QueueController
from simu_server.services.session_manager import SessionManager
from simu_server.stores.database import Database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize all services on startup, tear down on shutdown."""

    # Database
    db = Database(settings.db_path)
    await db.initialize()

    # Services
    session_manager = SessionManager(db)
    message_store = MessageStore(db)
    event_router = EventRouter()
    invocation_manager = InvocationManager(db, timeout=settings.agent_invocation_timeout)
    queue_controller = QueueController(max_depth=settings.agent_queue_depth)

    server_url = f"http://localhost:{settings.port}"
    process_manager = ProcessManager(server_url)

    # Agent registry
    agent_registry = AgentRegistry(db)

    # Agent generator
    agent_generator = AgentGenerator(
        agents_dir=settings.agents_dir,
        llm_config={
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "api_key": settings.llm_api_key,
            "base_url": settings.llm_base_url or None,
        },
    )

    # Group store
    group_persist = settings.db_path.parent / "group_chats.json"
    group_store = GroupStore(persist_path=group_persist)

    # Game engine
    engine = GameEngine(db)
    initial_state = settings.initial_state_path if settings.initial_state_path.exists() else None
    await engine.initialize(initial_state)

    # Wire queue dispatcher
    async def dispatch(agent_id: str, event: Any) -> None:
        inv = await invocation_manager.create(agent_id, event.session_id, event)
        event_with_inv = event.model_copy(update={"invocation_id": inv.invocation_id})
        await invocation_manager.mark_running(inv.invocation_id)
        await event_router.route(event_with_inv)

    queue_controller.set_dispatcher(dispatch)

    # Inject dependencies into route modules
    deps = {
        "db": db,
        "session_manager": session_manager,
        "message_store": message_store,
        "event_router": event_router,
        "invocation_manager": invocation_manager,
        "queue_controller": queue_controller,
        "process_manager": process_manager,
        "agent_registry": agent_registry,
        "agent_generator": agent_generator,
        "engine": engine,
        "group_store": group_store,
        "ws_manager": ws_manager,
    }
    client.set_dependencies(**deps)
    callback.set_dependencies(**deps)

    logger.info("Server started on %s:%d", settings.host, settings.port)
    yield

    # Shutdown
    await process_manager.shutdown_all()
    await db.close()
    logger.info("Server shut down")


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    app = FastAPI(title="Simu-Emperor Server", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(client.router)
    app.include_router(callback.router)

    return app
