"""
Agent 基类 - 文件驱动的 AI 官员

基于 Function Calling 的架构：
- 只响应事件，不主动发起
- 根据事件类型选择不同的 system prompt
- Skills 注册为 function calls
- LLM 自主决定调用哪些 functions
"""

import json
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from simu_emperor.agents.system_prompts import get_system_prompt
from simu_emperor.agents.tool_definitions import AVAILABLE_FUNCTIONS
from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
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
        db_logger=None,
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
            db_logger: 数据库日志记录器（用于查询历史事件）
            skill_loader: SkillLoader 实例（用于动态加载 Skill 内容）
        """
        self.agent_id = agent_id
        self.event_bus = event_bus
        self.llm_provider = llm_provider
        self.data_dir = Path(data_dir)
        self.repository = repository
        self.session_id = session_id
        self._db_logger = db_logger
        self._skill_loader = skill_loader

        # 加载 soul 和 data_scope
        self._soul: str | None = None
        self._data_scope: dict[str, Any] | None = None
        self._load_soul()
        self._load_data_scope()

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
                "query_province_data": self._handle_query_province_data_with_result,
                "query_national_data": self._handle_query_national_data_with_result,
                "list_provinces": self._handle_list_provinces_with_result,
                "list_agents": self._handle_list_agents_with_result,
                "get_agent_info": self._handle_get_agent_info_with_result,
            }
        )

        # Action 类函数 - 执行后返回成功消息
        # 使用包装器将无返回值的函数转换为返回成功消息
        action_handlers = {
            "send_game_event": (self._handle_send_game_event, "✅ 游戏事件已发送到 Calculator"),
            "send_message_to_agent": (
                self._handle_send_message_to_agent,
                "✅ 消息已发送给其他官员",
            ),
            "respond_to_player": (self._handle_respond_to_player, "✅ 响应已发送给玩家"),
            "send_ready": (self._handle_send_ready, "✅ Ready 信号已发送"),
            "write_memory": (self._handle_write_memory, "✅ 记忆已写入"),
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
        1. 根据 event type 选择 system prompt
        2. 构建 user prompt（包含事件信息）
        3. 调用 LLM with functions
        4. 循环执行 tool calls，把结果返回给LLM，直到LLM不再请求tool calls
        5. 发送最终响应

        Args:
            event: 事件对象
        """
        # 获取请求ID用于追踪
        request_id = event.payload.get("_request_id", "unknown")
        event_id = event.id if hasattr(event, "id") else "unknown"

        # 过滤不是发往此 Agent 的事件
        if (
            f"agent:{self.agent_id}" not in event.dst
            and "agent:*" not in event.dst
            and "*" not in event.dst
        ):
            return

        # 记录事件日志
        self._log_event("RECV", event, f"{event.type} from {event.src}")

        logger.info(
            f"📨 [Agent:{self.agent_id}:{request_id}] Received {event.type} event (id={event_id}) from {event.src}"
        )

        try:
            # 1-2. 构建 Context（包含历史事件）
            logger.info(f"🔧 [Agent:{self.agent_id}:{request_id}] Starting context build...")

            if self._db_logger:
                logger.info(
                    f"🔧 [Agent:{self.agent_id}:{request_id}] Using db_logger to build context"
                )
                # 使用数据库查询构建完整 Context
                messages = await self._build_context(event, history_limit=20)
            else:
                logger.info(
                    f"⚠️  [Agent:{self.agent_id}:{request_id}] No db_logger, using single event mode"
                )
                # 回退到单事件模式
                system_prompt = self._get_system_prompt_for_event(event.type)
                user_prompt = self._build_user_prompt(event)
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]

            logger.info(
                f"📝 [Agent:{self.agent_id}:{request_id}] Context built with {len(messages)} messages"
            )

            # 3-4. 多轮 function calling 循环
            max_iterations = 10  # 防止无限循环
            iteration = 0

            while iteration < max_iterations:
                iteration += 1
                logger.info(
                    f"🔄 [Agent:{self.agent_id}:{request_id}] Iteration {iteration}: Calling LLM..."
                )

                # 记录 LLM 调用开始时间
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

                tool_calls = result.get("tool_calls", [])
                response_text = result.get("response_text", "").strip()

                logger.info(
                    f"🔧 [Agent:{self.agent_id}:{request_id}] Iteration {iteration}: LLM returned {len(tool_calls)} tool calls"
                )
                logger.info(
                    f"💬 [Agent:{self.agent_id}:{request_id}] LLM response text: {response_text[:200] if response_text else '(empty)'}"
                )

                # 如果没有 tool calls，循环结束
                if not tool_calls:
                    logger.info(
                        f"✅ [Agent:{self.agent_id}:{request_id}] No more tool calls, ending loop"
                    )

                    # 发送最终响应
                    if response_text:
                        logger.info(
                            f"💬 [Agent:{self.agent_id}:{request_id}] Sending final response: {response_text[:50]}..."
                        )
                        self._log_event(
                            "SEND", event, f"RESPONSE to {event.src}: {response_text[:50]}..."
                        )
                        await self._send_response(response_text, event)
                    break

                # 添加assistant消息（包含tool_calls）
                assistant_message = {
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
                messages.append(assistant_message)

                # 执行 tool calls 并收集结果
                has_query_functions = False  # 是否有查询函数
                has_respond_to_player = False  # 是否有respond_to_player

                for idx, tool_call in enumerate(tool_calls, 1):
                    function_name = tool_call["function"]["name"]
                    function_args = json.loads(tool_call["function"]["arguments"])

                    logger.info(
                        f"⚙️ [Agent:{self.agent_id}:{request_id}] [Iter {iteration}, {idx}/{len(tool_calls)}] Calling: {function_name}"
                    )

                    # 检查是否是查询函数
                    if function_name in [
                        "query_province_data",
                        "query_national_data",
                        "list_provinces",
                    ]:
                        has_query_functions = True

                    # 检查是否已经调用了respond_to_player
                    if function_name == "respond_to_player":
                        has_respond_to_player = True

                    # 调用 function handler 并获取结果
                    result_str = await self._call_function_with_result(
                        function_name, function_args, event
                    )

                    # 记录 tool call 结果（使用OpenAI格式）
                    tool_result_message = {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result_str,
                    }
                    messages.append(tool_result_message)
                    logger.debug(
                        f"📤 [Agent:{self.agent_id}:{request_id}] Tool result: {result_str[:100]}..."
                    )

                # 如果已经有respond_to_player，说明第一轮LLM已经生成了最终响应，可以结束
                if has_respond_to_player:
                    logger.info(
                        f"✅ [Agent:{self.agent_id}:{request_id}] Already responded to player, ending loop"
                    )
                    break

                # 如果没有查询函数，说明所有tool calls都是执行类动作
                # 需要再给LLM一次机会生成最终响应（因为第一轮的response_text可能为空）
                if not has_query_functions:
                    logger.info(
                        f"✅ [Agent:{self.agent_id}:{request_id}] All actions executed, requesting final response from LLM..."
                    )
                    # 继续循环，让LLM生成最终响应
                    continue

            if iteration >= max_iterations:
                logger.warning(
                    f"⚠️  [Agent:{self.agent_id}:{request_id}] Reached max iterations ({max_iterations})"
                )

        except Exception as e:
            logger.error(
                f"❌ [Agent:{self.agent_id}:{request_id}] Error processing event: {e}",
                exc_info=True,
            )

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

        if event.payload:
            # 显示其他 payload 信息（但隐藏内部字段）
            display_payload = {k: v for k, v in event.payload.items() if not k.startswith("_")}
            if display_payload and command:  # 只在有命令时显示其他信息
                parts.append("\n# 其他信息：")
                payload_json = json.dumps(display_payload, ensure_ascii=False, indent=2)
                parts.append(f"```json\n{payload_json}\n```")

        return "\n".join(parts)

    def _format_event_as_message(self, event: Event, is_current: bool = False) -> str:
        """
        将事件格式化为 LLM 可读文本

        Args:
            event: 事件对象
            is_current: 是否为当前事件

        Returns:
            格式化的文本
        """
        prefix = "[当前事件]\n" if is_current else ""
        return f"""{prefix}事件ID: {event.event_id}
来源: {event.src}
目标: {", ".join(event.dst)}
类型: {event.type}
时间: {event.timestamp}
负载: {json.dumps(event.payload, ensure_ascii=False, indent=2)}
---"""

    async def _build_context(self, current_event: Event, history_limit: int = 20) -> list[dict]:
        """
        基于 Session 内可见事件组装 LLM Context

        Args:
            current_event: 当前事件
            history_limit: 历史事件数量限制

        Returns:
            OpenAI 格式的 messages 列表
        """
        messages = []

        # 1. System prompt
        logger.info(
            f"🔧 [Agent:{self.agent_id}] Building system prompt for event type: {current_event.type}"
        )
        system_content = self._get_system_prompt_for_event(current_event.type)
        messages.append({"role": "system", "content": system_content})

        # 2. 如果有 db_logger，查询可见历史事件
        if self._db_logger:
            try:
                logger.info(
                    f"🔧 [Agent:{self.agent_id}] Querying db_logger for history (session={current_event.session_id[:8]}...)"
                )
                history = await self._db_logger.get_agent_visible_events(
                    session_id=current_event.session_id, agent_id=self.agent_id, limit=history_limit
                )
                logger.info(f"🔧 [Agent:{self.agent_id}] Found {len(history)} historical events")

                # 3. 将历史事件转为 messages（从旧到新）
                for event in reversed(history):
                    if event.event_id == current_event.event_id:
                        continue
                    messages.append(
                        {"role": "user", "content": self._format_event_as_message(event)}
                    )

            except Exception as e:
                logger.error(
                    f"❌ [Agent:{self.agent_id}] Failed to build context from database: {e}",
                    exc_info=True,
                )
                # 如果数据库查询失败，回退到单事件模式
                logger.warning(f"⚠️  [Agent:{self.agent_id}] Falling back to single event mode")
                pass

        # 4. 当前事件
        messages.append(
            {
                "role": "user",
                "content": self._format_event_as_message(current_event, is_current=True),
            }
        )

        logger.info(f"✅ [Agent:{self.agent_id}] Context build complete: {len(messages)} messages")
        return messages

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
        request_id = original_event.payload.get("_request_id", "unknown")

        logger.info(f"🎯 [Agent:{self.agent_id}:{request_id}] Executing function: {function_name}")
        logger.debug(f"📋 [Agent:{self.agent_id}:{request_id}] Function arguments: {arguments}")

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
            logger.error(f"❌ [Agent:{self.agent_id}:{request_id}] {error_msg}", exc_info=True)
            return error_msg

    async def _handle_send_game_event(self, args: dict, event: Event) -> None:
        """发送游戏事件到 Calculator"""
        event_type_str = args.get("event_type")
        payload = args.get("payload", {})

        logger.info(
            f"🎮 [Agent:{self.agent_id}] Sending game event: {event_type_str} with payload: {payload}"
        )

        # 映射到 EventType
        event_type = self._str_to_event_type(event_type_str)
        if not event_type:
            logger.warning(f"⚠️  [Agent:{self.agent_id}] Unknown event type: {event_type_str}")
            return

        new_event = Event(
            src=f"agent:{self.agent_id}",
            dst=["system:calculator"],
            type=event_type,
            payload=payload,
            session_id=event.session_id,
            parent_event_id=event.event_id,
            root_event_id=event.root_event_id,
        )
        await self.event_bus.send_event(new_event)
        logger.info(f"✅ [Agent:{self.agent_id}] Sent {event_type_str} event to system:calculator")

    async def _handle_send_message_to_agent(self, args: dict, event: Event) -> None:
        """发送消息给其他 Agent"""
        target_agent = args.get("target_agent")
        message = args.get("message")

        logger.info(
            f"📨 [Agent:{self.agent_id}] Sending message to {target_agent}: {message[:50]}..."
        )

        if not target_agent.startswith("agent:"):
            target_agent = f"agent:{target_agent}"

        new_event = Event(
            src=f"agent:{self.agent_id}",
            dst=[target_agent],
            type=EventType.AGENT_MESSAGE,
            payload={"message": message},
            session_id=event.session_id,
            parent_event_id=event.event_id,
            root_event_id=event.root_event_id,
        )
        await self.event_bus.send_event(new_event)
        logger.info(f"✅ Agent {self.agent_id} sent AGENT_MESSAGE to {target_agent}")

    async def _handle_respond_to_player(self, args: dict, event: Event) -> None:
        """响应玩家"""
        content = args.get("content", "")

        logger.info(f"💬 [Agent:{self.agent_id}] Responding to {event.src}: {content[:50]}...")

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
        logger.info(f"✅ [Agent:{self.agent_id}] Sent RESPONSE event to {event.src}")

    async def _handle_send_ready(self, args: dict, event: Event) -> None:
        """发送 ready 信号"""
        new_event = Event(
            src=f"agent:{self.agent_id}",
            dst=["system:calculator"],
            type=EventType.READY,
            payload={},
            session_id=event.session_id,
            parent_event_id=event.event_id,
            root_event_id=event.root_event_id,
        )
        await self.event_bus.send_event(new_event)
        logger.info(f"✅ Agent {self.agent_id} sent READY to system:calculator")

    async def _handle_write_memory(self, args: dict, event: Event) -> None:
        """写入记忆"""
        content = args.get("content", "")
        turn = event.payload.get("turn", 0)

        # 创建 memory 目录
        memory_dir = self.data_dir / "memory"
        recent_dir = memory_dir / "recent"
        recent_dir.mkdir(parents=True, exist_ok=True)

        # 写入文件
        turn_file = recent_dir / f"turn_{turn:03d}.md"
        with open(turn_file, "w", encoding="utf-8") as f:
            f.write(f"# Turn {turn} Summary\n\n")
            f.write(f"Agent: {self.agent_id}\n")
            f.write(f"Date: {event.timestamp}\n\n")
            f.write(f"## Summary\n\n{content}\n")

        # 清理旧记忆
        self._cleanup_old_memories(recent_dir, turn)

        logger.info(f"✅ Agent {self.agent_id} wrote memory for turn {turn}")

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

    def _str_to_event_type(self, event_type_str: str) -> str | None:
        """将字符串映射到 EventType"""
        event_map = {
            "allocate_funds": EventType.ALLOCATE_FUNDS,
            "adjust_tax": EventType.ADJUST_TAX,
            "build_irrigation": EventType.BUILD_IRRIGATION,
            "recruit_troops": EventType.RECRUIT_TROOPS,
        }
        return event_map.get(event_type_str)

    def _cleanup_old_memories(self, recent_dir: Path, current_turn: int) -> None:
        """清理旧记忆（只保留最近3回合）"""
        import os

        if not recent_dir.exists():
            return

        for filename in os.listdir(recent_dir):
            if filename.startswith("turn_") and filename.endswith(".md"):
                try:
                    turn_str = filename[5:8]
                    file_turn = int(turn_str)

                    if file_turn <= current_turn - 3:
                        file_path = recent_dir / filename
                        file_path.unlink()
                        logger.debug(f"Cleaned up old memory: {filename}")
                except (ValueError, IndexError):
                    continue

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

    async def _handle_query_province_data_with_result(self, args: dict, event: Event) -> str:
        """查询省份数据并返回结果（用于多轮function calling）"""
        if not self.repository:
            return "❌ Repository not available"

        province_id = args.get("province_id")
        field_path = args.get("field_path")

        try:
            # 加载状态
            state = await self.repository.load_state()

            # 解析 field_path（如 "population.total"）
            parts = field_path.split(".")

            # 获取省份数据
            provinces_dict = {p["province_id"]: p for p in state.get("provinces", [])}
            if province_id not in provinces_dict:
                return f"❌ 未找到省份 {province_id}"

            province_data = provinces_dict[province_id]

            # 导航到目标字段
            value = province_data
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                elif isinstance(value, list) and part.isdigit():
                    value = value[int(part)]
                else:
                    return f"❌ 无法访问字段 {field_path}"

            logger.info(f"Agent {self.agent_id} queried {province_id}.{field_path} = {value}")

            # 返回查询结果（给LLM）
            return f"查询结果：{province_id} 的 {field_path} = {value}"

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error querying province data: {e}")
            return f"❌ 查询失败：{str(e)}"

    async def _handle_query_national_data_with_result(self, args: dict, event: Event) -> str:
        """查询国家级数据并返回结果（用于多轮function calling）"""
        if not self.repository:
            return "❌ Repository not available"

        field_name = args.get("field_name")

        try:
            # 加载状态
            state = await self.repository.load_state()

            # 获取字段值
            value = state.get(field_name)

            logger.info(f"Agent {self.agent_id} queried national.{field_name} = {value}")

            # 返回查询结果（给LLM）
            return f"查询结果：国家级 {field_name} = {value}"

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error querying national data: {e}")
            return f"❌ 查询失败：{str(e)}"

    async def _handle_list_provinces_with_result(self, args: dict, event: Event) -> str:
        """列出所有省份并返回结果（用于多轮function calling）"""
        if not self.repository:
            return "❌ Repository not available"

        try:
            # 加载状态
            state = await self.repository.load_state()

            # 获取省份列表
            provinces = state.get("provinces", [])
            province_ids = [p.get("province_id") for p in provinces]

            logger.info(f"Agent {self.agent_id} listed provinces: {province_ids}")

            # 返回结果（给LLM）
            return f"可用省份：{', '.join(province_ids)}"

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error listing provinces: {e}")
            return f"❌ 查询失败：{str(e)}"

    async def _handle_list_agents_with_result(self, args: dict, event: Event) -> str:
        """列出所有活跃的 Agent（官员）并返回结果（用于多轮function calling）"""
        # role_map.md 在项目根目录的 data/ 下，不是在 agent 目录下
        # 尝试多个可能的路径
        possible_paths = [
            Path("data/role_map.md"),  # 相对于项目根目录
            Path(self.data_dir) / "../../role_map.md",  # 相对于 agent 目录向上 3 级
            Path.cwd() / "data" / "role_map.md",  # 绝对路径（基于当前工作目录）
        ]

        role_map_path = None
        for path in possible_paths:
            if path.exists():
                role_map_path = path
                break

        if not role_map_path:
            return "❌ 无法查询官员信息：role_map.md 文件不存在"

        try:
            # 读取并解析 role_map.md
            with open(role_map_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 解析每个官员的信息
            agents_info = []
            current_section = None

            for line in content.split("\n"):
                line = line.strip()

                # 匹配 ## 职位名称 (agent_id)
                if line.startswith("## "):
                    if current_section:
                        agents_info.append(current_section)
                    # 提取职位和 agent_id
                    title_line = line[3:].strip()
                    if "(" in title_line and ")" in title_line:
                        title = title_line[: title_line.index("(")].strip()
                        agent_id = title_line[
                            title_line.index("(") + 1 : title_line.index(")")
                        ].strip()
                        current_section = {
                            "title": title,
                            "agent_id": agent_id,
                            "name": None,
                            "duty": None,
                        }

                # 匹配 - 姓名：xxx
                elif line.startswith("- 姓名：") or line.startswith("- 姓名:"):
                    if current_section:
                        current_section["name"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()

                # 匹配 - 职责：xxx
                elif line.startswith("- 职责：") or line.startswith("- 职责:"):
                    if current_section:
                        current_section["duty"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()

            # 添加最后一个 section
            if current_section:
                agents_info.append(current_section)

            # 构建返回结果
            if agents_info:
                result_lines = ["朝廷现任官员："]
                for agent in agents_info:
                    name = agent.get("name", "未知")
                    title = agent.get("title", "未知职位")
                    agent_id = agent.get("agent_id", "unknown")
                    duty = agent.get("duty", "暂无职责描述")

                    result_lines.append(f"- {title} {name}（ID: {agent_id}）: {duty}")

                logger.info(
                    f"Agent {self.agent_id} listed agents from role_map.md: {[a['agent_id'] for a in agents_info]}"
                )
                return "\n".join(result_lines)
            else:
                return "❌ role_map.md 解析失败：未找到任何官员信息"

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error listing agents: {e}", exc_info=True)
            return f"❌ 查询官员列表失败：{str(e)}"

    async def _handle_get_agent_info_with_result(self, args: dict, event: Event) -> str:
        """获取某个 Agent 的详细信息（职责、性格等）并返回结果（用于多轮function calling）"""
        agent_id = args.get("agent_id")

        if not agent_id:
            return "❌ 请提供 agent_id 参数"

        # role_map.md 在项目根目录的 data/ 下，不是在 agent 目录下
        # 尝试多个可能的路径
        possible_paths = [
            Path("data/role_map.md"),  # 相对于项目根目录
            Path(self.data_dir) / "../../role_map.md",  # 相对于 agent 目录向上 3 级
            Path.cwd() / "data" / "role_map.md",  # 绝对路径（基于当前工作目录）
        ]

        role_map_path = None
        for path in possible_paths:
            if path.exists():
                role_map_path = path
                break

        if not role_map_path:
            return "❌ 无法查询官员信息：role_map.md 文件不存在"

        try:
            # 读取并解析 role_map.md
            with open(role_map_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 查找对应的 agent section
            current_section = None
            result_info = []

            for line in content.split("\n"):
                line = line.strip()

                # 匹配 ## 职位名称 (agent_id)
                if line.startswith("## "):
                    # 如果已经找到了目标 section，返回结果
                    if current_section and current_section.get("agent_id") == agent_id:
                        break

                    # 开始新的 section
                    title_line = line[3:].strip()
                    if "(" in title_line and ")" in title_line:
                        title = title_line[: title_line.index("(")].strip()
                        section_agent_id = title_line[
                            title_line.index("(") + 1 : title_line.index(")")
                        ].strip()
                        current_section = {"title": title, "agent_id": section_agent_id, "info": []}

                # 如果在目标 section 中，收集信息
                elif current_section and current_section.get("agent_id") == agent_id:
                    if line.startswith("-"):
                        result_info.append(line)
                    elif result_info:  # 遇到空行或新 section
                        break

            # 构建返回结果
            if result_info and current_section:
                title = current_section.get("title", "")
                name = next(
                    (
                        line.split("：", 1)[-1].split(":", 1)[-1].strip()
                        for line in result_info
                        if line.startswith("- 姓名") or line.startswith("- 姓名:")
                    ),
                    "",
                )

                result = f"【{title} - {name}】\n\n" + "\n".join(result_info)
                logger.info(f"Agent {self.agent_id} retrieved info for {agent_id} from role_map.md")
                return result
            else:
                return f"❌ 未找到官员 {agent_id} 的信息，请检查 role_map.md 中是否包含该职位"

        except Exception as e:
            logger.error(f"Agent {self.agent_id} error getting agent info: {e}", exc_info=True)
            return f"❌ 查询官员信息失败：{str(e)}"
