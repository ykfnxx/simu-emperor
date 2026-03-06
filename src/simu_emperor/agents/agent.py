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
        """
        self.agent_id = agent_id
        self.event_bus = event_bus
        self.llm_provider = llm_provider
        self.data_dir = Path(data_dir)
        self.repository = repository
        self.session_id = session_id
        self._skill_loader = skill_loader

        # 加载 soul 和 data_scope
        self._soul: str | None = None
        self._data_scope: dict[str, Any] | None = None
        self._load_soul()
        self._load_data_scope()

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
        )

        # 初始化记忆系统组件（V3）
        from simu_emperor.memory.tape_writer import TapeWriter
        from simu_emperor.memory.manifest_index import ManifestIndex

        # Use configured memory_dir
        # Resolve to absolute path (relative to cwd when not absolute)
        # This ensures all agents use the same centralized memory directory
        self._memory_dir = Path(settings.memory.memory_dir).resolve()

        self._tape_writer = TapeWriter(memory_dir=self._memory_dir)
        self._manifest_index = ManifestIndex(memory_dir=self._memory_dir)

        # ContextManager - 用于当前session的上下文管理
        self._context_manager = None  # 延迟初始化，需要session_id
        self._memory_tools = None  # 延迟初始化，需要session_id

        # 初始化独立日志
        self._init_agent_logger()

        # 初始化函数处理器映射
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
            "send_game_event": (
                self._action_tools.send_game_event,
                "✅ 游戏事件已发送到 Calculator",
            ),
            "send_message_to_agent": (
                self._action_tools.send_message_to_agent,
                "✅ 消息已发送给其他官员",
            ),
            "respond_to_player": (self._action_tools.respond_to_player, "✅ 响应已发送给玩家"),
            "send_ready": (self._action_tools.send_ready, "✅ Ready 信号已发送"),
            "write_memory": (self._action_tools.write_memory, "✅ 记忆已写入"),
        }

        for func_name, (handler, success_msg) in action_handlers.items():
            self._function_handlers[func_name] = self._create_action_wrapper(handler, success_msg)

    @staticmethod
    def _create_action_wrapper(handler_func: callable, success_message: str) -> callable:
        """
        为动作处理函数创建包装器，使其返回标准化的成功消息

        Args:
            handler_func: 原始动作处理函数（无返回值）
            success_message: 执行成功后返回的消息

        Returns:
            包装后的异步函数（返回成功消息）
        """

        async def wrapper(args: dict, event: Event) -> str:
            await handler_func(args, event)
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
        if not self._context_manager or not self._memory_tools:
            logger.info(f"🧠 [Agent:{self.agent_id}] Initializing memory components...")

            from simu_emperor.memory.context_manager import ContextManager, ContextConfig
            from simu_emperor.agents.tools.memory_tools import MemoryTools

            # 初始化 ContextManager
            tape_path = self._tape_writer._get_tape_path(session_id, self.agent_id)
            self._context_manager = ContextManager(
                session_id=session_id,
                agent_id=self.agent_id,
                tape_path=tape_path,
                config=ContextConfig(),
                llm_provider=self.llm_provider,
                manifest_index=self._manifest_index,
            )

            # 初始化 MemoryTools
            self._memory_tools = MemoryTools(
                agent_id=self.agent_id,
                memory_dir=self._memory_dir,
                llm_provider=self.llm_provider,
                context_manager=self._context_manager,
            )

            # 注册 session（同步执行，确保完成）
            await self._manifest_index.register_session(
                session_id=session_id,
                agent_id=self.agent_id,
                turn=1,  # TODO: 从event payload获取实际回合数
            )

            # 从 tape 加载历史事件到 ContextManager
            await self._context_manager.load_from_tape()

            logger.info(f"✅ [Agent:{self.agent_id}] Memory components initialized")

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
        广播事件（END_TURN, TURN_RESOLVED）通过 EventBus 的路由规则自动处理。
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
        3. 构建上下文
        4. 多轮 LLM 调用
        5. 发送响应

        Args:
            event: 事件对象
        """
        # 1. 过滤事件
        if not self._should_handle_event(event):
            return

        # 2. 记录日志和初始化记忆组件
        session_id = event.session_id
        event_id = event.id if hasattr(event, "id") else "unknown"
        self._log_event("RECV", event, f"{event.type} from {event.src}")
        logger.info(
            f"📨 [Agent:{self.agent_id}:{session_id}] Received {event.type} event (id={event_id}) from {event.src}"
        )

        if event.type in (EventType.COMMAND, EventType.CHAT):
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
        if event.type in (
            EventType.COMMAND,
            EventType.CHAT,
            EventType.AGENT_MESSAGE,
        ):
            # 直接记录原始事件，不做二次封装
            # agent_id 参数指定写入当前 agent 的 tape（而不是从 event.src 提取）
            tape_write_tasks.append(
                self._tape_writer.write_event(event, agent_id=self.agent_id)
            )

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
        logger.info(f"🔧 [Agent:{self.agent_id}:{session_id}] Starting context build...")

        # 使用 ContextManager 从 tape 构建完整 Context
        system_prompt = self._get_system_prompt_for_event(event.type)

        # 从 ContextManager 获取历史消息
        if self._context_manager:
            context_messages = self._context_manager.get_context_messages()

            # 构建完整消息列表
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(context_messages)

            # 添加当前事件
            user_prompt = self._build_user_prompt(event)
            messages.append({"role": "user", "content": user_prompt})

            logger.info(
                f"🔧 [Agent:{self.agent_id}:{session_id}] Using ContextManager (loaded from tape)"
            )
        else:
            # 回退到单事件模式
            logger.warning(
                f"⚠️  [Agent:{self.agent_id}:{session_id}] No ContextManager, using single event mode"
            )
            user_prompt = self._build_user_prompt(event)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

        logger.info(
            f"📝 [Agent:{self.agent_id}:{session_id}] Context built with {len(messages)} messages"
        )
        return messages

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
            )
            tape_write_tasks.append(self._tape_writer.write_event(assistant_response_event))

            # 处理响应
            if not tool_calls:
                await self._handle_no_tool_calls(event, session_id, response_text, tape_write_tasks)
                break

            # 有 tool calls，添加 assistant 消息
            messages.append(self._build_assistant_message(response_text, tool_calls))

            # 执行 tool calls
            should_continue = await self._process_tool_calls(
                event, session_id, iteration, tool_calls, messages, tape_write_tasks
            )

            # 检查是否应该继续循环
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

        Returns:
            是否应该继续循环
        """
        has_respond_to_player = False  # 是否有respond_to_player

        for idx, tool_call in enumerate(tool_calls, 1):
            function_name = tool_call["function"]["name"]
            function_args = json.loads(tool_call["function"]["arguments"])

            logger.info(
                f"⚙️ [Agent:{self.agent_id}:{session_id}] [Iter {iteration}, {idx}/{len(tool_calls)}] Calling: {function_name}"
            )

            # 检查是否已经调用了respond_to_player
            if function_name == "respond_to_player":
                has_respond_to_player = True

            # 调用 function handler 并获取结果
            result_str = await self._call_function_with_result(function_name, function_args, event)

            # 构建 TOOL_RESULT Event
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
            )

            # TapeWriter: 写入 TOOL_RESULT Event
            tape_write_tasks.append(self._tape_writer.write_event(tool_result_event))

            # 记录 tool call 结果（使用OpenAI格式，与 tape 中存储的格式一致）
            tool_result_message = {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": result_str,
            }
            messages.append(tool_result_message)
            logger.debug(
                f"📤 [Agent:{self.agent_id}:{session_id}] Tool result: {result_str[:100]}..."
            )

        # 如果已经有respond_to_player，说明第一轮LLM已经生成了最终响应，可以结束
        if has_respond_to_player:
            logger.info(
                f"✅ [Agent:{self.agent_id}:{session_id}] Already responded to player, ending loop"
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

    def _build_assistant_message(self, response_text: str, tool_calls: list) -> dict:
        """
        构建 assistant 消息（包含 tool_calls）

        Args:
            response_text: LLM 响应文本
            tool_calls: 工具调用列表

        Returns:
            Assistant 消息
        """
        return {
            "role": "assistant",
            "content": response_text or None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                }
                for tc in tool_calls
            ],
        }

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

        # TapeWriter: 构造并写入 AGENT_RESPONSE Event
        agent_response_event = TapeEvent(
            src=f"agent:{self.agent_id}",
            dst=event.dst,
            type=EventType.AGENT_RESPONSE,
            payload={"response": final_response},
            session_id=event.session_id,
        )
        tape_write_tasks.append(self._tape_writer.write_event(agent_response_event))

        logger.info(
            f"💬 [Agent:{self.agent_id}:{session_id}] Sending final response: {final_response[:50]}..."
        )
        self._log_event("SEND", event, f"RESPONSE to {event.src}: {final_response[:50]}...")
        await self._send_response(final_response, event)

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

    def _build_user_prompt(self, event: Event) -> str:
        """
        构建 user prompt

        Args:
            event: 事件对象

        Returns:
            User prompt
        """
        parts = [
            "# 收到的事件",
            f"- 来源: {event.src}",
            f"- 类型: {event.type}",
            f"- 时间: {event.timestamp}",
        ]

        # 对于 COMMAND 事件，明确显示命令内容
        command = None
        if event.type == EventType.COMMAND and event.payload:
            command = event.payload.get("command", "")
            if command:
                parts.append("\n# 皇帝的命令：")
                parts.append("``")
                parts.append(command)
                parts.append("```")
                parts.append("\n**重要**：你需要**执行**这个命令，不仅仅是查询数据！")

        # 对于 CHAT 事件，显示消息内容
        if event.type == EventType.CHAT and event.payload:
            message = event.payload.get("message", "")
            if message:
                parts.append("\n# 皇帝的消息：")
                parts.append("``")
                parts.append(message)
                parts.append("```")

        # Handle AGENT_MESSAGE events
        elif event.type == EventType.AGENT_MESSAGE and event.payload:
            message = event.payload.get("message", "")
            source_agent = event.src.replace("agent:", "")
            if message:
                parts.append(f"\n# 来自 {source_agent} 的消息：")
                parts.append("```")
                parts.append(message)
                parts.append("```")

        if event.payload:
            # 显示其他 payload 信息（但隐藏内部字段）
            display_payload = {k: v for k, v in event.payload.items() if not k.startswith("_")}
            if display_payload and command:  # 只在有命令时显示其他信息
                parts.append("\n# 其他信息：")
                payload_json = json.dumps(display_payload, ensure_ascii=False, indent=2)
                parts.append(f"```json\n{payload_json}\n```")

        return "\n".join(parts)

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
