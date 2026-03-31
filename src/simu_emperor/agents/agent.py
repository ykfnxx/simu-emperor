"""
Agent 基类 - 文件驱动的 AI 官员

基于 Function Calling 的架构：
- 只响应事件，不主动发起
- 根据事件类型选择不同的 system prompt
- Skills 注册为 function calls
- LLM 自主决定调用哪些 functions
"""

import asyncio
import json
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from simu_emperor.agents.config import AgentConfig, AgentState
from simu_emperor.agents.react_loop import ReActLoop
from simu_emperor.agents.system_prompts import get_system_prompt
from simu_emperor.agents.tools import ActionTools, QueryTools
from simu_emperor.agents.tools.registry import ToolRegistry
from simu_emperor.agents.utils import write_llm_log
from simu_emperor.config import settings
from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.llm.base import LLMProvider

if TYPE_CHECKING:
    from simu_emperor.session.manager import SessionManager


logger = logging.getLogger(__name__)


class Agent:
    """
    AI 官员 Agent

    文件驱动的被动 Agent：
    - 只响应事件，不主动发起
    - personality 和权限由文件定义（soul.md, data_scope.yaml）
    - 使用 function calling 让 LLM 决定调用哪些 skills
    - 根据事件类型使用不同的 system prompt

    Attributes:
        agent_id: Agent 唯一标识符
        event_bus: 事件总线
        llm_provider: LLM 提供商
        data_dir: 数据目录
    """

    def __init__(self, config: AgentConfig):
        self.agent_id = config.agent_id
        self.event_bus = config.event_bus
        self.llm_provider = config.llm_provider
        self.data_dir = Path(config.data_dir)
        self.repository = config.repository
        self.session_id = config.session_id
        self._skill_loader = config.skill_loader
        self.session_manager = config.session_manager

        # 加载 soul 和 data_scope
        self._soul: str | None = None
        self._data_scope: dict[str, Any] | None = None
        self._load_soul()
        self._load_data_scope()

        # V4.1: 使用注入的实例（不再创建自己的副本）
        self._tape_writer = config.tape_writer
        self._tape_metadata_mgr = config.tape_metadata_mgr
        self._tape_repository = config.tape_repository

        # V4.1: Use configured memory_dir
        self._memory_dir = Path(settings.memory.memory_dir).resolve()

        # 初始化工具类
        self._query_tools = QueryTools(
            agent_id=self.agent_id,
            repository=self.repository,
            data_dir=self.data_dir,
            engine=config.engine,
        )
        self._action_tools = ActionTools(
            agent_id=self.agent_id,
            event_bus=self.event_bus,
            data_dir=self.data_dir,
            session_manager=self.session_manager,
            on_soul_updated=self._load_soul,
        )

        # ContextManager - 用于当前session的上下文管理
        self._context_manager = None  # 延迟初始化，需要session_id
        self._memory_tools = None  # 延迟初始化，需要session_id

        # Task Session 工具（V4）
        if self.session_manager:
            from simu_emperor.agents.tools.task_session_tools import TaskSessionTools

            self._task_session_tools = TaskSessionTools(
                agent_id=self.agent_id,
                session_manager=self.session_manager,
                event_bus=self.event_bus,
            )
        else:
            self._task_session_tools = None

        # 初始化独立日志
        self._init_agent_logger()

        # 初始化工具注册表并注册所有工具
        self._tool_registry = ToolRegistry()
        self._register_tools()

        # 初始化 ReAct 循环（Phase 2: 从 Agent 中提取）
        self._react_loop = ReActLoop(
            agent_id=self.agent_id,
            llm_provider=self.llm_provider,
            tool_registry=self._tool_registry,
            event_bus=self.event_bus,
            get_context_manager=lambda: self._context_manager,
            tape_writer=self._tape_writer,
            agent_logger=self._agent_logger,
            llm_log_path=self._llm_log_path,
            call_function=self._call_function_with_result,
            get_root_event_type=self._get_root_event_type,
            get_system_prompt=self._get_system_prompt_for_event,
            check_and_restore_state=self._check_and_restore_agent_state,
        )

        # 初始化记忆系统初始化器
        from simu_emperor.agents.memory_initializer import MemoryInitializer

        self._memory_initializer = MemoryInitializer(
            self.agent_id,
            self._memory_dir,
            self.llm_provider,
            tape_writer=self._tape_writer,
            tape_metadata_mgr=self._tape_metadata_mgr,
            tape_repository=self._tape_repository,
        )

        # 自主记忆反思计数器
        self._memory_tick_counter = 0

        # V4.2: Event queue for backpressure
        self._event_queue: asyncio.Queue | None = None
        self._queue_task: asyncio.Task | None = None
        self._running = False

        logger.info(f"Agent {config.agent_id} initialized")

    def _init_agent_logger(self) -> None:
        """初始化 Agent 独立日志"""
        log_dir = Path("logs/agents")
        log_dir.mkdir(parents=True, exist_ok=True)

        # 常规日志（按天轮转，保留 7 天）
        self._agent_logger = logging.getLogger(f"agent.{self.agent_id}")

        # 防止重复添加handler
        if not self._agent_logger.handlers:
            handler = logging.handlers.TimedRotatingFileHandler(
                log_dir / f"{self.agent_id}.log",
                when="midnight",
                interval=1,
                backupCount=7,
                encoding="utf-8",
            )
            formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
            handler.setFormatter(formatter)
            self._agent_logger.addHandler(handler)

        # 确保日志级别设置正确
        self._agent_logger.setLevel(logging.INFO)
        # 确保不传播到父logger，避免重复日志
        self._agent_logger.propagate = False

        # LLM 日志文件路径
        self._llm_log_path = log_dir / f"{self.agent_id}_llm.jsonl"

    def _register_tools(self) -> None:
        """Register all tools via decorator-based discovery."""
        self._tool_registry.register_provider(self._query_tools)
        self._tool_registry.register_provider(self._action_tools)
        if self._task_session_tools:
            self._tool_registry.register_provider(self._task_session_tools)
        self._register_memory_tools()

    def _register_memory_tools(self) -> None:
        """Register memory tool (uses wrapper for lazy init)."""
        from simu_emperor.agents.tools.registry import tool as tool_dec

        @tool_dec(
            name="retrieve_memory",
            description="检索历史记忆",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
            category="memory",
        )
        async def retrieve_memory_wrapper(args: dict, event: Event) -> str:
            return await self._retrieve_memory_wrapper(args, event)

        self._tool_registry.register_tool(
            "retrieve_memory", retrieve_memory_wrapper._tool_meta, retrieve_memory_wrapper
        )

    def _log_event(self, action: str, event: Event, message: str = "") -> None:
        """记录事件日志"""
        event_short = event.event_id[:8] if event.event_id else "unknown"
        session_short = event.session_id[-8:] if event.session_id else "unknown"
        msg = f"[EVT:{event_short}] [SES:{session_short}] [{action}] {message}"
        self._agent_logger.info(msg)

    def _log_llm_call(
        self,
        event_id: str,
        session_id: str,
        iteration: int,
        request: dict,
        response: dict,
        duration_ms: float,
    ) -> None:
        write_llm_log(
            self._llm_log_path,
            event_id=event_id,
            session_id=session_id,
            iteration=iteration,
            model=getattr(self.llm_provider, "model", "unknown"),
            request=request,
            response=response,
            duration_ms=duration_ms,
        )

    async def _ensure_memory_components(self, session_id: str) -> None:
        if (
            not self._context_manager
            or not self._memory_tools
            or self._context_manager.session_id != session_id
        ):
            self._context_manager, self._memory_tools = await self._memory_initializer.initialize(
                session_id
            )
            self._action_tools.set_context_manager(self._context_manager)

    async def _retrieve_memory_wrapper(self, args: dict, event: Event) -> str:
        await self._ensure_memory_components(event.session_id)
        return await self._memory_tools.retrieve_memory(args, event)

    def _count_tokens(self, text: str | Event | dict) -> int:
        raw = (
            text
            if isinstance(text, str)
            else text.to_json()
            if isinstance(text, Event)
            else json.dumps(text, ensure_ascii=False)
        )
        try:
            import tiktoken

            return len(tiktoken.encoding_for_model("gpt-4").encode(raw))
        except Exception:
            return len(raw) // 2

    def start(self) -> None:
        """
        启动 Agent

        订阅发往此 Agent 的事件（精确匹配）。

        注意：不订阅 '*'，因为发给特定agent的事件会通过 '*' 再次路由，导致重复处理。
        广播事件（TICK_COMPLETED）通过 EventBus 的路由规则自动处理。
        """
        logger.info(f"🚀 [Agent:{self.agent_id}] Starting agent...")

        handler = self._enqueue_event if settings.agent_queue.enabled else self._on_event

        # 只订阅精确匹配（发给自己的事件）
        self.event_bus.subscribe(f"agent:{self.agent_id}", handler)
        logger.debug(f"  ✅ [Agent:{self.agent_id}] Subscribed to agent:{self.agent_id}")

        # 检查事件dst是否为["*"]（广播），如果是则处理
        async def conditional_handler(event: Event) -> None:
            if event.dst == ["*"]:
                await handler(event)

        self.event_bus.subscribe("*", conditional_handler)
        logger.debug(f"  ✅ [Agent:{self.agent_id}] Subscribed to * (broadcast only)")

        logger.info(f"✅ Agent {self.agent_id} started")

    def stop(self) -> None:
        """停止 Agent"""
        handler = self._enqueue_event if settings.agent_queue.enabled else self._on_event
        self.event_bus.unsubscribe(f"agent:{self.agent_id}", handler)
        logger.info(f"Agent {self.agent_id} stopped")

    def start_queue_consumer(self) -> None:
        """V4.2: Start the event queue consumer for backpressure handling."""
        if not settings.agent_queue.enabled:
            return

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return

        max_size = settings.agent_queue.max_size
        self._event_queue = asyncio.Queue(maxsize=max_size if max_size > 0 else 0)
        self._running = True
        self._queue_task = asyncio.create_task(self._queue_consumer_loop())
        logger.info(f"Agent {self.agent_id} queue consumer started (max_size={max_size})")

    async def stop_queue_consumer(self) -> None:
        """V4.2: Stop the event queue consumer gracefully."""
        if not self._running:
            return

        self._running = False

        if self._queue_task and not self._queue_task.done():
            self._queue_task.cancel()
            try:
                await self._queue_task
            except asyncio.CancelledError:
                pass

        self._event_queue = None
        self._queue_task = None
        logger.info(f"Agent {self.agent_id} queue consumer stopped")

    async def _enqueue_event(self, event: Event) -> None:
        """V4.2: Enqueue event for serial processing with backpressure."""
        if not self._event_queue or not self._running:
            await self._on_event(event)
            return

        if self._event_queue.full() and self._event_queue.maxsize > 0:
            try:
                dropped = self._event_queue.get_nowait()
                logger.warning(
                    f"Queue full for agent {self.agent_id}, dropping oldest event {dropped.event_id}"
                )
            except asyncio.QueueEmpty:
                pass

        await self._event_queue.put(event)

    async def _queue_consumer_loop(self) -> None:
        """V4.2: Consumer loop that processes events serially from the queue."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                await self._on_event(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Agent {self.agent_id} queue consumer error: {e}", exc_info=True)

    async def _on_event(self, event: Event) -> None:
        """
        统一的事件处理入口（Agent Loop）

        流程：
        1. 过滤事件
        2. V4: Tick 驱动的元数据刷新
        3. 初始化记忆组件
        4. 多轮 LLM 调用（ContextManager 自动处理 tape 写入）

        Args:
            event: 事件对象
        """
        # 1. 过滤事件（基于目标地址和 agent 状态）
        if not await self._should_process_event(event):
            return

        # 2. V4: Tick 驱动的元数据刷新（在 LLM 处理之前）
        if event.type == EventType.TICK_COMPLETED:
            await self._refresh_memory_metadata(event)
            self._memory_tick_counter += 1
            if self._should_do_memory_reflection():
                await self._ensure_memory_components(event.session_id)
                await self._react_loop.run(event, event.session_id)
            return

        # 3. 记录日志和初始化记忆组件
        session_id = event.session_id
        event_id = event.id if hasattr(event, "id") else "unknown"
        self._log_event("RECV", event, f"{event.type} from {event.src}")
        logger.info(
            f"📨 [Agent:{self.agent_id}:{session_id}] Received {event.type} event (id={event_id}) from {event.src}"
        )

        await self._ensure_memory_components(event.session_id)

        # 4. 处理事件（V4: ContextManager 自动处理所有 tape 写入）
        try:
            await self._react_loop.run(event, session_id)
        except Exception as e:
            logger.error(
                f"❌ [Agent:{self.agent_id}:{session_id}] Error processing event: {e}",
                exc_info=True,
            )

    async def _should_process_event(self, event: Event) -> bool:
        """检查 agent 是否应该处理此事件（基于状态和事件类型）

        规则：
        1. 目标地址必须匹配
        2. 如果 agent 处于 WAITING_REPLY 状态，只处理特定事件：
           - AGENT_MESSAGE (其他 agent 的回复)
           - TASK_FINISHED / TASK_FAILED (任务完成通知)
        3. 其他情况下正常处理所有事件
        """
        # 检查目标地址
        if not (
            f"agent:{self.agent_id}" in event.dst or "agent:*" in event.dst or "*" in event.dst
        ):
            return False

        # 如果没有 session_manager，无法检查状态，默认处理
        if not self.session_manager:
            return True

        # 获取 session 状态
        session = await self.session_manager.get_session(event.session_id)
        if not session:
            return True  # session 不存在，默认处理

        # 获取当前 agent 在此 session 中的状态
        agent_state = await self.session_manager.get_agent_state(event.session_id, self.agent_id)

        # 如果状态是 WAITING_REPLY，只处理特定事件
        if agent_state == AgentState.WAITING_REPLY:
            return event.type in (
                EventType.AGENT_MESSAGE,  # 其他 agent 的回复
                EventType.TASK_FINISHED,  # 任务完成
                EventType.TASK_FAILED,  # 任务失败
            )

        return True

    async def _check_and_restore_agent_state(self, event: Event, session_id: str) -> bool:
        """检查并恢复 agent 状态

        检查是否有尚待完成的异步任务：
        - 如果收到 AGENT_MESSAGE 事件，调用 decrement_async_replies 减少计数
        - 如果计数归零，自动恢复为 ACTIVE 状态
        - 如果还有待完成的任务，返回 False

        Args:
            event: 当前事件
            session_id: 会话 ID

        Returns:
            是否应该继续处理事件
        """
        if not self.session_manager:
            return True

        session = await self.session_manager.get_session(session_id)
        if not session:
            return True

        agent_key = f"agent:{self.agent_id}"
        my_pending = session.pending_async_replies.get(agent_key, 0)

        # 如果收到 AGENT_MESSAGE，说明收到了回复，减少异步回复计数
        if event.type == EventType.AGENT_MESSAGE and my_pending > 0:
            all_received, remaining = await self.session_manager.decrement_async_replies(
                session_id, agent_key, count=1
            )
            if all_received:
                logger.info(
                    f"✅ [Agent:{self.agent_id}:{session_id}] All async replies received, state restored to ACTIVE"
                )
            else:
                logger.info(
                    f"⏳ [Agent:{self.agent_id}:{session_id}] Reply received, {remaining} pending async replies remaining"
                )
                return False

        # 如果还有待完成的异步任务，不处理此事件
        my_pending = session.pending_async_replies.get(agent_key, 0)
        if my_pending > 0:
            logger.info(
                f"⏳ [Agent:{self.agent_id}:{session_id}] Has {my_pending} pending async replies, skipping processing"
            )
            return False

        return True

    async def _get_root_event_type(self, event: Event, session_id: str) -> str:
        """
        获取会话的根事件类型（用于确定使用哪个 system prompt）

        策略：
        1. 如果当前事件就是根事件（root_event_id == event_id），直接返回其类型
        2. 否则，从 tape 读取第一个事件作为根事件

        Args:
            event: 当前事件
            session_id: 会话 ID

        Returns:
            根事件类型
        """
        # 1. 如果当前事件就是根事件，直接返回其类型
        if event.root_event_id == event.event_id or not event.root_event_id:
            return event.type

        # 2. 从 tape 读取第一个事件（根事件）
        try:
            from simu_emperor.common import FileOperationsHelper

            tape_path = self._tape_writer._get_tape_path(session_id, self.agent_id)
            events = await FileOperationsHelper.read_jsonl_file(tape_path)
            if events and len(events) > 0:
                return events[0].get("type", event.type)
        except Exception as e:
            logger.warning(f"Failed to read root event type from tape: {e}")

        # 3. 降级：返回当前事件类型
        return event.type

    def _get_system_prompt_for_event(self, event_type: str) -> str:
        soul_part = f"# 你的角色\n{self._soul}\n" if self._soul else ""
        scope_part = self._build_scope_part()
        task_part = self._resolve_task_instruction(event_type)
        return "\n".join(filter(None, [soul_part, scope_part, task_part])).strip()

    def _build_scope_part(self) -> str:
        if not self._data_scope:
            return ""
        import yaml

        scope_yaml = yaml.dump(self._data_scope, allow_unicode=True)
        return f"# 数据权限\n```yaml\n{scope_yaml}```\n"

    def _resolve_task_instruction(self, event_type: str) -> str:
        if not self._skill_loader:
            return self._get_hardcoded_instruction(event_type)
        skill_name = self._skill_loader.registry.get_skill_for_event(event_type)
        if not skill_name:
            return self._get_hardcoded_instruction(event_type)
        skill = self._skill_loader.load(skill_name)
        if skill:
            return self._inject_skill_variables(skill.content)
        return self._get_hardcoded_instruction(event_type)

    def event_to_messages(self, event: Event) -> dict:
        """
        将单个事件转换为一条 message（不组装上下文）

        Args:
            event: 事件对象

        Returns:
            单条 message，格式：{"role": "user" | "assistant" | "tool", "content": "..."}
        """
        # OBSERVATION → user (观察结果，用于 ReAct 循环)
        if event.type == EventType.OBSERVATION:
            parts = ["# 观察结果 (Observation)"]
            thought = event.payload.get("thought", "")
            if thought:
                parts.append(f"\n## 思考\n{thought}")

            actions = event.payload.get("actions", [])
            if actions:
                parts.append("\n## 执行的操作")
                for action in actions:
                    tool = action.get("tool", "")
                    result = action.get("result", "")
                    parts.append(f"- **{tool}**: {result[:200]}...")

            return {"role": "assistant", "content": "\n".join(parts)}

        # 4. 其他事件 → user (内联构建内容)
        parts = [
            "# 收到的事件",
            f"- 来源: {event.src}",
            f"- 类型: {event.type}",
            f"- 时间: {event.timestamp}",
        ]

        # CHAT
        if event.type == EventType.CHAT and event.payload:
            message = event.payload.get("message", "")
            if message:
                parts.extend(["\n# 皇帝的消息：", f"```\n{message}\n```"])

        # AGENT_MESSAGE
        elif event.type == EventType.AGENT_MESSAGE and event.payload:
            message = event.payload.get("message", "") or event.payload.get("content", "")
            source = event.src.replace("agent:", "")
            if message:
                parts.extend([f"\n# 来自 {source} 的消息：", f"```\n{message}\n```"])
            await_reply = event.payload.get("await_reply", False)
            if await_reply:
                parts.append("\n⚠️ 对方期待你的回复。")

            # Inject task session role context
            if event.session_id and event.session_id.startswith("task:"):
                segments = event.session_id.split(":")
                task_creator = segments[1] if len(segments) > 1 else ""
                if task_creator == self.agent_id:
                    parts.append(
                        "\n**[角色：你是此任务的创建者] 对方是对你之前消息的回复。"
                        "评估任务目标是否已完成，如果完成则调用 `finish_task_session`。**"
                    )
                else:
                    parts.append(
                        f"\n**[角色：你是此任务的参与者，由 {task_creator} 创建] "
                        '你需要回复对方。禁止调用 finish_task_session 或 send_message(recipients=["player"])。**'
                    )

        # TASK_FINISHED
        elif event.type == EventType.TASK_FINISHED and event.payload:
            result = event.payload.get("result", "")
            if result:
                parts.extend(["\n# 任务已完成", f"```\n{result}\n```"])

        # TASK_FAILED
        elif event.type == EventType.TASK_FAILED and event.payload:
            reason = event.payload.get("reason", "")
            if reason:
                parts.extend(["\n# 任务失败", f"```\n{reason}\n```"])

        # TASK_TIMEOUT
        elif event.type == EventType.TASK_TIMEOUT and event.payload:
            task_session_id = event.payload.get("task_session_id", "")
            if task_session_id:
                parts.extend(["\n# 任务超时", f"任务会话 {task_session_id} 已超时"])

        # TICK_COMPLETED
        elif event.type == EventType.TICK_COMPLETED and event.payload:
            tick = event.payload.get("tick", 0)
            parts.extend(
                [
                    "\n# ⏰ Tick 已完成",
                    f"游戏时间推进了一周（Tick {tick}）。",
                ]
            )

        # 其他 payload
        if event.payload and event.type != EventType.CHAT:
            display_payload = {k: v for k, v in event.payload.items() if not k.startswith("_")}
            if display_payload:
                parts.extend(
                    [
                        "\n# 其他信息：",
                        f"```json\n{json.dumps(display_payload, ensure_ascii=False)}\n```",
                    ]
                )

        return {"role": "user", "content": "\n".join(parts)}

    def _inject_skill_variables(self, content: str) -> str:
        """
        注入动态变量到 Skill 内容

        Args:
            content: Skill 内容（可能包含变量占位符）

        Returns:
            注入变量后的内容
        """

        variables = {
            "{{agent_id}}": self.agent_id,
            "{{turn}}": str(self._get_current_turn()),
            "{{timestamp}}": datetime.now().isoformat(),
        }

        for key, value in variables.items():
            content = content.replace(key, value)

        return content

    def _get_current_turn(self) -> int:
        """
        获取当前回合数

        Returns:
            当前回合数，如果无法获取则返回 1
        """
        if self.repository:
            try:
                state = self.repository.load_game_state()
                return state.turn if state else 1
            except Exception:
                pass
        return 1

    def _get_hardcoded_instruction(self, event_type: str) -> str:
        """
        获取硬编码的任务指令（回退机制）

        Args:
            event_type: 事件类型

        Returns:
            任务指令
        """
        return get_system_prompt(event_type)

    async def _call_function_with_result(
        self, function_name: str, arguments: dict, original_event: Event
    ) -> str:
        session_id = original_event.session_id

        logger.info(f"🎯 [Agent:{self.agent_id}:{session_id}] Executing function: {function_name}")
        logger.debug(f"📋 [Agent:{self.agent_id}:{session_id}] Function arguments: {arguments}")

        try:
            handler = self._tool_registry.get_handler(function_name)
            if handler is None:
                return f"❌ 未知工具: {function_name}"

            result = await handler(arguments, original_event)
            return result

        except Exception as e:
            error_msg = f"❌ 工具执行失败: {e}"
            logger.error(f"❌ [Agent:{self.agent_id}:{session_id}] {error_msg}", exc_info=True)
            return error_msg

    def _load_soul(self) -> None:
        """加载 soul.md"""
        soul_path = self.data_dir / "soul.md"

        if soul_path.exists():
            with open(soul_path, "r", encoding="utf-8") as f:
                self._soul = f.read()
            logger.info(f"Agent {self.agent_id} loaded soul from {soul_path}")
        else:
            logger.warning(f"Soul file not found: {soul_path}")
            self._soul = "# Default Soul\nYou are a loyal official."

    def _load_data_scope(self) -> None:
        """加载 data_scope.yaml"""
        import yaml

        scope_path = self.data_dir / "data_scope.yaml"

        if scope_path.exists():
            with open(scope_path, "r", encoding="utf-8") as f:
                self._data_scope = yaml.safe_load(f)
            logger.info(f"Agent {self.agent_id} loaded data_scope from {scope_path}")
        else:
            logger.warning(f"Data scope file not found: {scope_path}")
            self._data_scope = {}

    def _should_do_memory_reflection(self) -> bool:
        """检查是否应该进行自主记忆反思"""
        config = settings.autonomous_memory
        if not config.enabled:
            return False
        return self._memory_tick_counter % config.check_interval_ticks == 0

    async def _refresh_memory_metadata(self, event: Event) -> None:
        """
        V4: Tick 驱动的元数据刷新

        在收到 TICK_COMPLETED 事件时，刷新 tape_meta.jsonl 中当前 session 的元数据。

        Args:
            event: TICK_COMPLETED 事件，payload 包含 {"tick": int}
        """
        current_tick = event.payload.get("tick")

        try:
            await self._tape_metadata_mgr.append_or_update_entry(
                agent_id=self.agent_id,
                session_id=event.session_id,
                first_event=None,  # 更新模式，不需要 first_event
                llm=self.llm_provider,
                current_tick=current_tick,
            )
            logger.debug(
                f"🔄 [Agent:{self.agent_id}] Refreshed memory metadata for session {event.session_id} at tick {current_tick}"
            )
        except Exception as e:
            logger.warning(f"Failed to refresh metadata: {e}")
