"""游戏循环编排器：阶段推进 + 多模块协调。"""

from __future__ import annotations

import asyncio
import random
from uuid import uuid4

from aiosqlite import Connection

from simu_emperor.agents.agent_manager import AgentManager
from simu_emperor.agents.context_builder import ContextBuilder
from simu_emperor.agents.event_handler import AgentEventHandler
from simu_emperor.agents.file_manager import FileManager
from simu_emperor.agents.llm.client import LLMClient
from simu_emperor.agents.llm.providers import LLMProvider
from simu_emperor.agents.memory_manager import MemoryManager
from simu_emperor.agents.runtime import AgentRuntime
from simu_emperor.config import GameConfig
from simu_emperor.core.event_bus import (
    ControlEvent,
    EventBus,
    EventPriority,
    EventType,
)
from simu_emperor.engine.calculator import resolve_turn
from simu_emperor.engine.event_generator import generate_events_for_turn, load_event_templates
from simu_emperor.engine.models.events import PlayerEvent
from simu_emperor.engine.models.metrics import NationalTurnMetrics
from simu_emperor.engine.models.state import GamePhase, GameState, TurnRecord
from simu_emperor.persistence.repositories import (
    AgentReportRepository,
    ChatHistoryRepository,
    EventLogRepository,
    GameSaveRepository,
    PlayerCommandRepository,
)
from simu_emperor.utils.logger import log_event, setup_logging


class PhaseError(Exception):
    """当前阶段不允许执行的操作。"""


