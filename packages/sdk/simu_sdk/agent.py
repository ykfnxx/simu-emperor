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
import os
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
from simu_sdk.memory.metadata import TapeMetadataManager
from simu_sdk.memory.retriever import MemoryRetriever
from simu_sdk.memory.store import MemoryStore
from simu_sdk.react import ReActLoop
from simu_sdk.tape.context import ContextManager
from simu_sdk.tape.manager import TapeManager
from simu_sdk.tools.memory import MemoryTools
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

        # Summary LLM — separate provider if configured, else share main LLM
        if config.memory.summary_llm:
            self._summary_llm: LLMProvider = create_llm_provider(config.memory.summary_llm)
        else:
            self._summary_llm = self.llm

        # Tape (local) — stored under the agent's own config directory
        # Also mirrors to data/memory/ if SIMU_MEMORY_DIR is set
        tape_dir = Path(config.config_path) / "tape"
        memory_dir_env = os.environ.get("SIMU_MEMORY_DIR")
        mirror_dir = Path(memory_dir_env) if memory_dir_env else None
        self.tape = TapeManager(
            tape_dir,
            agent_id=config.agent_id,
            memory_dir=mirror_dir,
        )

        # Memory system
        memory_dir = Path(config.config_path) / "memory"
        self.metadata_manager = TapeMetadataManager(memory_dir / "metadata.db")
        self.memory_store = MemoryStore(config.agent_id, memory_dir / "chromadb")
        self.memory_retriever = MemoryRetriever(self.metadata_manager, self.memory_store)

        self.context_manager = ContextManager(
            self.tape,
            config.context,
            memory_config=config.memory,
            metadata_manager=self.metadata_manager,
            memory_store=self.memory_store,
            llm=self._summary_llm,
            memory_dir=mirror_dir,
            agent_id=config.agent_id,
        )

        # Tools
        self.tools = ToolRegistry()
        self._standard_tools = StandardTools(
            self.server,
            session_state=self.session_state,
            agent_id=config.agent_id,
        )
        self.tools.register_provider(self._standard_tools)
        self._memory_tools = MemoryTools(self.memory_retriever)
        self.tools.register_provider(self._memory_tools)
        self.tools.register_provider(self)  # auto-register @tool methods on subclass

        # ReAct
        self.react_loop = ReActLoop(
            self.llm,
            self.tools,
            max_iterations=config.react.max_iterations,
            max_tool_calls=config.react.max_tool_calls,
        )

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
        """Start the Agent: register, init tape + memory, enter event loop."""
        await self.tape.initialize()
        await self.metadata_manager.initialize()
        await self.memory_store.initialize()

        # Register first-event callback for title generation
        self.tape.on_first_event = self._handle_first_event

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
        await self.memory_store.close()
        await self.metadata_manager.close()
        await self.tape.close()
        if self._summary_llm is not self.llm:
            await self._summary_llm.close()
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
        # Both AGENT_MESSAGE (initiated messages) and RESPONSE (auto-replies)
        # can serve as replies to a pending await_reply.
        if event.event_type in (EventType.AGENT_MESSAGE, EventType.RESPONSE):
            cleared = self._try_clear_pending_reply(event)
            if cleared:
                if not self.session_state.is_blocked(event.session_id):
                    # Fully unblocked — process the reply, then any queued messages
                    await self.react(event)
                    await self._process_queued_messages(event.session_id)
                else:
                    # Still waiting for more replies — queue the reply for later
                    self.session_state.enqueue_message(event.session_id, event)
                return

        # Session-level blocking: if the session has pending tasks/replies, queue the event
        if self.session_state.is_blocked(event.session_id):
            logger.info(
                "Session %s is blocked, queuing event %s",
                event.session_id,
                event.event_id,
            )
            self.session_state.enqueue_message(event.session_id, event)
            return

        await self.react(event)

    async def _handle_task_completion(self, event: TapeEvent) -> None:
        """Process a TASK_FINISHED or TASK_FAILED event.

        The event arrives on the parent session.  If the session is fully
        unblocked (no more pending tasks/replies), feed the event into the
        ReAct loop so the agent can see the task result and report to the
        player.  Otherwise queue it for later processing.
        """
        session_id = event.session_id

        if not self.session_state.is_blocked(session_id):
            # Parent session unblocked — process the completion event
            await self.react(event)
            await self._process_queued_messages(session_id)
        else:
            # Still blocked (other pending tasks/replies) — queue for later
            await self.tape.append(event)
            self.session_state.enqueue_message(session_id, event)

    def _try_clear_pending_reply(self, event: TapeEvent) -> bool:
        """Clear pending reply matched by sender. Returns True if cleared."""
        session_id = event.session_id

        # Try exact match first (parent_event_id matches a pending reply)
        origin = event.parent_event_id
        if origin:
            replies = self.session_state._pending_replies.get(session_id, {})
            if origin in replies:
                self.session_state.remove_pending_reply(session_id, origin)
                return True

        # Match by sender — the replying agent's send_message creates a
        # fresh event without parent_event_id, so match by event.src.
        if self.session_state.clear_reply_from(session_id, event.src):
            logger.info(
                "Cleared pending reply from %s on session %s",
                event.src,
                session_id,
            )
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
                queued_event.event_id,
                session_id,
            )
            await self.react(queued_event)

    async def react(self, event: TapeEvent) -> None:
        """Run the ReAct loop for an event."""
        session_id = event.session_id

        # Record the incoming event in local tape
        await self.tape.append(event)

        # Build context window — uses the current session's tape
        context = await self.context_manager.get_context(session_id)

        # Build system prompt (context-aware for task sessions)
        system_prompt = self._build_system_prompt(session_id)

        # Execute ReAct loop
        result = await self.react_loop.run(
            system_prompt=system_prompt,
            event=event,
            context=context,
            tape=self.tape,
            agent_id=self.agent_id,
            server=self.server,
        )

        # Record the agent response in local tape and push to server
        response_event = TapeEvent(
            src=f"agent:{self.agent_id}",
            dst=[event.src],
            event_type=EventType.RESPONSE,
            payload={"content": result.content},
            session_id=session_id,
            parent_event_id=event.event_id,
            root_event_id=event.root_event_id or event.event_id,
            invocation_id=event.invocation_id,
        )
        await self.tape.append(response_event)

        # Route RESPONSE to destination agents for agent-to-agent replies.
        # Only when the ReAct loop ended naturally (text output) — if a tool
        # ended the loop (e.g. send_message already routed an AGENT_MESSAGE),
        # routing the RESPONSE would be redundant.
        should_route = (
            result.ended_by_tool is None
            and event.src.startswith("agent:")
            and event.src != f"agent:{self.agent_id}"
        )
        await self.server.push_tape_event(response_event, route=should_route)

        # Update session summary in background — avoid blocking the react
        # loop on LLM summarization (which can take minutes).
        asyncio.create_task(self._update_session_summary(session_id))

        # Handle session transitions triggered by tools
        if result.ended_by_tool == "create_task_session":
            await self._enter_task_session(event)
            return

        # For finish/fail task session, the server sends TASK_FINISHED/FAILED
        # event to the parent session, which is handled by _handle_task_completion.

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

    async def _enter_task_session(self, parent_event: TapeEvent) -> None:
        """Dispatch a synthetic event into a newly created task session."""
        task_session_id = self.session_state.get_active_session()
        if not task_session_id:
            logger.warning("_enter_task_session called but no active session")
            return

        goal = self.session_state.get_goal(task_session_id)
        logger.info(
            "Entering task session %s (goal=%s)",
            task_session_id,
            goal,
        )

        # Create a synthetic event to kick off the task session
        task_event = TapeEvent(
            src=f"agent:{self.agent_id}",
            dst=[f"agent:{self.agent_id}"],
            event_type=EventType.TASK_CREATED,
            payload={"content": f"Task: {goal}", "goal": goal},
            session_id=task_session_id,
            parent_event_id=parent_event.event_id,
        )
        await self.react(task_event)

    async def _handle_first_event(self, event: TapeEvent) -> None:
        """Generate and store a title when a session's first event arrives."""
        if await self.metadata_manager.has_metadata(event.session_id):
            return
        title = await self.context_manager.generate_title(event)
        await self.metadata_manager.create_metadata(event.session_id, title)
        await self.server.update_session_title(event.session_id, title)
        logger.info("Generated title for session %s: %s", event.session_id, title)

    async def _update_session_summary(self, session_id: str) -> None:
        """Update session summary after each agent response."""
        try:
            recent = await self.tape.query(session_id, limit=10)
            await self.context_manager.update_session_summary(session_id, recent)
        except Exception:
            logger.warning(
                "Failed to update session summary for %s",
                session_id,
                exc_info=True,
            )

    def _build_system_prompt(self, session_id: str = "") -> str:
        parts = []
        if self.soul:
            parts.append(self.soul)
        if self.data_scope:
            scope_text = yaml.dump(self.data_scope, allow_unicode=True, default_flow_style=False)
            parts.append(f"\n## Data Access Scope\n\n```yaml\n{scope_text}```")

        # Action execution instructions (only when agent has data_scope)
        if self.data_scope:
            parts.append(self._action_execution_instructions())

        # Context-aware instructions
        if session_id.startswith("task:"):
            goal = self.session_state.get_goal(session_id)
            parts.append(self._task_execution_instructions(goal))
        else:
            parts.append(self._task_dispatch_instructions())

        # Always include reply instructions
        parts.append(self._agent_reply_instructions())

        return "\n\n".join(parts)

    @staticmethod
    def _action_execution_instructions() -> str:
        """Instructions for using create_incident to affect game state."""
        return """## 执行影响游戏状态的指令

当皇帝下达涉及经济、税收、生产等方面的具体指令时，你**必须调用 `create_incident` 工具**来执行，仅口头回复不会产生实际效果。

### 需要调用 `create_incident` 的场景
- 调整税率（如"给直隶加税5%"）→ 对 `tax_modifier` 使用 `add`（注意：`tax_modifier` 是加性修正值，初始为 0，用 `add` 而非 `factor`）
- 增减库存/拨款（如"拨银十万两赈灾"）→ 使用 `stockpile` 或 `imperial_treasury` 的 `add`
- 按比例调整生产/人口 → 对 `production_value` 或 `population` 使用 `factor`
- 任何需要改变省份或国家数值的指令

### add 与 factor 的区别
- **add**：一次性加减固定值。适用于调整修正量（如 `tax_modifier`）、拨款（`stockpile`）等
- **factor**：每 tick 按比例变化，`field *= (1 + factor)`。适用于持续性增减（如产值提升 10% → factor="0.10"）
- **注意**：对当前值为 0 的字段使用 factor 无效（0 乘任何数仍为 0），此时应使用 add

### 关键规则
- **先执行，再汇报**：收到指令后先调用 `create_incident` 创建 incident，再向皇帝回复执行结果
- **不要只回复"遵旨"**：如果指令要求改变数值，必须通过工具调用实际执行
- 你只能修改 Data Access Scope 中列出的字段和省份，超出范围的操作会被拒绝
- 使用 `query_state` 工具可以查询当前数值，帮助你确定合理的参数

### 示例

皇帝指令："给直隶加税5%"
正确做法：调用 `create_incident(title="直隶增税", effects=[{"target_path": "provinces.zhili.tax_modifier", "add": "0.05"}], remaining_ticks=12, description="奉旨增加直隶税率5%")`
错误做法：使用 factor 修改 tax_modifier（tax_modifier 初始值为 0，factor 无效）"""

    @staticmethod
    def _task_dispatch_instructions() -> str:
        return """## 任务派发与跨官员沟通

当玩家的指令涉及其他官员时（例如"问问张廷玉…"、"让各省加税"），按以下流程处理：

1. **查询角色表**：先调用 `query_role_map` 获取官员姓名与 agent_id 的对应关系。
2. **创建任务会话**：调用 `create_task_session`，goal 必须包含**完整的具体指令和数值**（例如"命令江南巡抚将江南税率降低5%"，而不是"让江南巡抚减税"）。
   创建后你会自动进入任务会话上下文。
3. **在任务会话中执行**：在任务会话中调用 `send_message`，设置 `await_reply=true`，向目标 agent 发送询问。
   发送后会话自动暂停等待回复。
4. **收到回复后结束任务**：回复到达后你会被唤醒，调用 `finish_task_session` 并附上汇总结果。
5. **回到主会话**：结束任务后自动回到主会话，你会收到任务完成的通知，此时向 player 汇报结果。

如果需要同时联系多位官员，可以在主会话中依次创建多个任务。

重要规则：
- 必须先用 `query_role_map` 查到 agent_id，不要猜测。
- 与其他官员沟通时始终使用 `await_reply=true`。
- `create_task_session` 的 goal 必须包含玩家指令中的**所有具体数值和细节**，不得遗漏或概括。
- `create_task_session`、`finish_task_session`、`fail_task_session` 调用后会话会自动切换，无需额外操作。
- `send_message(await_reply=true)` 发送后当前会话自动暂停，等待回复后继续。
- 向其他 agent 传达指令时，必须**原样传达玩家的具体数值和要求**，不得自行修改或概括。"""

    @staticmethod
    def _task_execution_instructions(goal: str) -> str:
        """Generate execution instructions for task sessions."""
        return f"""## 当前处于任务会话中

你现在正在执行一个任务，目标是：**{goal}**

你是这个任务的**创建者**，负责执行并结束任务。

在任务会话中，你应该：
1. 直接执行任务 — 查询所需信息、向目标 agent 发送消息等
2. 向其他 agent 传达命令时，必须**原样传达 goal 中的具体数值和要求**
3. 完成后**必须调用 `finish_task_session`**，将结果汇报给主会话
4. 如果无法完成，调用 `fail_task_session` 说明原因

**重要：收到其他 agent 的回复后，不要直接输出文字，而是立即调用 `finish_task_session` 汇总结果。**
直接输出文字不会结束任务，只有调用 `finish_task_session` 才能正确完成任务并返回主会话。

### 工具调用失败处理
- 如果工具调用返回错误（如 `create_incident` 失败），**不得谎称已经执行成功**
- 可以尝试修正参数后重试一次
- 如果仍然失败，必须在 `finish_task_session` 或回复中**如实说明失败原因**
- 接收到其他 agent 回复"未能执行"时，必须**如实向上级传达**，不得篡改结果

### 禁止行为
- **不要直接输出文字回复** — 输出文字无法结束任务
- **不要把工具调用写成文字** — 例如写 `finish_task_session result="..."` 是错误的，必须通过工具调用
- **不要在未收到回复前就结束任务** — 必须等待 `send_message(await_reply=true)` 的回复到达后再行动
- **不要继续对话** — 收到回复后立即结束，不要寒暄或追问
- **禁止在任务会话中再次创建 task session**，除非你发现必须委派给其他 agent 才能完成任务
- **不得在工具调用失败后声称执行成功** — 这是欺君之罪

### 示例流程

假设任务是 "向户部尚书张廷玉询问其身体状况，获取回复后向主会话汇报"：

1. 调用 `query_role_map` 查到张廷玉的 agent_id 是 `minister_of_revenue`
2. 调用 `send_message(recipients=["minister_of_revenue"], message="张廷玉大人，皇上关心您的身体状况，请据实禀报。", await_reply=true)`
3. 等待回复（会话自动暂停）
4. 收到回复后，**立即**调用 `finish_task_session(result="张廷玉回复：臣身体尚好…")`

请立即开始执行任务。"""

    @staticmethod
    def _agent_reply_instructions() -> str:
        """Instructions for replying to messages from other agents."""
        return """## 回复其他官员的消息

当你收到来自其他官员（agent）的消息时，**直接输出文字回复即可**，系统会自动将你的回复发送给对方。

**例外**：如果你是任务创建者并且收到了等待的回复，应调用 `finish_task_session` 结束任务，不要直接输出文字（详见"当前处于任务会话中"的说明）。

### send_message 与直接回复的区别

- **直接回复（输出文字）**：用于**回应**收到的消息。你只需输出回复内容，系统会自动路由给发送者。
- **`send_message` 工具**：用于**主动发起**新的沟通，例如向某位官员询问信息、下达指令等。

### 示例

收到 `agent:governor_jiangnan` 发来的问候消息，正确的回复方式：

直接输出："承蒙挂念，老夫身体尚好…"

**不需要**调用 `send_message` — 系统会自动将你的回复发送给 governor_jiangnan。

### 重要规则
- 回复收到的消息时，直接输出文字，不要调用 `send_message`
- 主动发起沟通时，使用 `send_message` 工具
- **禁止给自己发消息** — `send_message` 的 `recipients` 中不能包含你自己的 agent_id
- 收到命令后执行工具调用，如果工具调用失败，**必须如实回复失败原因**，不得谎称已执行
- 收到包含具体数值的命令（如"减税5%"），必须**严格按照该数值执行**，不得自行修改

### 任务会话中的角色

如果你在一个 task session 中收到消息，但你**不是**这个 task 的创建者（即消息是别人发来的询问），那么：
- 你是任务**参与者**，不是创建者
- **禁止调用 `finish_task_session` 或 `fail_task_session`** — 只有创建者有权结束任务
- 直接输出文字回复即可，系统会自动发送给对方"""

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


def _setup_logging(config: AgentConfig) -> None:
    """Configure logging to write to both stderr and a per-agent log file."""
    log_dir = config.config_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "agent.log"

    fmt = f"%(asctime)s [{config.agent_id}] %(name)s %(levelname)s: %(message)s"
    formatter = logging.Formatter(fmt)

    # File handler — rotating would be nice but keep it simple
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Stderr handler (captured by server's ProcessManager)
    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(logging.INFO)
    stderr_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(stderr_handler)


def run_agent(agent_cls: type[BaseAgent] | None = None) -> None:
    """Entry point for running an Agent process.

    Reads config from environment variables, creates the Agent, and
    runs it until SIGTERM/SIGINT.
    """
    config = AgentConfig.from_env()
    _setup_logging(config)
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
