"""BaseAgent — the foundation class for all simu-emperor Agents.

Subclass ``BaseAgent`` to create a custom Agent.  Override ``on_event``
for custom dispatch logic, or rely on the default which feeds every
event into the ReAct loop.

Minimal usage::

    agent = BaseAgent(AgentConfig.from_env())
    await agent.start()
"""

from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path
from typing import Any

import yaml

from simu_shared.constants import EventType
from simu_shared.models import TapeEvent
from simu_sdk.client import ServerClient
from simu_sdk.config import AgentConfig
from simu_sdk.hot_reload import watch_config
from simu_sdk.llm.base import LLMProvider, create_llm_provider
from simu_sdk.react import ReActLoop, ReActResult
from simu_sdk.tape.context import ContextManager
from simu_sdk.tape.manager import TapeManager
from simu_sdk.tools.registry import ToolRegistry
from simu_sdk.tools.standard import SessionStateManager, StandardTools

logger = logging.getLogger(__name__)


class BaseAgent:
    """Agent SDK base class.

    Manages the full Agent lifecycle: registration, event loop, tool
    execution, tape management, config hot-reload, and graceful shutdown.
    """

    def __init__(self, config: AgentConfig) -> None:
        self.agent_id = config.agent_id
        self.config = config

        # Communication
        self.server = ServerClient(config.server_url, config.agent_id, config.agent_token)

        # Session state management
        self.session_state = SessionStateManager()

        # LLM
        self.llm: LLMProvider = create_llm_provider(config.llm)

        # Tools
        self.tools = ToolRegistry()
        self._standard_tools = StandardTools(self.server, session_state=self.session_state)
        self.tools.register_provider(self._standard_tools)
        self.tools.register_provider(self)  # auto-register @tool methods on subclass

        # ReAct
        self.react_loop = ReActLoop(
            self.llm,
            self.tools,
            max_iterations=config.react.max_iterations,
            max_tool_calls=config.react.max_tool_calls,
        )

        # Tape (local) — stored under the agent's own config directory
        tape_dir = Path(config.config_path) / "tape"
        self.tape = TapeManager(tape_dir)
        self.context_manager = ContextManager(self.tape, config.context)

        # Personality files
        self.soul: str = ""
        self.data_scope: dict[str, Any] = {}
        self._load_personality()

        # Lifecycle
        self._running = False
        self._heartbeat_task: asyncio.Task | None = None
        self._watch_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Personality loading
    # ------------------------------------------------------------------

    def _load_personality(self) -> None:
        soul_path = self.config.config_path / "soul.md"
        if soul_path.exists():
            self.soul = soul_path.read_text(encoding="utf-8")

        scope_path = self.config.config_path / "data_scope.yaml"
        if scope_path.exists():
            self.data_scope = yaml.safe_load(scope_path.read_text(encoding="utf-8")) or {}

    def _on_config_change(self, filename: str) -> None:
        """Callback invoked by hot-reload watcher."""
        logger.info("Reloading %s for agent %s", filename, self.agent_id)
        self._load_personality()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the Agent: register, init tape, enter event loop."""
        await self.tape.initialize()

        await self.server.register(capabilities=self.tools.list_names())
        logger.info("Agent %s registered with Server", self.agent_id)

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
        await self.tape.close()
        await self.llm.close()
        await self.server.close()
        logger.info("Agent %s stopped", self.agent_id)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    async def on_event(self, event: TapeEvent) -> None:
        """Handle an incoming event.  Override for custom dispatch."""
        if event.event_type == EventType.SHUTDOWN:
            await self.stop()
            return

        if event.event_type == EventType.RELOAD_CONFIG:
            self._load_personality()
            return

        # Handle task completion events — unblock parent session
        if event.event_type in (EventType.TASK_FINISHED, EventType.TASK_FAILED):
            await self._handle_task_completion(event)
            return

        # Handle reply events — unblock session waiting for reply
        if event.event_type == EventType.AGENT_MESSAGE:
            cleared = self._try_clear_pending_reply(event)
            if cleared:
                # Reply received — process queued messages if session unblocked
                await self._process_queued_messages(event.session_id)
                return

        # Session-level blocking: if the session has pending tasks/replies, queue the event
        if self.session_state.is_blocked(event.session_id):
            logger.info(
                "Session %s is blocked, queuing event %s",
                event.session_id, event.event_id,
            )
            self.session_state.enqueue_message(event.session_id, event)
            return

        await self.react(event)

    async def _handle_task_completion(self, event: TapeEvent) -> None:
        """Process a TASK_FINISHED or TASK_FAILED event."""
        # Record in tape
        await self.tape.append(event)

        # The event arrives in the parent session — check if it unblocks
        session_id = event.session_id
        # The task_session_id is in the event payload or can be inferred
        # For now, try to unblock by checking if all pending tasks are done
        await self._process_queued_messages(session_id)

    def _try_clear_pending_reply(self, event: TapeEvent) -> bool:
        """Check if this event clears a pending reply. Returns True if it did."""
        session_id = event.session_id
        # Check if the origin_event_id matches a pending reply
        origin = event.parent_event_id
        if origin:
            replies = self.session_state._pending_replies.get(session_id, set())
            if origin in replies:
                self.session_state.remove_pending_reply(session_id, origin)
                return True
        return False

    async def _process_queued_messages(self, session_id: str) -> None:
        """If session is no longer blocked, process queued messages."""
        if self.session_state.is_blocked(session_id):
            return

        queued = self.session_state.drain_queue(session_id)
        for queued_event in queued:
            logger.info(
                "Processing queued event %s for unblocked session %s",
                queued_event.event_id, session_id,
            )
            await self.react(queued_event)

    async def react(self, event: TapeEvent) -> None:
        """Run the ReAct loop for an event."""
        # Determine which session to use (may be redirected to active task session)
        session_id = event.session_id

        # Record the incoming event in local tape
        await self.tape.append(event)

        # Build context window — uses the current session's tape
        context = await self.context_manager.get_context(session_id)

        # Build system prompt
        system_prompt = self._build_system_prompt()

        # Execute ReAct loop
        result = await self.react_loop.run(
            system_prompt=system_prompt,
            event=event,
            context=context,
        )

        # Record the agent response in local tape
        response_event = TapeEvent(
            src=f"agent:{self.agent_id}",
            dst=event.dst,
            event_type=EventType.RESPONSE,
            payload={"content": result.content},
            session_id=session_id,
            parent_event_id=event.event_id,
            root_event_id=event.root_event_id or event.event_id,
            invocation_id=event.invocation_id,
        )
        await self.tape.append(response_event)

        # Send response back to server so it appears in MessageStore / frontend
        # Only send for non-task sessions (task results go via finish_task)
        if result.content and not session_id.startswith("task:"):
            await self.server.post_message(
                recipients=["player"],
                message=result.content,
                session_id=session_id,
            )

        # Report invocation completion
        if event.invocation_id:
            await self.server.complete_invocation(event.invocation_id)

    def _build_system_prompt(self) -> str:
        parts = []
        if self.soul:
            parts.append(self.soul)
        if self.data_scope:
            scope_text = yaml.dump(self.data_scope, allow_unicode=True, default_flow_style=False)
            parts.append(f"\n## Data Access Scope\n\n```yaml\n{scope_text}```")
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Background tasks
    # ------------------------------------------------------------------

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
        """Send periodic heartbeat to the Server."""
        while self._running:
            try:
                await self.server.heartbeat()
            except Exception:
                logger.warning("Heartbeat failed", exc_info=True)
            await asyncio.sleep(30)


# ---------------------------------------------------------------------------
# Convenience entry point for launching an Agent from CLI
# ---------------------------------------------------------------------------

def run_agent(agent_cls: type[BaseAgent] | None = None) -> None:
    """Entry point for running an Agent process.

    Reads config from environment variables, creates the Agent, and
    runs it until SIGTERM/SIGINT.
    """
    config = AgentConfig.from_env()
    agent = (agent_cls or BaseAgent)(config)

    loop = asyncio.new_event_loop()

    def _shutdown() -> None:
        loop.create_task(agent.stop())

    loop.add_signal_handler(signal.SIGTERM, _shutdown)
    loop.add_signal_handler(signal.SIGINT, _shutdown)

    try:
        loop.run_until_complete(agent.start())
    finally:
        loop.close()


if __name__ == "__main__":
    run_agent()
