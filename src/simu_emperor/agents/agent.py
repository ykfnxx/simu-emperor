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
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from simu_emperor.agents.system_prompts import get_system_prompt
from simu_emperor.agents.tool_definitions import AVAILABLE_FUNCTIONS
from simu_emperor.agents.tools import ActionTools, QueryTools
from simu_emperor.config import settings
from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event import Event as TapeEvent
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.llm.base import LLMProvider
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

    def __init__(
        self,
        agent_id: str,
        event_bus: EventBus,
        llm_provider: LLMProvider,
        data_dir: str | Path,
        repository=None,
        session_id: str | None = None,
        skill_loader=None,
        session_manager=SessionManager,
    ):
        """
        初始化 Agent

        Args:
            agent_id: Agent 唯一标识符
            event_bus: 事件总线
            llm_provider: LLM 提供商
            data_dir: 数据目录（包含 soul.md 和 data_scope.yaml）
            repository: GameRepository（用于数据查询）
            session_id: 会话标识符（用于 Context 组装）
            skill_loader: SkillLoader 实例（用于动态加载 Skill 内容）
            session_manager: SessionManager（V4 Task Session 支持）
        """
        self.agent_id = agent_id
        self.event_bus = event_bus
        self.llm_provider = llm_provider
        self.data_dir = Path(data_dir)
        self.repository = repository
        self.session_id = session_id
        self._skill_loader = skill_loader
        self.session_manager = session_manager

        # 加载 soul 和 data_scope
        self._soul: str | None = None
        self._data_scope: dict[str, Any] | None = None
        self._load_soul()
        self._load_data_scope()

        # 初始化记忆系统组件（V3）- 必须在工具类之前初始化
        from simu_emperor.memory.tape_writer import TapeWriter
        from simu_emperor.memory.manifest_index import ManifestIndex

        # Use configured memory_dir
        # Resolve to absolute path (relative to cwd when not absolute)
        # This ensures all agents use the same centralized memory directory
        self._memory_dir = Path(settings.memory.memory_dir).resolve()

        self._tape_writer = TapeWriter(memory_dir=self._memory_dir)
        self._manifest_index = ManifestIndex(memory_dir=self._memory_dir)

        # 初始化工具类
        self._query_tools = QueryTools(
            agent_id=self.agent_id,
            repository=self.repository,
            data_dir=self.data_dir,
        )
        self._action_tools = ActionTools(
            agent_id=self.agent_id,
            event_bus=self.event_bus,
            data_dir=self.data_dir,
            session_manager=self.session_manager,
            tape_writer=self._tape_writer,
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

        # 初始化工具注册表（未来版本将取代_function_handlers）
        from simu_emperor.agents.tools.tool_registry import ToolRegistry

        self._tool_registry = ToolRegistry()

        # 初始化记忆系统初始化器
        from simu_emperor.agents.memory_initializer import MemoryInitializer

        self._memory_initializer = MemoryInitializer(
            self.agent_id,
            self._memory_dir,
            self.llm_provider,
        )

        # 初始化函数处理器映射（保持向后兼容）
        self._function_handlers: dict[str, callable] = {}
        self._init_function_handlers()

        logger.info(f"Agent {agent_id} initialized")

    def _init_agent_logger(self) -> None:
        """初始化 Agent 独立日志"""
        log_dir = Path("logs/agents")
        log_dir.mkdir(parents=True, exist_ok=True)

        # 常规日志（按天轮转，保留 7 天）
        self._agent_logger = logging.getLogger(f"agent.{self.agent_id}")
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
        self._agent_logger.setLevel(logging.INFO)

        # LLM 日志文件路径
        self._llm_log_path = log_dir / f"{self.agent_id}_llm.jsonl"

    def _init_function_handlers(self) -> None:
        """
        初始化函数处理器映射表

        将函数名映射到对应的处理方法，避免大量的 if-elif 语句
        """
        # Query 类函数 - 直接返回结果
        self._function_handlers.update(
            {
                "query_province_data": self._query_tools.query_province_data,
                "query_national_data": self._query_tools.query_national_data,
                "list_provinces": self._query_tools.list_provinces,
                "list_agents": self._query_tools.list_agents,
                "get_agent_info": self._query_tools.get_agent_info,
            }
        )

        # Memory 类函数 - 记忆检索
        # Note: MemoryTools 延迟初始化，在 _ensure_memory_components 中处理
        self._function_handlers["retrieve_memory"] = self._retrieve_memory_wrapper

        # Action 类函数 - 执行后返回成功消息
        # 使用包装器将无返回值的函数转换为返回成功消息
        action_handlers = {
            "send_message_to_agent": (
                self._action_tools.send_message_to_agent,
                "✅ 消息已发送给其他官员",
            ),
            "respond_to_player": (self._action_tools.respond_to_player, "✅ 响应已发送给玩家"),
            "finish_loop": (self._action_tools.finish_loop, "✅ finish_loop 已执行"),
        }

        for func_name, (handler, success_msg) in action_handlers.items():
            self._function_handlers[func_name] = self._create_action_wrapper(handler, success_msg)

        # Task Session 类函数（V4）
        if self._task_session_tools:
            task_handlers = {
                "create_task_session": self._wrap_create_task_session,
                "finish_task_session": self._wrap_finish_task_session,
                "fail_task_session": self._wrap_fail_task_session,
            }
            self._function_handlers.update(task_handlers)

    async def _wrap_create_task_session(self, args: dict, event: Event) -> str:
        """包装 create_task_session 以符合 Agent 调用约定"""
        import json

        result = await self._task_session_tools.create_task_session(
            timeout_seconds=args.get("timeout_seconds", 300),
            description=args.get("description", ""),
            current_session_id=event.session_id,
        )
        return json.dumps(result, ensure_ascii=False)

    async def _wrap_finish_task_session(self, args: dict, event: Event) -> str:
        """包装 finish_task_session 以符合 Agent 调用约定

        注意：此工具只能从任务会话（task session）内部调用。
        从主会话（main session）调用将返回错误。
        """
        import json

        # 获取当前会话
        session = await self.session_manager.get_session(event.session_id)
        if not session:
            return json.dumps(
                {"success": False, "error": "Session not found"},
                ensure_ascii=False,
            )

        # 只能从任务会话中调用
        if not session.is_task:
            return json.dumps(
                {
                    "success": False,
                    "error": "finish_task_session can only be called from a task session, not from main session",
                },
                ensure_ascii=False,
            )

        # 直接使用当前 session_id（因为它就是 task session）
        result = await self._task_session_tools.finish_task_session(
            task_session_id=event.session_id,
            result=args.get("result", ""),
        )
        return json.dumps(result, ensure_ascii=False)

    async def _wrap_fail_task_session(self, args: dict, event: Event) -> str:
        """包装 fail_task_session 以符合 Agent 调用约定

        注意：此工具只能从任务会话（task session）内部调用。
        从主会话（main session）调用将返回错误。
        """
        import json

        # 获取当前会话
        session = await self.session_manager.get_session(event.session_id)
        if not session:
            return json.dumps(
                {"success": False, "error": "Session not found"},
                ensure_ascii=False,
            )

        # 只能从任务会话中调用
        if not session.is_task:
            return json.dumps(
                {
                    "success": False,
                    "error": "fail_task_session can only be called from a task session, not from main session",
                },
                ensure_ascii=False,
            )

        # 直接使用当前 session_id（因为它就是 task session）
        result = await self._task_session_tools.fail_task_session(
            task_session_id=event.session_id,
            reason=args.get("reason", ""),
        )
        return json.dumps(result, ensure_ascii=False)

    @staticmethod
    def _create_action_wrapper(handler_func: callable, success_message: str) -> callable:
        """
        为动作处理函数创建包装器，使其返回标准化的成功消息

        Args:
            handler_func: 原始动作处理函数（可返回 str 表示自定义消息）
            success_message: 执行成功后返回的消息（当 handler 不返回自定义消息时使用）

        Returns:
            包装后的异步函数（返回成功消息或 handler 的自定义消息）

        Note:
            如果 handler 返回非空字符串，则使用该返回值（支持错误消息）
            否则使用默认的 success_message
        """

        async def wrapper(args: dict, event: Event) -> str:
            result = await handler_func(args, event)
            # If handler returns a non-empty string, use it (supports custom messages like errors)
            # Otherwise, use the default success message
            if isinstance(result, str) and result.strip():
                return result
            return success_message

        return wrapper

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
        """记录 LLM 调用详情到 JSONL"""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_id": event_id,
            "session_id": session_id,
            "iteration": iteration,
            "model": getattr(self.llm_provider, "model", "unknown"),
            "duration_ms": duration_ms,
            "request": request,
            "response": response,
        }
        with open(self._llm_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def _ensure_memory_components(self, session_id: str) -> None:
        """
        确保记忆系统组件已初始化（延迟初始化）

        Args:
            session_id: 会话ID
        """
        if (
            not self._context_manager
            or not self._memory_tools
            or self._context_manager.session_id != session_id
        ):
            self._context_manager, self._memory_tools = await self._memory_initializer.initialize(
                session_id
            )

    async def _retrieve_memory_wrapper(self, args: dict, event: Event) -> str:
        """
        retrieve_memory 的包装器，确保记忆组件已初始化

        Args:
            args: 函数参数
            event: 当前事件

        Returns:
            检索结果字符串
        """
        await self._ensure_memory_components(event.session_id)
        return await self._memory_tools.retrieve_memory(args, event)

    def _count_tokens(self, text: str | Event | dict) -> int:
        """
        使用 tiktoken 计算 token 数

        Args:
            text: 文本、Event 或 dict

        Returns:
            Token 数量（近似值）
        """
        try:
            import tiktoken

            encoding = tiktoken.encoding_for_model("gpt-4")

            if isinstance(text, str):
                return len(encoding.encode(text))
            elif isinstance(text, Event):
                return len(encoding.encode(text.to_json()))
            elif isinstance(text, dict):
                return len(encoding.encode(json.dumps(text, ensure_ascii=False)))
            else:
                return 0
        except Exception:
            # Fallback: 粗略估算（2字符 ≈ 1 token）
            if isinstance(text, str):
                return len(text) // 2
            elif isinstance(text, Event):
                text_str = text.to_json()
                return len(text_str) // 2
            elif isinstance(text, dict):
                text_str = json.dumps(text, ensure_ascii=False)
                return len(text_str) // 2
            else:
                return 0

    def start(self) -> None:
        """
        启动 Agent

        订阅发往此 Agent 的事件（精确匹配）。

        注意：不订阅 '*'，因为发给特定agent的事件会通过 '*' 再次路由，导致重复处理。
        广播事件（TICK_COMPLETED）通过 EventBus 的路由规则自动处理。
        """
        logger.info(f"🚀 [Agent:{self.agent_id}] Starting agent...")

        # 只订阅精确匹配（发给自己的事件）
        # 广播事件（dst=["*"]）会通过 EventBus 的特殊逻辑处理
        self.event_bus.subscribe(f"agent:{self.agent_id}", self._on_event)
        logger.debug(f"  ✅ [Agent:{self.agent_id}] Subscribed to agent:{self.agent_id}")

        # 检查事件dst是否为["*"]（广播），如果是则处理
        # 这样避免发给特定agent的事件被 '*' 重复路由
        async def conditional_handler(event: Event) -> None:
            # 只处理真正的广播事件（dst只有"*"）
            if event.dst == ["*"]:
                await self._on_event(event)

        self.event_bus.subscribe("*", conditional_handler)
        logger.debug(f"  ✅ [Agent:{self.agent_id}] Subscribed to * (broadcast only)")

        logger.info(f"✅ Agent {self.agent_id} started")

    def stop(self) -> None:
        """停止 Agent"""
        # 取消订阅
        self.event_bus.unsubscribe(f"agent:{self.agent_id}", self._on_event)

        # 注意：conditional_handler 是局部变量，无法取消订阅
        # 实际使用中，Agent 通常是长期运行的，stop() 很少调用
        # 如果需要正确取消订阅，可以将 conditional_handler 保存为实例变量

        logger.info(f"Agent {self.agent_id} stopped")

    async def _on_event(self, event: Event) -> None:
        """
        统一的事件处理入口（Agent Loop）

        流程：
        1. 过滤事件
        2. 初始化记忆组件
        3. 构建上下文。
        4. 多轮 LLM 调用。
        5. 发送响应

        Args:
            event: 事件对象
        """
        # 1. 过滤事件（基于目标地址和 agent 状态）
        if not await self._should_process_event(event):
            return

        # 2. 记录日志和初始化记忆组件
        session_id = event.session_id
        event_id = event.id if hasattr(event, "id") else "unknown"
        self._log_event("RECV", event, f"{event.type} from {event.src}")
        logger.info(
            f"📨 [Agent:{self.agent_id}:{session_id}] Received {event.type} event (id={event_id}) from {event.src}"
        )

        await self._ensure_memory_components(event.session_id)

        # 3. 准备 Tape 写入任务
        tape_write_tasks = await self._prepare_tape_for_event(event)

        # 4. 处理事件
        try:
            await self._process_event_with_llm(event, session_id, tape_write_tasks)
        except Exception as e:
            logger.error(
                f"❌ [Agent:{self.agent_id}:{session_id}] Error processing event: {e}",
                exc_info=True,
            )
        finally:
            # 5. 确保所有 Tape 写入任务完成
            await self._complete_tape_writes(tape_write_tasks)

    def _should_handle_event(self, event: Event) -> bool:
        """检查是否应该处理此事件"""
        return f"agent:{self.agent_id}" in event.dst or "agent:*" in event.dst or "*" in event.dst

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

        # 获取当前 agent 在此 session 中的状态
        agent_state = await self.session_manager.get_agent_state(event.session_id, self.agent_id)

        # 如果状态是 WAITING_REPLY，只处理特定事件
        if agent_state == "WAITING_REPLY":
            return event.type in (
                EventType.AGENT_MESSAGE,  # 其他 agent 的回复
                EventType.TASK_FINISHED,  # 任务完成
                EventType.TASK_FAILED,  # 任务失败
            )

        return True

    async def _prepare_tape_for_event(self, event: Event) -> list:
        """
        准备 Tape 写入任务

        原则：是什么事件就记录什么事件，不做二次封装

        Args:
            event: 当前事件

        Returns:
            Tape 写入任务列表
        """
        tape_write_tasks = []

        # 记录需要处理的事件类型到 tape
        # 这些事件都是 agent 的"输入"，需要记录到当前 agent 的 tape
        # 直接记录原始事件，不做二次封装
        # agent_id 参数指定写入当前 agent 的 tape（而不是从 event.src 提取）
        tape_write_tasks.append(self._tape_writer.write_event(event, agent_id=self.agent_id))

        return tape_write_tasks

    async def _build_llm_context(self, event: Event, session_id: str) -> list[dict]:
        """
        为事件构建完整的 LLM 上下文

        整合：系统提示 + 历史消息 + 当前事件

        Args:
            event: 当前事件
            session_id: 会话 ID

        Returns:
            Messages 列表
        """
        logger.info(f"🔧 [Agent:{self.agent_id}:{session_id}] Building context...")

        # 1. 获取根事件类型（用于确定使用哪个 system prompt）
        root_event_type = await self._get_root_event_type(event, session_id)

        # 2. 获取系统提示（基于根事件类型）
        system_prompt = self._get_system_prompt_for_event(root_event_type)

        # 3. 获取历史消息（从 ContextManager）
        history_messages = []
        if self._context_manager:
            history_messages = self._context_manager.get_context_messages()
            logger.info(
                f"📚 [Agent:{self.agent_id}:{session_id}] Loaded {len(history_messages)} history messages"
            )

        # 4. 将当前事件转换为 message
        current_message = self.event_to_messages(event)

        # 5. 组装完整消息列表
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history_messages)
        messages.append(current_message)

        logger.info(
            f"📝 [Agent:{self.agent_id}:{session_id}] Context built with {len(messages)} messages"
        )
        return messages

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

        # 如果收到 AGENT_MESSAGE，说明收到了回复，减少异步回复计数
        if event.type == EventType.AGENT_MESSAGE and session.pending_async_replies > 0:
            all_received, remaining = await self.session_manager.decrement_async_replies(
                session_id, self.agent_id, count=1
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
        if session.pending_async_replies > 0:
            logger.info(
                f"⏳ [Agent:{self.agent_id}:{session_id}] Has {session.pending_async_replies} pending async replies, skipping processing"
            )
            return False

        return True

    async def _process_event_with_llm(
        self, event: Event, session_id: str, tape_write_tasks: list
    ) -> None:
        """
        使用 LLM 处理事件（多轮 function calling）

        Args:
            event: 当前事件
            session_id: 会话 ID
            tape_write_tasks: Tape 写入任务列表
        """
        # 检查是否有尚待完成的异步任务，如果有则跳过处理
        if not await self._check_and_restore_agent_state(event, session_id):
            return

        # Capture turn start time to ensure event ordering
        turn_start_time = datetime.now(timezone.utc).isoformat()

        # 构建消息
        messages = await self._build_llm_context(event, session_id)

        # 多轮 function calling 循环
        max_iterations = 10  # 防止无限循环
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            logger.info(
                f"🔄 [Agent:{self.agent_id}:{session_id}] Iteration {iteration}: Calling LLM..."
            )

            # 调用 LLM
            result = await self._call_llm(event, session_id, iteration, messages)

            # 提取结果
            tool_calls = result.get("tool_calls", [])
            response_text = result.get("response_text", "").strip()

            logger.info(
                f"🔧 [Agent:{self.agent_id}:{session_id}] Iteration {iteration}: LLM returned {len(tool_calls)} tool calls"
            )
            logger.info(
                f"💬 [Agent:{self.agent_id}:{session_id}] LLM response text: {response_text[:200] if response_text else '(empty)'}"
            )

            # TapeWriter: 构造并写入 ASSISTANT_RESPONSE Event（包含完整 tool_calls）
            assistant_response_event = TapeEvent(
                src=f"agent:{self.agent_id}",
                dst=event.dst,
                type=EventType.ASSISTANT_RESPONSE,
                payload={
                    "response": response_text,
                    "iteration": iteration,
                    "has_tool_calls": len(tool_calls) > 0,
                    "tool_calls": tool_calls if tool_calls else None,  # 完整的 tool_calls 数据
                },
                session_id=event.session_id,
                timestamp=turn_start_time,
            )
            tape_write_tasks.append(self._tape_writer.write_event(assistant_response_event))

            # 处理响应
            if not tool_calls:
                await self._handle_no_tool_calls(event, session_id, response_text, tape_write_tasks)
                break

            # 有 tool calls，添加 assistant 消息（使用已构建的 event）
            messages.append(self.event_to_messages(assistant_response_event))

            # 执行 tool calls
            should_continue = await self._process_tool_calls(
                event,
                session_id,
                iteration,
                tool_calls,
                messages,
                tape_write_tasks,
                turn_start_time,
            )

            if not should_continue:
                break

        if iteration >= max_iterations:
            logger.warning(
                f"⚠️  [Agent:{self.agent_id}:{session_id}] Reached max iterations ({max_iterations})"
            )

    async def _call_llm(
        self, event: Event, session_id: str, iteration: int, messages: list[dict]
    ) -> dict:
        """
        调用 LLM with functions

        Args:
            event: 当前事件
            session_id: 会话 ID
            iteration: 迭代次数
            messages: 消息历史

        Returns:
            LLM 响应结果
        """
        start_time = datetime.now(timezone.utc)

        # Debug: 打印 messages 结构
        logger.debug(f"🔍 [Agent:{self.agent_id}:{session_id}] Messages being sent to LLM:")
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content_preview = str(msg.get("content", ""))[:100]
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                logger.debug(f"  [{i}] role={role}, tool_calls={tool_calls}")
            else:
                logger.debug(f"  [{i}] role={role}, content={content_preview}")

        # 调用 LLM（传递完整的messages历史）
        result = await self.llm_provider.call_with_functions(
            functions=AVAILABLE_FUNCTIONS,
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
        )

        # 记录 LLM 调用详情
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        self._log_llm_call(
            event_id=event.event_id,
            session_id=event.session_id,
            iteration=iteration,
            request={"messages": messages, "functions": AVAILABLE_FUNCTIONS},
            response=result,
            duration_ms=duration_ms,
        )

        return result

    async def _process_tool_calls(
        self,
        event: Event,
        session_id: str,
        iteration: int,
        tool_calls: list,
        messages: list[dict],
        tape_write_tasks: list,
        turn_start_time: str,
    ) -> bool:
        """
        处理 tool calls

        Args:
            event: 当前事件
            session_id: 会话 ID
            iteration: 迭代次数
            tool_calls: 工具调用列表
            messages: 消息历史（会被修改）
            tape_write_tasks: Tape 写入任务列表
            turn_start_time: Turn开始时间戳（用于确保事件顺序）

        Returns:
            是否应该继续循环
        """
        has_finish_loop = False
        has_respond_to_player = False

        for idx, tool_call in enumerate(tool_calls, 1):
            function_name = tool_call["function"]["name"]
            function_args = json.loads(tool_call["function"]["arguments"])

            logger.info(
                f"⚙️  [Agent:{self.agent_id}:{session_id}] [Iter {iteration}, {idx}/{len(tool_calls)}] Calling: {function_name}"
            )

            if function_name == "finish_loop":
                has_finish_loop = True

            if function_name == "respond_to_player":
                has_respond_to_player = True

            result_str = await self._call_function_with_result(function_name, function_args, event)

            # Fix: Ensure tool_result timestamps come AFTER assistant_response
            # Parse base timestamp and increment microseconds to maintain ordering
            base_dt = datetime.fromisoformat(turn_start_time.replace("Z", "+00:00"))
            tool_result_dt = base_dt + timedelta(microseconds=idx)
            tool_result_timestamp = tool_result_dt.isoformat()

            tool_result_event = TapeEvent(
                src=f"agent:{self.agent_id}",
                dst=event.dst,
                type=EventType.TOOL_RESULT,
                payload={
                    "tool_call_id": tool_call["id"],
                    "tool": function_name,
                    "result": result_str,
                },
                session_id=event.session_id,
                timestamp=tool_result_timestamp,
            )

            tape_write_tasks.append(self._tape_writer.write_event(tool_result_event))

            # 记录 tool call 结果（使用已构建的 event）
            messages.append(self.event_to_messages(tool_result_event))
            logger.debug(
                f"📤 [Agent:{self.agent_id}:{session_id}] Tool result: {result_str[:100]}..."
            )

        # 检查退出条件（finish_loop 优先）
        if has_finish_loop:
            logger.info(
                f"🔄 [Agent:{self.agent_id}:{session_id}] finish_loop called (priority check), ending loop"
            )
            return False

        # 如果已经有respond_to_player，说明第一轮LLM已经生成了最终响应，可以结束
        if has_respond_to_player:
            logger.info(
                f"✅ [Agent:{self.agent_id}:{session_id}] respond_to_player called, ending loop"
            )
            return False

        # 否则继续循环，让 LLM 基于工具调用结果生成最终响应
        logger.info(
            f"✅ [Agent:{self.agent_id}:{session_id}] Tool calls executed, requesting final response from LLM..."
        )
        return True

    async def _complete_tape_writes(self, tape_write_tasks: list) -> None:
        """
        完成 Tape 写入任务

        Args:
            tape_write_tasks: Tape 写入任务列表
        """
        if tape_write_tasks:
            try:
                results = await asyncio.gather(*tape_write_tasks, return_exceptions=True)

                # 检查是否有任务失败
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.warning(
                            f"[Agent:{self.agent_id}] Tape write task {i} failed: {result}"
                        )

                if results:
                    logger.debug(
                        f"[Agent:{self.agent_id}] {len(results)} tape write tasks completed"
                    )
            except Exception as tape_error:
                logger.warning(f"Failed to complete tape write tasks: {tape_error}")

    async def _handle_no_tool_calls(
        self, event: Event, session_id: str, response_text: str, tape_write_tasks: list
    ) -> None:
        """
        处理无 tool calls 的情况

        Args:
            event: 当前事件
            session_id: 会话 ID
            response_text: LLM 响应文本
            tape_write_tasks: Tape 写入任务列表
        """
        logger.info(f"✅ [Agent:{self.agent_id}:{session_id}] No more tool calls, ending loop")

        # 发送最终响应（即使为空也要响应）
        final_response = response_text if response_text else "抱歉，我暂时无法理解您的请求。"

        # TapeWriter: 构造并写入 RESPONSE Event (统一使用 RESPONSE 类型)
        response_event = TapeEvent(
            src=f"agent:{self.agent_id}",
            dst=event.dst,
            type=EventType.RESPONSE,
            payload={"narrative": final_response},
            session_id=event.session_id,
        )
        tape_write_tasks.append(self._tape_writer.write_event(response_event))

        logger.info(
            f"💬 [Agent:{self.agent_id}:{session_id}] Sending final response: {final_response[:50]}..."
        )
        self._log_event("SEND", event, f"RESPONSE to {event.src}: {final_response[:50]}...")
        await self._send_response(final_response, event)

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
        """
        根据事件类型获取 system prompt（支持动态 Skill 加载）

        Args:
            event_type: 事件类型

        Returns:
            System prompt
        """
        # 1. Soul（不变）
        soul_part = f"# 你的角色\n{self._soul}\n" if self._soul else ""

        # 2. Data Scope（不变）
        scope_part = ""
        if self._data_scope:
            import yaml

            scope_yaml = yaml.dump(self._data_scope, allow_unicode=True)
            scope_part = f"# 数据权限\n```yaml\n{scope_yaml}```\n"

        # 3. Skill Content（动态加载）
        task_part = ""
        if self._skill_loader:
            skill_name = self._skill_loader.registry.get_skill_for_event(event_type)
            if skill_name:
                skill = self._skill_loader.load(skill_name)
                if skill:
                    task_part = self._inject_skill_variables(skill.content)
                else:
                    task_part = self._get_hardcoded_instruction(event_type)
            else:
                task_part = self._get_hardcoded_instruction(event_type)
        else:
            task_part = self._get_hardcoded_instruction(event_type)

        return "\n".join(filter(None, [soul_part, scope_part, task_part])).strip()

    def event_to_messages(self, event: Event) -> dict:
        """
        将单个事件转换为一条 message（不组装上下文）

        Args:
            event: 事件对象

        Returns:
            单条 message，格式：{"role": "user" | "assistant" | "tool", "content": "..."}
        """
        # 1. Agent 响应类 → assistant (RESPONSE 统一处理，不再区分 AGENT_RESPONSE)
        if event.type == EventType.RESPONSE:
            return {"role": "assistant", "content": event.payload.get("narrative", "")}

        # 2. ASSISTANT_RESPONSE → assistant (带 tool_calls)
        if event.type == EventType.ASSISTANT_RESPONSE:
            msg = {"role": "assistant", "content": event.payload.get("response", "")}
            tool_calls = event.payload.get("tool_calls")
            if tool_calls:
                msg["tool_calls"] = tool_calls
            return msg

        # 3. TOOL_RESULT → tool
        if event.type == EventType.TOOL_RESULT:
            return {
                "role": "tool",
                "tool_call_id": event.payload.get("tool_call_id"),
                "content": event.payload.get("result", ""),
            }

        # 4. 其他事件 → user (内联构建内容)
        parts = [
            "# 收到的事件",
            f"- 来源: {event.src}",
            f"- 类型: {event.type}",
            f"- 时间: {event.timestamp}",
        ]

        # COMMAND
        if event.type == EventType.COMMAND and event.payload:
            command = event.payload.get("command", "")
            if command:
                parts.extend(
                    [
                        "\n# 皇帝的命令：",
                        f"```\n{command}\n```",
                        "\n**重要**：你需要**执行**这个命令！",
                    ]
                )

        # CHAT
        elif event.type == EventType.CHAT and event.payload:
            message = event.payload.get("message", "")
            if message:
                parts.extend(["\n# 皇帝的消息：", f"```\n{message}\n```"])

        # AGENT_MESSAGE
        elif event.type == EventType.AGENT_MESSAGE and event.payload:
            message = event.payload.get("message", "")
            source = event.src.replace("agent:", "")
            if message:
                parts.extend([f"\n# 来自 {source} 的消息：", f"```\n{message}\n```"])

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

        # 其他 payload
        if event.payload and event.type not in (EventType.COMMAND, EventType.CHAT):
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
        """
        调用 function handler 并返回结果（多轮模式）

        使用函数映射表来避免大量的 if-elif 语句，提高代码可维护性。

        Args:
            function_name: 函数名称
            arguments: 函数参数
            original_event: 原始事件

        Returns:
            函数执行结果（返回给LLM）
        """
        session_id = original_event.session_id

        logger.info(f"🎯 [Agent:{self.agent_id}:{session_id}] Executing function: {function_name}")
        logger.debug(f"📋 [Agent:{self.agent_id}:{session_id}] Function arguments: {arguments}")

        try:
            # 从映射表中获取处理函数
            handler = self._function_handlers.get(function_name)
            if handler is None:
                return f"❌ 未知函数: {function_name}"

            # 执行处理函数
            result = await handler(arguments, original_event)
            return result

        except Exception as e:
            error_msg = f"❌ 函数执行失败: {e}"
            logger.error(f"❌ [Agent:{self.agent_id}:{session_id}] {error_msg}", exc_info=True)
            return error_msg

    async def _send_response(self, content: str, event: Event) -> None:
        """发送响应"""
        new_event = Event(
            src=f"agent:{self.agent_id}",
            dst=[event.src],
            type=EventType.RESPONSE,
            payload={"narrative": content},
            session_id=event.session_id,
            parent_event_id=event.event_id,
            root_event_id=event.root_event_id,
        )
        await self.event_bus.send_event(new_event)
        logger.info(f"✅ Agent {self.agent_id} sent RESPONSE to {event.src}")

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
