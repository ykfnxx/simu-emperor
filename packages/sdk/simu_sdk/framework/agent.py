"""SimuAgent — orchestration layer with session state machine.

Sits above the BubFramework core and manages:
- Session state machine (IDLE / BLOCKED / DRAINING)
- Event dispatch (which events enter the pipeline vs. get queued)
- Agent lifecycle (start / stop / heartbeat)

The Bub pipeline only processes events that pass the state machine gate.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from simu_shared.constants import EventType
from simu_shared.models import TapeEvent
import signal

from simu_sdk.client import ServerClient
from simu_sdk.config import AgentConfig
from simu_sdk.framework.core import BubFramework, Envelope
from simu_sdk.hot_reload import watch_config
from simu_sdk.llm.base import LLMProvider, create_llm_provider
from simu_sdk.memory.metadata import TapeMetadataManager
from simu_sdk.memory.retriever import MemoryRetriever
from simu_sdk.memory.store import MemoryStore
from simu_sdk.tape.context import ContextManager
from simu_sdk.tape.manager import TapeManager
from simu_sdk.tools.registry import ToolRegistry
from simu_sdk.tools.standard import SessionStateManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session state dataclass
# ---------------------------------------------------------------------------

@dataclass
class SessionState:
    """Per-session state for the state machine."""

    session_id: str
    status: Literal["idle", "blocked", "draining"] = "idle"
    pending_tasks: set[str] = field(default_factory=set)
    pending_replies: dict[str, str] = field(default_factory=dict)  # msg_id → awaiting_from
    message_queue: deque[TapeEvent] = field(default_factory=deque)
    parent_id: str | None = None
    depth: int = 0
    goal: str = ""

    def is_idle(self) -> bool:
        return not self.pending_tasks and not self.pending_replies

    def is_blocked(self) -> bool:
        return bool(self.pending_tasks) or bool(self.pending_replies)

    def recompute_status(self) -> None:
        """Derive status from pending state."""
        if self.is_blocked():
            self.status = "blocked"
        elif self.message_queue:
            self.status = "draining"
        else:
            self.status = "idle"


# ---------------------------------------------------------------------------
# SimuAgent
# ---------------------------------------------------------------------------

class SimuAgent:
    """V6 Agent with Bub pipeline core and session state machine.

    The state machine runs OUTSIDE the Bub pipeline:

        on_event()
          ├─ resolve event (task completion / reply) → try unblock
          ├─ session blocked → enqueue
          └─ session idle → framework.process_inbound()
    """

    def __init__(self, config: AgentConfig) -> None:
        self.agent_id = config.agent_id
        self.config = config

        # Communication (kept for lifecycle — SSE, heartbeat, register)
        self.server = ServerClient(config.server_url, config.agent_id, config.agent_token)

        # Legacy session state (used by StandardTools, bridged to new state machine)
        self.session_state = SessionStateManager()

        # LLM
        self.llm: LLMProvider = create_llm_provider(config.llm)
        if config.memory.summary_llm:
            self._summary_llm: LLMProvider = create_llm_provider(config.memory.summary_llm)
        else:
            self._summary_llm = self.llm

        # Tape
        tape_dir = Path(config.config_path) / "tape"
        memory_dir_env = os.environ.get("SIMU_MEMORY_DIR")
        mirror_dir = Path(memory_dir_env) if memory_dir_env else None
        self.tape = TapeManager(tape_dir, agent_id=config.agent_id, memory_dir=mirror_dir)

        # Memory
        memory_dir = Path(config.config_path) / "memory"
        self.metadata_manager = TapeMetadataManager(memory_dir / "metadata.db")
        self.memory_store = MemoryStore(config.agent_id, memory_dir / "chromadb")
        self.memory_retriever = MemoryRetriever(self.metadata_manager, self.memory_store)

        # Context
        self.context_manager = ContextManager(
            self.tape, config.context,
            memory_config=config.memory,
            metadata_manager=self.metadata_manager,
            memory_store=self.memory_store,
            llm=self._summary_llm,
            memory_dir=mirror_dir,
            agent_id=config.agent_id,
        )

        # Tools
        self.tools = ToolRegistry()

        # Personality
        self.soul: str = ""
        self.data_scope: dict[str, Any] = {}
        self._load_personality()

        # Framework core
        self._framework = BubFramework()

        # Session state machine
        self._sessions: dict[str, SessionState] = {}

        # Lifecycle
        self._running = False
        self._heartbeat_task: asyncio.Task | None = None
        self._watch_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Session state machine
    # ------------------------------------------------------------------

    def _get_or_create_session(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
        return self._sessions[session_id]

    def _try_resolve(self, session: SessionState, event: TapeEvent) -> bool:
        """Try to resolve a blocking condition (task completion or reply).

        Returns True if the event was consumed as a resolution event.
        """
        # Task completion
        if event.event_type in (EventType.TASK_FINISHED, EventType.TASK_FAILED):
            task_id = event.payload.get("task_session_id", "")
            if task_id and task_id in session.pending_tasks:
                session.pending_tasks.discard(task_id)
                # Also update legacy SessionStateManager
                self.session_state.remove_pending_task(session.session_id, task_id)
                session.recompute_status()
                return True

        # Reply resolution
        if event.event_type in (EventType.AGENT_MESSAGE, EventType.RESPONSE):
            # Try exact match on parent_event_id
            origin = event.parent_event_id
            if origin and origin in session.pending_replies:
                del session.pending_replies[origin]
                self.session_state.remove_pending_reply(session.session_id, origin)
                session.recompute_status()
                return True
            # Match by sender
            for msg_id, awaiting in list(session.pending_replies.items()):
                if awaiting == event.src:
                    del session.pending_replies[msg_id]
                    self.session_state.clear_reply_from(session.session_id, event.src)
                    session.recompute_status()
                    return True

        return False

    # ------------------------------------------------------------------
    # Event handling — state machine gate
    # ------------------------------------------------------------------

    async def on_event(self, event: TapeEvent) -> None:
        """Main event handler with state machine gating."""
        if event.event_type == EventType.SHUTDOWN:
            await self.stop()
            return

        if event.event_type == EventType.RELOAD_CONFIG:
            self._load_personality()
            return

        session = self._get_or_create_session(event.session_id)

        # 1. Try to resolve a blocking condition
        if self._try_resolve(session, event):
            if session.is_idle():
                # Unblocked — process the resolution event, then drain
                await self._run_pipeline(event)
                await self._drain_queue(session)
            else:
                # Still blocked — queue for later
                session.message_queue.append(event)
            return

        # 2. Session blocked → enqueue
        if session.is_blocked():
            logger.info("Session %s blocked, queuing event %s", event.session_id, event.event_id)
            session.message_queue.append(event)
            return

        # 3. Session idle → enter pipeline
        await self._run_pipeline(event)

    async def _run_pipeline(self, event: TapeEvent) -> None:
        """Run the Bub pipeline for a single event."""
        envelope = Envelope(payload=event)
        turn = await self._framework.process_inbound(envelope)

        # Check if a tool triggered a session transition
        state = turn.state
        if state.new_task_session_id:
            await self._enter_task_session(event, state.new_task_session_id)

    async def _drain_queue(self, session: SessionState) -> None:
        """Process queued messages one by one while session stays idle."""
        session.status = "draining"
        while session.message_queue and session.is_idle():
            event = session.message_queue.popleft()
            logger.info("Draining queued event %s for session %s", event.event_id, session.session_id)
            await self._run_pipeline(event)
            # Pipeline may have re-blocked the session
            if session.is_blocked():
                break
        session.recompute_status()

    async def _enter_task_session(self, parent_event: TapeEvent, task_session_id: str) -> None:
        """Dispatch a synthetic event into a newly created task session."""
        goal = self.session_state.get_goal(task_session_id)
        logger.info("Entering task session %s (goal=%s)", task_session_id, goal)

        # Register in state machine
        parent_session = self._get_or_create_session(parent_event.session_id)
        parent_session.pending_tasks.add(task_session_id)
        parent_session.recompute_status()

        task_session = self._get_or_create_session(task_session_id)
        task_session.parent_id = parent_event.session_id
        task_session.depth = parent_session.depth + 1
        task_session.goal = goal

        # Synthetic kick-off event
        task_event = TapeEvent(
            src=f"agent:{self.agent_id}",
            dst=[f"agent:{self.agent_id}"],
            event_type=EventType.TASK_CREATED,
            payload={"content": f"Task: {goal}", "goal": goal},
            session_id=task_session_id,
            parent_event_id=parent_event.event_id,
        )
        await self._run_pipeline(task_event)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the Agent: register, init subsystems, enter event loop."""
        await self.tape.initialize()
        await self.metadata_manager.initialize()
        await self.memory_store.initialize()

        self.tape.on_first_event = self._handle_first_event

        # Register plugins (lazy import to avoid circular deps)
        from simu_sdk.framework.plugins.tape_plugin import SimuTapePlugin
        from simu_sdk.framework.plugins.context_plugin import SimuContextPlugin
        from simu_sdk.framework.plugins.react_plugin import SimuReActPlugin
        from simu_sdk.framework.plugins.mcp_plugin import MCPClientPlugin
        from simu_sdk.framework.plugins.memory_plugin import SimuMemoryPlugin

        self._framework.register(SimuTapePlugin(self.tape))
        self._framework.register(SimuContextPlugin(
            context_manager=self.context_manager,
            soul=self.soul,
            data_scope=self.data_scope,
            session_state=self.session_state,
        ))
        self._framework.register(SimuMemoryPlugin(self.memory_retriever))
        self._framework.register(SimuReActPlugin(
            llm=self.llm,
            tools=self.tools,
            tape=self.tape,
            server=self.server,
            agent_id=self.agent_id,
            max_iterations=self.config.react.max_iterations,
            max_tool_calls=self.config.react.max_tool_calls,
        ))
        self._framework.register(MCPClientPlugin(
            server=self.server,
            agent_id=self.agent_id,
            session_state=self.session_state,
            context_manager=self.context_manager,
        ))

        await self.server.register(capabilities=self.tools.list_names())
        logger.info("Agent %s registered with Server (V6 framework)", self.agent_id)

        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._watch_task = asyncio.create_task(
            watch_config(self.config.config_path, self._on_config_change),
        )

        await self._event_loop()

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._watch_task:
            self._watch_task.cancel()
        await self.server.deregister()
        await self.memory_store.close()
        await self.metadata_manager.close()
        await self.tape.close()
        if self._summary_llm is not self.llm:
            await self._summary_llm.close()
        await self.llm.close()
        await self.server.close()
        logger.info("Agent %s stopped", self.agent_id)

    async def _event_loop(self) -> None:
        """Receive and dispatch SSE events from Server."""
        async for event in self.server.event_stream():
            if not self._running:
                break
            try:
                await self.on_event(event)
            except Exception as exc:
                logger.exception("Error handling event %s", event.event_id)
                await self.server.report_error(event, exc)

    async def _heartbeat_loop(self) -> None:
        while self._running:
            try:
                await self.server.heartbeat()
            except Exception:
                logger.warning("Heartbeat failed", exc_info=True)
            await asyncio.sleep(30)

    # ------------------------------------------------------------------
    # Personality and callbacks
    # ------------------------------------------------------------------

    def _load_personality(self) -> None:
        soul_path = self.config.config_path / "soul.md"
        if soul_path.exists():
            self.soul = soul_path.read_text(encoding="utf-8")

        scope_path = self.config.config_path / "data_scope.yaml"
        if scope_path.exists():
            self.data_scope = yaml.safe_load(scope_path.read_text(encoding="utf-8")) or {}

    def _on_config_change(self, filename: str) -> None:
        logger.info("Reloading %s for agent %s", filename, self.agent_id)
        self._load_personality()

    async def _handle_first_event(self, event: TapeEvent) -> None:
        if await self.metadata_manager.has_metadata(event.session_id):
            return
        title = await self.context_manager.generate_title(event)
        await self.metadata_manager.create_metadata(event.session_id, title)
        await self.server.update_session_title(event.session_id, title)
        logger.info("Generated title for session %s: %s", event.session_id, title)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _setup_logging(config: AgentConfig) -> None:
    """Configure logging to write to both stderr and a per-agent log file."""
    log_dir = config.config_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "agent.log"

    fmt = f"%(asctime)s [{config.agent_id}] %(name)s %(levelname)s: %(message)s"
    formatter = logging.Formatter(fmt)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(logging.INFO)
    stderr_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(stderr_handler)


def run_agent() -> None:
    """Entry point for running a SimuAgent process.

    Reads config from environment variables, creates the agent, and
    runs until SIGTERM/SIGINT.
    """
    config = AgentConfig.from_env()
    _setup_logging(config)
    agent = SimuAgent(config)

    loop = asyncio.new_event_loop()

    def _shutdown() -> None:
        loop.create_task(agent.stop())

    loop.add_signal_handler(signal.SIGTERM, _shutdown)
    loop.add_signal_handler(signal.SIGINT, _shutdown)

    try:
        loop.run_until_complete(agent.start())
    finally:
        loop.close()
