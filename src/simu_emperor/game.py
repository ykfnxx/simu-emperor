"""游戏循环编排器：阶段推进 + 多模块协调。"""

from __future__ import annotations

import asyncio
import random

from aiosqlite import Connection

from simu_emperor.agents.agent_manager import AgentManager
from simu_emperor.agents.context_builder import ContextBuilder
from simu_emperor.agents.file_manager import FileManager
from simu_emperor.agents.llm.client import LLMClient
from simu_emperor.agents.llm.providers import LLMProvider
from simu_emperor.agents.memory_manager import MemoryManager
from simu_emperor.agents.runtime import AgentRuntime
from simu_emperor.config import GameConfig
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
            await self._event_log_repo.log_event(
                self._state.game_id, self._state.current_turn, event, "applied"
            )
        for event in random_events:
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

        流程：
        1. 获取活跃 Agent 列表
        2. asyncio.gather 并行触发所有 Agent 汇总
        3. 持久化报告到 agent_reports 表
        4. 推进到 INTERACTION 阶段

        Returns:
            {agent_id: report_markdown} 的字典
        """
        if self._state.phase != GamePhase.SUMMARY:
            raise PhaseError(f"当前阶段为 {self._state.phase}，无法执行汇总")

        agents = self._agent_manager.list_active_agents()
        turn = self._state.current_turn

        async def _summarize_one(agent_id: str) -> tuple[str, str]:
            async with self._llm_semaphore:
                report = await self._runtime.summarize(agent_id, turn, self._state.base_data)
            # 持久化报告
            await self._report_repo.save_report(
                game_id=self._state.game_id,
                turn=turn,
                agent_id=agent_id,
                markdown=report,
                real_data=self._state.base_data,
                report_type="report",
                file_name=f"{turn:03d}_report.md",
            )
            return agent_id, report

        results = await asyncio.gather(*[_summarize_one(a) for a in agents])
        reports = dict(results)

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

        流程：
        1. 按命令分配 Agent 执行
        2. asyncio.gather 并行执行
        3. 收集 AgentEvent 加入 active_events
        4. 持久化命令和结果
        5. 推进到 EXECUTION 阶段

        Returns:
            AgentEvent 列表
        """
        if self._state.phase != GamePhase.INTERACTION:
            raise PhaseError(f"当前阶段为 {self._state.phase}，无法推进到执行")

        agents = self._agent_manager.list_active_agents()
        turn = self._state.current_turn
        agent_events = []

        async def _execute_one(command: PlayerEvent) -> None:
            # 选择执行 Agent：如有 target_province_id 则匹配 governor，否则用第一个 agent
            executor = agents[0] if agents else None
            for a in agents:
                if command.target_province_id and command.target_province_id in a:
                    executor = a
                    break

            if executor is None:
                return

            async with self._llm_semaphore:
                event = await self._runtime.execute(executor, turn, command, self._state.base_data)

            agent_events.append(event)
            self._state.active_events.append(event)

            # 持久化
            await self._command_repo.save_command(self._state.game_id, turn, command, event)
            # 执行结果写入报告表
            await self._report_repo.save_report(
                game_id=self._state.game_id,
                turn=turn,
                agent_id=executor,
                markdown=event.description,
                real_data=self._state.base_data,
                report_type="exec",
                file_name=f"{turn:03d}_exec_{command.command_type}.md",
            )

        if self._pending_commands:
            await asyncio.gather(*[_execute_one(cmd) for cmd in self._pending_commands])

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
