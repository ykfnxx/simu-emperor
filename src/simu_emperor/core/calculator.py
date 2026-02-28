"""
Calculator - 游戏状态管理器

负责回合协调和经济计算。
"""

import asyncio
import logging
from typing import Any

from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType


logger = logging.getLogger(__name__)


class Calculator:
    """
    游戏状态管理器（Calculator）

    特殊的 EventBus 订阅者，负责：
    - 协调回合结算（等待所有 Agent ready）
    - 执行经济公式（复用 V1 engine）
    - 修改数据库（唯一的写入权限）
    - 发布 turn_resolved 事件

    Attributes:
        event_bus: 事件总线
        repository: 数据库仓储
        agent_manager: Agent 管理器（可选）
        pending_ready: 等待中的 Agent ID 集合
        ready_timeout: ready 超时时间（秒）
        _running: 是否运行中
    """

    def __init__(self, event_bus: EventBus, repository: Any, agent_manager: Any = None):
        """
        初始化 Calculator

        Args:
            event_bus: 事件总线
            repository: 数据库仓储对象
            agent_manager: Agent 管理器对象（可选，用于获取活跃 Agent）
        """
        self.event_bus = event_bus
        self.repository = repository
        self.agent_manager = agent_manager
        self.pending_ready: set[str] = set()
        self.ready_timeout: float = 5.0  # 5 秒超时
        self._running: bool = False
        self._ready_timeout_task: asyncio.Task | None = None
        self._current_turn_chat_id: int | None = None  # 存储当前回合的 chat_id

        logger.info("Calculator initialized")

    def start(self) -> None:
        """
        启动 Calculator

        订阅相关事件：
        - end_turn: 玩家结束回合
        - ready: Agent 准备就绪
        - allocate_funds: 拨款
        - adjust_tax: 调整税率
        - build_irrigation: 建设水利
        - recruit_troops: 招募军队
        """
        self._running = True

        # 订阅系统事件
        self.event_bus.subscribe("*", self._on_end_turn)
        self.event_bus.subscribe("system:calculator", self._on_ready)

        # 订阅游戏动作事件
        self.event_bus.subscribe("system:calculator", self._on_allocate_funds)
        self.event_bus.subscribe("system:calculator", self._on_adjust_tax)
        self.event_bus.subscribe("system:calculator", self._on_build_irrigation)
        self.event_bus.subscribe("system:calculator", self._on_recruit_troops)

        logger.info("Calculator started and subscribed to events")

    def stop(self) -> None:
        """停止 Calculator"""
        self._running = False
        if self._ready_timeout_task:
            self._ready_timeout_task.cancel()
        logger.info("Calculator stopped")

    async def _on_end_turn(self, event: Event) -> None:
        """
        处理回合结束事件

        收集所有活跃 Agent，等待它们发送 ready 信号。

        Args:
            event: end_turn 事件
        """
        if event.type != EventType.END_TURN:
            return

        # 保存 chat_id 用于后续通知
        self._current_turn_chat_id = event.payload.get("chat_id")

        logger.info("Received end_turn event, collecting agent ready signals")

        # 获取所有活跃 Agent
        active_agents = await self._get_active_agents()
        logger.info(f"Active agents: {active_agents}")

        # 初始化 pending_ready 集合
        self.pending_ready = set(active_agents)

        # 如果没有 Agent，直接结算
        if not self.pending_ready:
            await self._resolve_turn()
            return

        # 启动超时任务
        self._ready_timeout_task = asyncio.create_task(self._ready_timeout_handler())

    async def _on_ready(self, event: Event) -> None:
        """
        处理 Agent 准备就绪事件

        从 pending_ready 中移除已就绪的 Agent。
        当所有 Agent 都就绪时，触发回合结算。

        Args:
            event: ready 事件
        """
        if event.type != EventType.READY:
            return

        agent_id = event.src
        if agent_id in self.pending_ready:
            self.pending_ready.remove(agent_id)
            logger.debug(f"Agent {agent_id} is ready. Remaining: {self.pending_ready}")

        # 检查是否所有 Agent 都就绪
        if not self.pending_ready:
            # 取消超时任务
            if self._ready_timeout_task:
                self._ready_timeout_task.cancel()
                self._ready_timeout_task = None

            logger.info("All agents ready, resolving turn")
            await self._resolve_turn()

    async def _ready_timeout_handler(self) -> None:
        """
        处理 ready 超时

        如果 5 秒后仍有 Agent 未发送 ready 信号，
        记录警告并强制进行回合结算。
        """
        try:
            await asyncio.sleep(self.ready_timeout)

            if self.pending_ready:
                logger.warning(
                    f"Ready timeout after {self.ready_timeout}s. "
                    f"Missing agents: {self.pending_ready}. "
                    f"Proceeding with turn resolution."
                )

            await self._resolve_turn()

        except asyncio.CancelledError:
            # 超时任务被取消（所有 Agent 都就绪）
            logger.debug("Ready timeout task cancelled")

    async def _resolve_turn(self) -> None:
        """
        执行回合结算

        1. 加载当前游戏状态
        2. 运行经济公式（复用 V1 engine）
        3. 保存新状态
        4. 保存回合指标
        5. 发布 turn_resolved 事件
        """
        logger.info("Resolving turn")

        try:
            # 加载当前状态（dict 格式）
            state_dict = await self.repository.load_state()
            current_turn = state_dict.get("turn", 0)

            # 转换为 Pydantic 模型
            from simu_emperor.engine.models.base_data import NationalBaseData
            from simu_emperor.engine.calculator import resolve_turn

            current_data = NationalBaseData.model_validate(state_dict)
            logger.info(f"Loaded game state for turn {current_turn}")

            # 运行经济公式（暂时无活跃事件）
            new_data, national_metrics = resolve_turn(current_data, active_events=[])

            # 转换回 dict 格式并保存
            new_state_dict = new_data.model_dump(mode='json')
            await self.repository.save_state(new_state_dict)

            # 保存回合指标
            metrics_dict = national_metrics.model_dump(mode='json')
            await self.repository.save_turn_metrics(new_data.turn, metrics_dict)

            # 发布 turn_resolved 事件（包含 chat_id 用于通知）
            payload = {
                "turn": new_data.turn,
                "metrics": metrics_dict,
            }
            if self._current_turn_chat_id is not None:
                payload["chat_id"] = self._current_turn_chat_id

            event = Event(
                src="system:calculator",
                dst=["*"],
                type=EventType.TURN_RESOLVED,
                payload=payload,
            )
            await self.event_bus.send_event(event)

            logger.info(
                f"Turn {new_data.turn} resolved - "
                f"Food: {national_metrics.imperial_treasury_change}, "
                f"Treasury: {new_data.imperial_treasury}"
            )

            # 清除 chat_id
            self._current_turn_chat_id = None

        except Exception as e:
            logger.error(f"Error resolving turn: {e}", exc_info=True)

    async def _on_allocate_funds(self, event: Event) -> None:
        """
        处理拨款事件

        Args:
            event: allocate_funds 事件
        """
        if event.type != EventType.ALLOCATE_FUNDS:
            return

        province = event.payload.get("province")
        amount = event.payload.get("amount")

        if province and amount is not None:
            state = await self.repository.load_state()

            # 检查国库余额
            imperial_treasury = state.get("imperial_treasury", 0)
            if imperial_treasury < amount:
                logger.warning(f"Insufficient funds in imperial treasury: {imperial_treasury} < {amount}")
                return

            # 扣除国库
            state["imperial_treasury"] = imperial_treasury - amount

            # 增加省库
            provinces = state.get("provinces", [])
            for p in provinces:
                if p.get("province_id") == province:
                    current_local = p.get("local_treasury", 0)
                    p["local_treasury"] = current_local + amount
                    break

            await self.repository.save_state(state)
            logger.info(f"Allocated {amount} from imperial treasury to {province}")
        else:
            logger.warning(f"Invalid allocation payload: {event.payload}")

    async def _on_adjust_tax(self, event: Event) -> None:
        """
        处理税率调整事件

        Args:
            event: adjust_tax 事件
        """
        if event.type != EventType.ADJUST_TAX:
            return

        province = event.payload.get("province")
        rate = event.payload.get("rate")

        if province and rate is not None:
            # 更新税率
            await self.repository.update_province_data(
                province, "taxation", {"land_tax_rate": rate}
            )
            logger.info(f"Tax rate updated: {province} -> {rate}")
        else:
            logger.warning(f"Invalid tax adjustment payload: {event.payload}")

    async def _on_build_irrigation(self, event: Event) -> None:
        """
        处理水利建设事件

        Args:
            event: build_irrigation 事件
        """
        if event.type != EventType.BUILD_IRRIGATION:
            return

        # TODO: 实现水利建设逻辑
        # province = event.payload.get("province")
        # level = event.payload.get("level")
        # await self.repository.update_irrigation(province, level)

        logger.info(f"Irrigation build requested: {event.payload}")

    async def _on_recruit_troops(self, event: Event) -> None:
        """
        处理招募军队事件

        Args:
            event: recruit_troops 事件
        """
        if event.type != EventType.RECRUIT_TROOPS:
            return

        # TODO: 实现招募军队逻辑
        # province = event.payload.get("province")
        # count = event.payload.get("count")
        # await self.repository.update_troops(province, count)

        logger.info(f"Troop recruitment requested: {event.payload}")

    async def _get_active_agents(self) -> list[str]:
        """
        获取所有活跃 Agent ID

        Returns:
            Agent ID 列表
        """
        # 优先从 AgentManager 获取
        if self.agent_manager:
            return self.agent_manager.get_active_agents()

        # 如果没有 AgentManager，尝试从数据库获取
        # 或者返回空列表（无 Agent 场景）
        logger.warning("No AgentManager available, returning empty agent list")
        return []