class GameLoop:
    """游戏循环编排器，严格按阶段推进。

    阶段顺序：RESOLUTION → SUMMARY → INTERACTION → EXECUTION → RESOLUTION → ...

    - RESOLUTION: 回合结算（apply events + economic formulas + random events）
    - SUMMARY: Agent 汇总报告（asyncio.gather 并行）
    - INTERACTION: 玩家与 Agent 对话
    - EXECUTION: Agent 执行命令（asyncio.gather 并行）
    """

    def __init__(
        self,
        state: GameState,
        config: GameConfig,
        provider: LLMProvider,
        conn: Connection,
    ) -> None:
        self._state = state
        self._config = config
        self._conn = conn

        # 初始化日志系统
        setup_logging(config)

        # 文件系统层
        data_dir = config.data_dir
        self._file_manager = FileManager(
            agent_base=data_dir / "agent",
            template_base=data_dir / "default_agents",
            skills_dir=data_dir / "skills",
        )
        self._agent_manager = AgentManager(
            file_manager=self._file_manager,
            saves_dir=data_dir / "saves",
        )
        self._context_builder = ContextBuilder(self._file_manager)
        self._memory_manager = MemoryManager(self._file_manager)

        # LLM 层
        self._llm_client = LLMClient(provider)
        self._runtime = AgentRuntime(
            self._llm_client,
            self._context_builder,
            self._memory_manager,
            self._file_manager,
        )

        # 持久化层
        self._save_repo = GameSaveRepository(conn)
        self._event_log_repo = EventLogRepository(conn)
        self._report_repo = AgentReportRepository(conn)
        self._chat_repo = ChatHistoryRepository(conn)
        self._command_repo = PlayerCommandRepository(conn)

        # 随机数生成器
        self._rng = random.Random(config.seed)

        # 事件模板
        templates_path = data_dir / "event_templates.json"
        if templates_path.exists():
            self._event_templates = load_event_templates(templates_path)
        else:
            self._event_templates = []

        # LLM 并发限流
        self._llm_semaphore = asyncio.Semaphore(config.agent.max_concurrent_llm_calls)

        # 回合内待执行命令
        self._pending_commands: list[PlayerEvent] = []

        # 最新指标缓存
        self._latest_metrics: NationalTurnMetrics | None = None

        # 事件总线（Phase 1 新增）
        self._event_bus = EventBus(max_queue_size=1000)

        # Agent 事件处理器（Phase 1 新增）
        self._agent_handlers: dict[str, AgentEventHandler] = {}

    # ── 属性 ──

    @property
    def state(self) -> GameState:
        return self._state

    @property
    def phase(self) -> GamePhase:
        return self._state.phase

    @property
    def latest_metrics(self) -> NationalTurnMetrics | None:
        return self._latest_metrics

    # ── 生命周期（Phase 1 新增）──

    async def initialize(self) -> None:
        """初始化事件总线（应用启动时调用）。"""
        # 启动事件总线
        await self._event_bus.start()

        # 为每个 Agent 创建事件处理器
        agents = self._agent_manager.list_active_agents()
        for agent_id in agents:
            handler = AgentEventHandler(
                agent_id=agent_id,
                event_bus=self._event_bus,
                runtime=self._runtime,
            )
            self._agent_handlers[agent_id] = handler

    async def cleanup(self) -> None:
        """清理资源（应用关闭时调用）。"""
        # 取消所有 Agent 订阅
        for handler in self._agent_handlers.values():
            handler.unsubscribe_all()
        self._agent_handlers.clear()

        # 停止事件总线
        await self._event_bus.stop()

    def register_agent_handler(self, agent_id: str) -> None:
        """注册新 Agent 的事件处理器。"""
        if agent_id not in self._agent_handlers:
            handler = AgentEventHandler(
                agent_id=agent_id,
                event_bus=self._event_bus,
                runtime=self._runtime,
            )
            self._agent_handlers[agent_id] = handler

    def unregister_agent_handler(self, agent_id: str) -> None:
        """注销 Agent 的事件处理器。"""
        handler = self._agent_handlers.pop(agent_id, None)
        if handler:
            handler.unsubscribe_all()

    # ── 阶段推进 ──

    async def advance_to_resolution(self) -> tuple[GameState, NationalTurnMetrics]:
        """推进到 RESOLUTION 阶段：回合结算。

        前置条件：当前阶段为 EXECUTION（首回合为 RESOLUTION）。

        流程：
        1. resolve_turn(base_data, active_events) → (new_data, metrics)
        2. 生成随机事件
        3. 记录 TurnRecord 到 history
        4. 更新 state
        5. 推进到 SUMMARY 阶段

        Returns:
            (更新后的 GameState, 本回合指标)
        """
        if self._state.phase != GamePhase.EXECUTION and self._state.current_turn > 0:
            raise PhaseError(f"当前阶段为 {self._state.phase}，无法推进到 RESOLUTION")

        # 回合结算
        new_data, metrics = resolve_turn(self._state.base_data, self._state.active_events)
        self._latest_metrics = metrics

        # 记录 TurnRecord
        turn_record = TurnRecord(
            turn=self._state.current_turn,
            base_data_snapshot=self._state.base_data,
            events_applied=list(self._state.active_events),
            metrics=metrics,
        )
        self._state.history.append(turn_record)

        # 生成随机事件
        province_ids = [p.province_id for p in new_data.provinces]
        random_events = generate_events_for_turn(
            self._event_templates,
            new_data.turn,
            province_ids,
            self._rng,
            max_events=self._config.max_random_events_per_turn,
        )

        # 记录事件日志
        for event in self._state.active_events:
            log_event(event, action="applied")
            await self._event_log_repo.log_event(
                self._state.game_id, self._state.current_turn, event, "applied"
            )
        for event in random_events:
            log_event(event, action="generated")
            await self._event_log_repo.log_event(
                self._state.game_id, new_data.turn, event, "generated"
            )

        # 更新 state
        self._state.base_data = new_data
        self._state.current_turn = new_data.turn
        self._state.active_events = list(random_events)
        self._state.phase = GamePhase.SUMMARY
        self._pending_commands = []

        return self._state, metrics

    async def advance_to_summary(self) -> dict[str, str]:
        """推进到 SUMMARY 阶段：Agent 汇总报告。

        前置条件：当前阶段为 SUMMARY。

        流程（Phase 1 使用事件总线）：
        1. 获取活跃 Agent 列表
        2. 通过事件总线发布汇总请求
        3. 等待所有 Agent 完成汇总
        4. 持久化报告到 agent_reports 表
        5. 推进到 INTERACTION 阶段

        Returns:
            {agent_id: report_markdown} 的字典
        """
        if self._state.phase != GamePhase.SUMMARY:
            raise PhaseError(f"当前阶段为 {self._state.phase}，无法执行汇总")

        agents = self._agent_manager.list_active_agents()
        turn = self._state.current_turn

        if not agents:
            self._state.phase = GamePhase.INTERACTION
            return {}

        # 使用事件总线发布汇总请求
        correlation_id = uuid4().hex

        # 为每个 Agent 创建 Future
        futures: dict[str, asyncio.Future[ControlEvent]] = {}
        for agent_id in agents:
            # 发布汇总请求事件
            await self._event_bus.publish(
                event_type=EventType.AGENT_SUMMARY_REQUESTED,
                turn=turn,
                phase=self._state.phase,
                agent_id=agent_id,
                payload={
                    "national_data": self._state.base_data.model_dump(),
                },
                priority=EventPriority.NORMAL,
                correlation_id=correlation_id,
            )
            # 创建对应的 Future
            futures[agent_id] = self._event_bus.create_request_future(
                correlation_id=correlation_id,
                agent_id=agent_id,
            )

        # 并发等待所有 Future，带超时
        async def wait_one(agent_id: str, fut: asyncio.Future[ControlEvent]) -> tuple[str, str | None]:
            try:
                event = await asyncio.wait_for(fut, timeout=60.0)
                return agent_id, event.payload.get("report", "")
            except asyncio.TimeoutError:
                return agent_id, None
            except asyncio.CancelledError:
                return agent_id, None

        results = await asyncio.gather(*[wait_one(aid, fut) for aid, fut in futures.items()])

        # 处理结果
        reports: dict[str, str] = {}
        for agent_id, report in results:
            if report is not None:
                reports[agent_id] = report
            else:
                # 超时时生成占位符报告
                reports[agent_id] = f"# 报告生成超时\n\nAgent {agent_id} 未在 60s 内完成报告。"
                self._event_bus.cancel_request(correlation_id, agent_id)

            # 无论成功或超时，都持久化报告
            await self._report_repo.save_report(
                game_id=self._state.game_id,
                turn=turn,
                agent_id=agent_id,
                markdown=reports[agent_id],
                real_data=self._state.base_data,
                report_type="report",
                file_name=f"{turn:03d}_report.md",
            )

        self._state.phase = GamePhase.INTERACTION
        return reports

    async def handle_player_message(self, agent_id: str, message: str) -> str:
        """交互阶段：处理玩家与 Agent 的对话。

        前置条件：当前阶段为 INTERACTION。

        Args:
            agent_id: 目标 Agent ID
            message: 玩家消息

        Returns:
            Agent 的回答
        """
        if self._state.phase != GamePhase.INTERACTION:
            raise PhaseError(f"当前阶段为 {self._state.phase}，无法与 Agent 对话")

        async with self._llm_semaphore:
            response = await self._runtime.respond(
                agent_id, self._state.current_turn, message, self._state.base_data
            )

        # 持久化对话
        await self._chat_repo.add_message(self._state.game_id, agent_id, "player", message)
        await self._chat_repo.add_message(self._state.game_id, agent_id, "agent", response)

        return response

    async def _build_agent_context(self, agent_id: str, player_message: str):
        """构建 Agent 对话上下文（用于流式输出）。

        Args:
            agent_id: Agent ID
            player_message: 玩家消息

        Returns:
            AgentContext 对象
        """
        from simu_emperor.agents.context_builder import AgentContext

        # 读取记忆
        mem = self._memory_manager.read_context(agent_id)

        # 组装上下文
        context = self._context_builder.build_context(
            agent_id=agent_id,
            skill_name="query_data",
            national_data=self._state.base_data,
            memory_summary=mem.summary,
            recent_memories=mem.recent,
        )

        # 将玩家消息附加到 skill prompt 中
        context = AgentContext(
            agent_id=context.agent_id,
            soul=context.soul,
            skill=context.skill + f"\n\n## 玩家问话\n{player_message}",
            data=context.data,
            memory_summary=context.memory_summary,
            recent_memories=context.recent_memories,
        )

        return context

    def submit_command(self, command: PlayerEvent) -> None:
        """交互阶段：提交玩家命令。

        direct=True 的命令直接加入 active_events。
        direct=False 的命令暂存，等待执行阶段由 Agent 处理。

        前置条件：当前阶段为 INTERACTION。
        """
        if self._state.phase != GamePhase.INTERACTION:
            raise PhaseError(f"当前阶段为 {self._state.phase}，无法提交命令")

        if command.direct:
            self._state.active_events.append(command)
        else:
            self._pending_commands.append(command)

    async def advance_to_execution(self) -> list:
        """推进到 EXECUTION 阶段：Agent 执行命令。

        前置条件：当前阶段为 INTERACTION。

        流程（Phase 1 使用事件总线）：
        1. 按命令分配 Agent 执行
        2. 通过事件总线发布执行请求
        3. 等待所有 Agent 完成执行
        4. 收集 AgentEvent 加入 active_events
        5. 持久化命令和结果
        6. 推进到 EXECUTION 阶段

        Returns:
            AgentEvent 列表
        """
        if self._state.phase != GamePhase.INTERACTION:
            raise PhaseError(f"当前阶段为 {self._state.phase}，无法推进到执行")

        agents = self._agent_manager.list_active_agents()
        turn = self._state.current_turn
        agent_events = []

        if not self._pending_commands:
            self._state.phase = GamePhase.EXECUTION
            return agent_events

        # 使用事件总线发布执行请求
        correlation_id = uuid4().hex

        # 为每个命令分配执行 Agent 并发布执行请求
        command_agent_pairs: list[tuple[PlayerEvent, str]] = []
        futures: dict[str, asyncio.Future[ControlEvent]] = {}

        for idx, command in enumerate(self._pending_commands):
            # 选择执行 Agent：如有 target_province_id 则匹配 governor，否则用第一个 agent
            executor = agents[0] if agents else None
            for a in agents:
                if command.target_province_id and command.target_province_id in a:
                    executor = a
                    break

            if executor is None:
                continue

            command_agent_pairs.append((command, executor))
            request_key = f"{idx}:{command.event_id}"

            # 发布执行请求事件
            await self._event_bus.publish(
                event_type=EventType.AGENT_EXECUTE_REQUESTED,
                turn=turn,
                phase=self._state.phase,
                agent_id=executor,
                payload={
                    "national_data": self._state.base_data.model_dump(),
                    "command": command.model_dump(),
                },
                priority=EventPriority.HIGH,
                correlation_id=correlation_id,
            )

            # 创建对应的 Future
            futures[request_key] = self._event_bus.create_request_future(
                correlation_id=correlation_id,
                agent_id=executor,
            )

        # 并发等待所有 Future，带超时
        async def wait_one(key: str, command: PlayerEvent, agent_id: str, fut: asyncio.Future[ControlEvent]):
            try:
                event = await asyncio.wait_for(fut, timeout=60.0)
                return key, command, agent_id, event.payload.get("agent_event"), None
            except asyncio.TimeoutError:
                return key, command, agent_id, None, "timeout"
            except asyncio.CancelledError:
                return key, command, agent_id, None, "cancelled"

        wait_tasks = [
            wait_one(key, cmd, agent_id, fut)
            for (cmd, agent_id), (key, fut) in zip(command_agent_pairs, futures.items())
        ]

        if wait_tasks:
            results = await asyncio.gather(*wait_tasks)

            # 处理结果
            from simu_emperor.engine.models.events import AgentEvent

            for key, command, agent_id, event_data, error in results:
                if error:
                    self._event_bus.cancel_request(correlation_id, agent_id)
                    continue

                if event_data:
                    agent_event = AgentEvent.model_validate(event_data)
                    agent_events.append(agent_event)
                    self._state.active_events.append(agent_event)

                    # 持久化
                    await self._command_repo.save_command(self._state.game_id, turn, command, agent_event)
                    # 执行结果写入报告表
                    await self._report_repo.save_report(
                        game_id=self._state.game_id,
                        turn=turn,
                        agent_id=agent_id,
                        markdown=agent_event.description,
                        real_data=self._state.base_data,
                        report_type="exec",
                        file_name=f"{turn:03d}_exec_{command.command_type}.md",
                    )

        self._state.phase = GamePhase.EXECUTION
        self._pending_commands = []

        return agent_events

    # ── 存档/加载 ──

    async def save_game(self) -> None:
        """保存当前游戏状态。"""
        await self._save_repo.save(self._state)
        self._agent_manager.save_snapshot(self._state.game_id, self._state.current_turn)

    async def load_game(self, game_id: str, turn: int | None = None) -> GameState:
        """加载游戏存档。"""
        state = await self._save_repo.load(game_id, turn)
        if state is None:
            raise ValueError(f"未找到存档：game_id={game_id}, turn={turn}")

        self._state = state
        loaded_agents = self._agent_manager.load_snapshot(game_id, state.current_turn)
        if loaded_agents:
            await self._agent_manager.rebuild_workspace(
                game_id, state.current_turn, self._report_repo
            )

        return self._state

    # ── 新游戏 ──

    def initialize_agents(self) -> list[str]:
        """初始化 Agent 文件系统（新游戏时调用）。"""
        return self._agent_manager.initialize_game()
