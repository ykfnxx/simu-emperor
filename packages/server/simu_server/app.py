"""FastAPI application factory and lifespan management."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from simu_shared.models import InvocationStatus
from simu_server.agents.generator import AgentGenerator
from simu_server.agents.registry import AgentRegistry
from simu_server.config import settings
from simu_server.engine.game_engine import GameEngine
from simu_server.mcp import set_role_dependencies, set_simu_dependencies, simu_mcp, role_mcp
from simu_server.mcp.auth import MCPAuthMiddleware, set_process_manager
from simu_server.routes import callback, client
from simu_server.routes.client import WSManager, ws_manager, ws_router
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
    message_store = MessageStore(db, memory_dir=settings.memory_dir)
    event_router = EventRouter()
    invocation_manager = InvocationManager(db, timeout=settings.agent_invocation_timeout)
    queue_controller = QueueController(max_depth=settings.agent_queue_depth)

    server_url = f"http://localhost:{settings.port}"
    process_manager = ProcessManager(
        server_url,
        llm_config={
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "api_key": settings.llm_api_key,
            "base_url": settings.llm_base_url or "",
        },
        memory_dir=str(settings.memory_dir),
    )

    # Agent registry
    agent_registry = AgentRegistry(db)

    # Copy default agents to agents_dir and register them
    import shutil
    from simu_shared.models import AgentRegistration, AgentStatus

    default_agents_dir = settings.default_agents_dir
    agents_dir = settings.agents_dir
    if default_agents_dir.exists():
        agents_dir.mkdir(parents=True, exist_ok=True)
        for src_dir in sorted(default_agents_dir.iterdir()):
            if src_dir.is_dir() and (src_dir / "soul.md").exists():
                agent_id = src_dir.name
                dst_dir = agents_dir / agent_id

                # Copy if not already present
                if not dst_dir.exists():
                    shutil.copytree(src_dir, dst_dir)
                    logger.info("Copied default agent %s to %s", agent_id, dst_dir)

                # Extract display name from soul.md
                display_name = agent_id
                soul_path = dst_dir / "soul.md"
                first_line = soul_path.read_text(encoding="utf-8").split("\n")[0]
                if first_line.startswith("# "):
                    display_name = first_line[2:].strip().split(" - ")[0].strip()

                reg = AgentRegistration(
                    agent_id=agent_id,
                    display_name=display_name,
                    status=AgentStatus.REGISTERED,
                    config_path=str(dst_dir),
                )
                await agent_registry.register(reg)
                logger.info("Registered agent: %s (%s)", agent_id, display_name)

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
    logger.info(
        "Initial state path: %s (exists=%s)",
        settings.initial_state_path,
        settings.initial_state_path.exists(),
    )
    await engine.initialize(initial_state)

    # Wire queue dispatcher
    async def dispatch(agent_id: str, event: Any) -> None:
        inv = await invocation_manager.create(agent_id, event.session_id, event)
        event_with_inv = event.model_copy(update={"invocation_id": inv.invocation_id})
        await invocation_manager.mark_running(inv.invocation_id)
        try:
            await event_router.route(event_with_inv)
        except Exception:
            logger.exception("Dispatch failed for agent %s, marking invocation FAILED", agent_id)
            await invocation_manager.complete(
                inv.invocation_id, InvocationStatus.FAILED, error="dispatch routing failed"
            )
            raise

    queue_controller.set_dispatcher(dispatch)

    # Shared set tracking which agents are currently online — used by both
    # the periodic heartbeat checker and the callback broadcast helper to
    # avoid duplicate WebSocket broadcasts.
    online_agents: set[str] = set()

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
        "online_agents": online_agents,
    }
    client.set_dependencies(**deps)
    callback.set_dependencies(**deps)

    # MCP server dependencies
    set_process_manager(process_manager)
    mcp_deps = {
        "engine": engine,
        "session_manager": session_manager,
        "message_store": message_store,
        "queue_controller": queue_controller,
        "agent_registry": agent_registry,
        "ws_manager": ws_manager,
        "invocation_manager": invocation_manager,
    }
    set_simu_dependencies(**mcp_deps)
    set_role_dependencies(agent_registry=agent_registry)

    # Spawn agent processes for all registered agents
    for agent in await agent_registry.list_all():
        if agent.config_path:
            try:
                pid = await process_manager.spawn(agent)
                logger.info("Spawned agent %s (PID %d)", agent.agent_id, pid)
            except Exception:
                logger.warning("Failed to spawn agent %s", agent.agent_id, exc_info=True)

    # Background task: detect agents that missed heartbeat and broadcast offline
    async def _heartbeat_checker() -> None:
        timeout = settings.agent_heartbeat_timeout
        while True:
            await asyncio.sleep(15)
            try:
                agents = await agent_registry.list_all()
                for agent in agents:
                    is_online = AgentRegistry.is_agent_online(agent, timeout)
                    was_online = agent.agent_id in online_agents

                    if is_online and not was_online:
                        online_agents.add(agent.agent_id)
                        await ws_manager.broadcast({
                            "kind": "agent_status",
                            "data": {
                                "agent_id": agent.agent_id,
                                "agent_name": agent.display_name or agent.agent_id,
                                "status": agent.status.value,
                                "is_online": True,
                            },
                        })
                    elif not is_online and was_online:
                        online_agents.discard(agent.agent_id)
                        await ws_manager.broadcast({
                            "kind": "agent_status",
                            "data": {
                                "agent_id": agent.agent_id,
                                "agent_name": agent.display_name or agent.agent_id,
                                "status": agent.status.value,
                                "is_online": False,
                            },
                        })
            except Exception:
                logger.debug("Heartbeat checker iteration failed", exc_info=True)

    heartbeat_task = asyncio.create_task(_heartbeat_checker())

    logger.info("Server started on %s:%d", settings.host, settings.port)
    yield

    # Shutdown
    heartbeat_task.cancel()
    await process_manager.shutdown_all()
    await db.close()
    logger.info("Server shut down")


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    app = FastAPI(title="Simu-Emperor Server", lifespan=lifespan)

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(client.router)
    app.include_router(ws_router)
    app.include_router(callback.router)

    # Mount MCP servers with auth middleware
    app.mount("/mcp/simu", MCPAuthMiddleware(simu_mcp.streamable_http_app()))
    app.mount("/mcp/role", MCPAuthMiddleware(role_mcp.streamable_http_app()))

    return app
