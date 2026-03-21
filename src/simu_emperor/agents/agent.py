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
from simu_emperor.agents.tools import ActionTools, QueryTools
from simu_emperor.agents.tools.tool_registry import Tool, ToolRegistry
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
        # V4.1: 注入全局共享实例
        tape_writer=None,
        tape_metadata_mgr=None,
        engine=None,
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
            tape_writer: V4.1 全局共享的 TapeWriter 实例
            tape_metadata_mgr: V4.1 全局共享的 TapeMetadataManager 实例
            engine: Engine 实例（用于 incident 查询）
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

        # V4.1: 使用注入的实例（不再创建自己的副本）
        self._tape_writer = tape_writer
        self._tape_metadata_mgr = tape_metadata_mgr

        # V4.1: Use configured memory_dir
        self._memory_dir = Path(settings.memory.memory_dir).resolve()

        # 初始化工具类
        self._query_tools = QueryTools(
            agent_id=self.agent_id,
            repository=self.repository,
            data_dir=self.data_dir,
            engine=engine,
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

        # 初始化记忆系统初始化器
        from simu_emperor.agents.memory_initializer import MemoryInitializer

        self._memory_initializer = MemoryInitializer(
            self.agent_id,
            self._memory_dir,
            self.llm_provider,
            tape_writer=self._tape_writer,
            tape_metadata_mgr=self._tape_metadata_mgr,
        )

        # 自主记忆反思计数器
        self._memory_tick_counter = 0

        logger.info(f"Agent {agent_id} initialized")

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
        """统一注册所有工具到 ToolRegistry"""
        self._register_query_tools()
        self._register_memory_tools()
        self._register_action_tools()
        if self._task_session_tools:
            self._register_session_tools()

    def _register_query_tools(self) -> None:
        """注册 Query 类型工具"""
        # query_province_data
        self._tool_registry.register(
            Tool(
                name="query_province_data",
                description="查询某个省份的特定数据字段",
                parameters={
                    "type": "object",
                    "properties": {
                        "province_id": {
                            "type": "string",
                            "enum": [
                                "zhili",
                                "jiangsu",
                                "zhejiang",
                                "fujian",
                                "huguang",
                                "sichuan",
                                "shaanxi",
                                "shandong",
                                "jiangxi",
                            ],
                        },
                        "field_path": {"type": "string"},
                    },
                    "required": ["province_id", "field_path"],
                },
                handler=self._query_tools.query_province_data,
                category="query",
            )
        )

        # query_national_data
        self._tool_registry.register(
            Tool(
                name="query_national_data",
                description="查询国家级数据",
                parameters={
                    "type": "object",
                    "properties": {
                        "field_name": {
                            "type": "string",
                            "enum": [
                                "imperial_treasury",
                                "turn",
                                "base_tax_rate",
                                "tribute_rate",
                                "fixed_expenditure",
                            ],
                        }
                    },
                    "required": ["field_name"],
                },
                handler=self._query_tools.query_national_data,
                category="query",
            )
        )

        # list_provinces
        self._tool_registry.register(
            Tool(
                name="list_provinces",
                description="列出所有可访问的省份 ID",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._query_tools.list_provinces,
                category="query",
            )
        )

        # list_agents
        self._tool_registry.register(
            Tool(
                name="list_agents",
                description="列出所有活跃的官员",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._query_tools.list_agents,
                category="query",
            )
        )

        # get_agent_info
        self._tool_registry.register(
            Tool(
                name="get_agent_info",
                description="获取某个官员的详细信息",
                parameters={
                    "type": "object",
                    "properties": {"agent_id": {"type": "string"}},
                    "required": ["agent_id"],
                },
                handler=self._query_tools.get_agent_info,
                category="query",
            )
        )

        # query_incidents
        self._tool_registry.register(
            Tool(
                name="query_incidents",
                description="查询当前活跃的游戏事件（旱灾、丰收等），可按省份或来源过滤",
                parameters={
                    "type": "object",
                    "properties": {
                        "filter_province": {
                            "type": "string",
                            "description": "按省份 ID 过滤（可选）",
                        },
                        "filter_source": {
                            "type": "string",
                            "description": "按来源过滤（可选）",
                        },
                    },
                    "required": [],
                },
                handler=self._query_tools.query_incidents,
                category="query",
            )
        )

    def _register_memory_tools(self) -> None:
        """注册 Memory 类型工具"""
        self._tool_registry.register(
            Tool(
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
                handler=self._retrieve_memory_wrapper,
                category="memory",
            )
        )

    def _register_action_tools(self) -> None:
        """注册 Action 类型工具"""
        # send_message (统一的消息发送接口)
        self._tool_registry.register(
            Tool(
                name="send_message",
                description="发送消息（统一接口）",
                parameters={
                    "type": "object",
                    "properties": {
                        "recipients": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "content": {"type": "string"},
                        "await_reply": {"type": "boolean", "default": False},
                    },
                    "required": ["recipients", "content"],
                },
                handler=self._action_tools.send_message,
                category="action",
            )
        )

        # finish_loop
        self._tool_registry.register(
            Tool(
                name="finish_loop",
                description="结束当前 agent loop",
                parameters={
                    "type": "object",
                    "properties": {"reason": {"type": "string"}},
                    "required": ["reason"],
                },
                handler=self._action_tools.finish_loop,
                category="action",
            )
        )

        # create_incident
        self._tool_registry.register(
            Tool(
                name="create_incident",
                description="创建持续 N 个 tick 的游戏事件",
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "effects": {"type": "array", "items": {"type": "object"}},
                        "duration_ticks": {"type": "integer", "minimum": 1},
                    },
                    "required": ["title", "description", "effects", "duration_ticks"],
                },
                handler=self._action_tools.create_incident,
                category="action",
            )
        )

        # write_memory (短期记忆，turn_*.md)
        self._tool_registry.register(
            Tool(
                name="write_memory",
                description="写入短期记忆摘要（turn_*.md，保留最近3回合）",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "记忆内容"},
                    },
                    "required": ["content"],
                },
                handler=self._action_tools.write_memory,
                category="action",
            )
        )

        # write_long_term_memory (长期记忆，MEMORY.md)
        self._tool_registry.register(
            Tool(
                name="write_long_term_memory",
                description="写入长期记忆（MEMORY.md，永久保存的重要记忆）",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "长期记忆内容（重要事件、关键决策、深刻感悟）",
                        },
                    },
                    "required": ["content"],
                },
                handler=self._action_tools.write_long_term_memory,
                category="action",
            )
        )

        # update_soul (性格演化，soul.md 追加)
        self._tool_registry.register(
            Tool(
                name="update_soul",
                description="记录性格变化（追加到 soul.md，仅在重大转变时使用）",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "性格变化描述（什么事件导致了什么性格转变）",
                        },
                    },
                    "required": ["content"],
                },
                handler=self._action_tools.update_soul,
                category="action",
            )
        )

    def _register_session_tools(self) -> None:
        """注册 Session 类型工具"""
        self._tool_registry.register(
            Tool(
                name="create_task_session",
                description="创建任务会话",
                parameters={
                    "type": "object",
                    "properties": {
                        "timeout_seconds": {"type": "integer", "default": 300},
                        "description": {"type": "string"},
                        "goal": {"type": "string"},
                        "constraints": {"type": "string"},
                    },
                    "required": [],
                },
                handler=self._wrap_create_task_session,
                category="session",
            )
        )

        self._tool_registry.register(
            Tool(
                name="finish_task_session",
                description="完成任务会话",
                parameters={
                    "type": "object",
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                },
                handler=self._wrap_finish_task_session,
                category="session",
            )
        )

        self._tool_registry.register(
            Tool(
                name="fail_task_session",
                description="任务会话失败",
                parameters={
                    "type": "object",
                    "properties": {"reason": {"type": "string"}},
                    "required": ["reason"],
                },
                handler=self._wrap_fail_task_session,
                category="session",
            )
        )

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
                await self._process_event_with_llm(event, event.session_id)
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
            await self._process_event_with_llm(event, session_id)
        except Exception as e:
            logger.error(
                f"❌ [Agent:{self.agent_id}:{session_id}] Error processing event: {e}",
                exc_info=True,
            )

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

        # 获取 session 状态
        session = await self.session_manager.get_session(event.session_id)
        if not session:
            return True  # session 不存在，默认处理

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

    async def _process_event_with_llm(self, event: Event, session_id: str) -> None:
        """
        使用 LLM 处理事件（ReAct Observation 模式）。

        ReAct 循环架构：
        1. LLM 返回 thought + tool_calls
        2. 执行工具并创建 Observation
        3. 将 Observation 添加到 tape
        4. 检查是否应该停止（send_message, finish_loop, create_task_session）
        5. 重复直到可以给出最终响应

        所有事件通过 ContextManager.add_event_and_maybe_compact() 添加。
        ContextManager 内部负责写入 tape.jsonl。

        Args:
            event: 当前事件
            session_id: 会话 ID
        """
        # 检查是否有尚待完成的异步任务，如果有则跳过处理
        if not await self._check_and_restore_agent_state(event, session_id):
            return

        # Capture turn start time to ensure event ordering
        turn_start_time = datetime.now(timezone.utc).isoformat()

        # V4: 设置 system_prompt（仅首次）
        if self._context_manager and self._context_manager._system_prompt is None:
            root_event_type = await self._get_root_event_type(event, session_id)
            system_prompt = self._get_system_prompt_for_event(root_event_type)
            self._context_manager._system_prompt = system_prompt

        # V4: 将当前事件添加到 ContextManager（内部自动写入 tape）
        await self._context_manager.add_event_and_maybe_compact(event)

        # 多轮 function calling 循环
        max_iterations = 10  # 防止无限循环
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            logger.info(
                f"🔄 [Agent:{self.agent_id}:{session_id}] Iteration {iteration}: Calling LLM..."
            )

            # V4: 每次迭代从 ContextManager 获取最新消息
            messages = await self._context_manager.get_llm_messages()

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

            # 处理响应
            if not tool_calls:
                await self._handle_no_tool_calls(event, session_id, response_text)
                break

            # 执行 tool calls 并创建 Observation（ReAct 模式）
            observation = await self._execute_tools_and_create_observation(
                event,
                session_id,
                iteration,
                tool_calls,
                response_text,
                turn_start_time,
            )

            # 将 Observation 添加到 tape
            await self._add_observation_to_tape(event, session_id, observation)

            # 检查退出条件
            # create_task_session 优先级最高，创建任务后应立即停止主session的LLM循环
            if observation.get("has_create_task_session"):
                logger.info(
                    f"📋 [Agent:{self.agent_id}:{session_id}] create_task_session called, task session created. "
                    f"Main session loop ending to wait for task completion."
                )
                break

            # finish_loop 其次
            if observation.get("has_finish_loop"):
                logger.info(
                    f"🔄 [Agent:{self.agent_id}:{session_id}] finish_loop called (priority check), ending loop"
                )
                break

            # 如果已经有send_message（发送给player），说明第一轮LLM已经生成了最终响应，可以结束
            if observation.get("has_send_message"):
                logger.info(
                    f"✅ [Agent:{self.agent_id}:{session_id}] send_message called, ending loop"
                )
                break

            # 否则继续循环，让 LLM 基于工具调用结果生成最终响应
            logger.info(
                f"✅ [Agent:{self.agent_id}:{session_id}] Tool calls executed, requesting final response from LLM..."
            )

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
        functions = self._tool_registry.to_function_definitions()
        result = await self.llm_provider.call_with_functions(
            functions=functions,
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
            request={"messages": messages, "functions": functions},
            response=result,
            duration_ms=duration_ms,
        )

        return result

    async def _execute_tools_and_create_observation(
        self,
        event: Event,
        session_id: str,
        iteration: int,
        tool_calls: list,
        response_text: str,
        turn_start_time: str,
    ) -> dict:
        """
        执行工具并创建 Observation（ReAct 模式）

        Args:
            event: 当前事件
            session_id: 会话 ID
            iteration: 迭代次数
            tool_calls: 工具调用列表
            response_text: LLM 响应文本（thought）
            turn_start_time: Turn开始时间戳（用于确保事件顺序）

        Returns:
            Observation dict 包含 thought, actions, has_send_message, has_finish_loop, has_create_task_session
        """
        observation = {
            "thought": response_text,
            "actions": [],
            "has_send_message": False,
            "has_finish_loop": False,
            "has_create_task_session": False,
        }

        for idx, tool_call in enumerate(tool_calls, 1):
            function_name = tool_call["function"]["name"]
            function_args = json.loads(tool_call["function"]["arguments"])

            logger.info(
                f"⚙️  [Agent:{self.agent_id}:{session_id}] [Iter {iteration}, {idx}/{len(tool_calls)}] Calling: {function_name}"
            )

            result = await self._call_function_with_result(function_name, function_args, event)

            # V4: 处理 tool 返回值
            # 如果返回元组 (message, event)，提取消息和事件
            result_str = result
            result_event = None
            if isinstance(result, tuple):
                result_str, result_event = result

            # 记录 action
            observation["actions"].append(
                {
                    "tool": function_name,
                    "result": result_str,
                }
            )

            # 检查函数是否成功执行
            if function_name == "finish_loop":
                # finish_loop 成功时返回 "✅ finish_loop 已执行..."
                if result_str.startswith("✅"):
                    observation["has_finish_loop"] = True
                else:
                    logger.warning(
                        f"⚠️ [Agent:{self.agent_id}:{session_id}] finish_loop 执行失败: {result_str}"
                    )

            if function_name == "send_message":
                # V4: send_message 返回元组 (message, event)
                # 只要消息以 ✅ 或 等待 开头就认为成功
                if result_str.startswith("✅") or result_str.startswith("等待"):
                    observation["has_send_message"] = True
                # V4: 将事件添加到 ContextManager（如果返回了事件）
                if result_event:
                    await self._context_manager.add_event_and_maybe_compact(result_event)

            if function_name == "create_task_session":
                # create_task_session 返回 JSON，需要解析检查 success 字段
                try:
                    result_data = json.loads(result_str)
                    if result_data.get("success") is True:
                        observation["has_create_task_session"] = True
                    else:
                        logger.warning(
                            f"⚠️ [Agent:{self.agent_id}:{session_id}] create_task_session 执行失败: {result_str}"
                        )
                except json.JSONDecodeError:
                    logger.warning(
                        f"⚠️ [Agent:{self.agent_id}:{session_id}] create_task_session 返回无效 JSON: {result_str}"
                    )

        return observation

    async def _add_observation_to_tape(
        self, event: Event, session_id: str, observation: dict
    ) -> None:
        """
        将 Observation 添加到 tape 并发送到 EventBus

        Args:
            event: 当前事件
            session_id: 会话 ID
            observation: Observation dict
        """
        observation_event = Event(
            src=f"agent:{self.agent_id}",
            dst=[f"benchmark:{session_id}"],
            type=EventType.OBSERVATION,
            payload=observation,
            session_id=event.session_id,
            parent_event_id=event.event_id,
            root_event_id=event.root_event_id,
        )
        await self._context_manager.add_event_and_maybe_compact(observation_event)
        await self.event_bus.send_event(observation_event)

    async def _handle_no_tool_calls(
        self, event: Event, session_id: str, response_text: str
    ) -> None:
        """
        处理无 tool calls 的情况（直接创建 AGENT_MESSAGE 事件）

        Args:
            event: 当前事件
            session_id: 会话 ID
            response_text: LLM 响应文本
        """
        logger.info(f"✅ [Agent:{self.agent_id}:{session_id}] No more tool calls, ending loop")

        # 发送最终响应（即使为空也要响应）
        final_message = response_text if response_text else "抱歉，我暂时无法理解您的请求。"

        # 直接创建 AGENT_MESSAGE 事件（不通过工具调用）
        message_event = Event(
            src=f"agent:{self.agent_id}",
            dst=["player"],
            type=EventType.AGENT_MESSAGE,
            payload={"content": final_message, "await_reply": False},
            session_id=event.session_id,
            parent_event_id=event.event_id,
            root_event_id=event.root_event_id,
        )
        await self.event_bus.send_event(message_event)

        # 将 AGENT_MESSAGE 事件添加到 tape
        if self._context_manager:
            await self._context_manager.add_event_and_maybe_compact(message_event)

        logger.info(
            f"💬 [Agent:{self.agent_id}:{session_id}] Sending final response: {final_message[:50]}..."
        )

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

            return {"role": "user", "content": "\n".join(parts)}

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
        """
        调用 function handler 并返回结果（多轮模式）

        使用 ToolRegistry 获取工具处理器。

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
            # 从 ToolRegistry 获取工具
            tool = self._tool_registry.get(function_name)
            if tool is None:
                return f"❌ 未知工具: {function_name}"

            # 执行工具处理函数
            result = await tool.handler(arguments, original_event)
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
