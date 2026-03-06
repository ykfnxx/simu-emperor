"""
Telegram 会话管理

每个 Telegram 用户有独立的游戏会话，包含独立的 EventBus、Repository、AgentManager 和 Calculator。
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from telegram.ext import Application

from simu_emperor.config import GameConfig
from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.event_bus.logger import FileEventLogger, DatabaseEventLogger
from simu_emperor.persistence import init_database, close_database
from simu_emperor.persistence.repositories import GameRepository
from simu_emperor.engine.coordinator import TurnCoordinator
from simu_emperor.agents.manager import AgentManager
from simu_emperor.llm.base import LLMProvider
from simu_emperor.adapters.telegram.session_context import SessionContextManager
from simu_emperor.adapters.telegram.session_context import EventCategory


logger = logging.getLogger(__name__)


class GameSession:
    """
    单个 Telegram 用户的游戏会话

    每个会话包含：
    - 独立的数据库（sessions/telegram_{chat_id}.db）
    - 独立的事件总线
    - 独立的 Repository
    - 独立的 Calculator
    - 独立的 AgentManager
    - Session 上下文管理器（用于 session 切换）

    Attributes:
        chat_id: Telegram 聊天 ID
        player_id: 玩家 ID（格式：player:telegram:{chat_id}）
        session_id: 基础会话 ID（格式：session:telegram:{chat_id}）
        settings: 游戏配置
        db_path: 数据库路径
        event_bus: 事件总线
        repository: 数据库仓储
        calculator: 游戏状态管理器
        agent_manager: Agent 管理器
        bot_application: Telegram Bot 应用实例
        llm_provider: LLM 提供商
        session_context_manager: Session 上下文管理器
    """

    def __init__(
        self,
        chat_id: int,
        settings: GameConfig,
        bot_application: Application,
        llm_provider: LLMProvider,
    ):
        """
        初始化游戏会话

        Args:
            chat_id: Telegram 聊天 ID
            settings: 游戏配置
            bot_application: Telegram Bot 应用实例
            llm_provider: LLM 提供商
        """
        self.chat_id = chat_id
        self.player_id = f"player:telegram:{chat_id}"
        self.session_id = f"session:telegram:{chat_id}"
        self.settings = settings
        self.bot_application = bot_application
        self.llm_provider = llm_provider

        # 独立数据库
        sessions_dir = settings.data_dir / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = str(sessions_dir / f"telegram_{chat_id}.db")

        # 延迟初始化的组件
        self.event_bus: EventBus | None = None
        self.repository: GameRepository | None = None
        self.calculator: Calculator | None = None
        self.agent_manager: AgentManager | None = None
        self._running: bool = False

        # Session 上下文管理器
        self.session_context_manager: SessionContextManager | None = None

        logger.info(f"GameSession created for chat_id={chat_id}")

    async def start(self) -> None:
        """启动会话"""
        if self._running:
            logger.warning(f"Session {self.chat_id} already running")
            return

        logger.info(f"Starting session for chat_id={self.chat_id}")

        # 0. 初始化 SessionContextManager
        self.session_context_manager = SessionContextManager(
            chat_id=self.chat_id,
            base_session_id=self.session_id,
            chat_ttl_hours=24,
            command_ttl_hours=1,
        )
        await self.session_context_manager.start_cleanup_task(interval_seconds=3600)
        logger.info("SessionContextManager initialized")

        # 1. 初始化数据库
        conn = await init_database(self.db_path)
        self.repository = GameRepository(conn)
        logger.info(f"Database initialized: {self.db_path}")

        # 1.5. 初始化游戏状态（如果为空）
        await self._initialize_game_state()

        # 2. 初始化事件日志记录器
        log_dir = self.settings.log_dir / "events"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_logger = FileEventLogger(log_dir)
        db_logger = DatabaseEventLogger(conn)
        logger.info("Event loggers initialized")

        # 2.5. 初始化事件总线
        self.event_bus = EventBus(file_logger=file_logger, db_logger=db_logger)

        # 订阅响应事件
        self.event_bus.subscribe(self.player_id, self._on_response)
        # 订阅回合结算完成事件
        self.event_bus.subscribe(self.player_id, self._on_turn_resolved)
        logger.info("EventBus initialized")

        # 3. 初始化 AgentManager（在 Calculator 之前）
        self.agent_manager = AgentManager(
            event_bus=self.event_bus,
            llm_provider=self.llm_provider,
            template_dir=self.settings.data_dir / "default_agents",
            agent_dir=self.settings.data_dir / "agent" / f"telegram_{self.chat_id}",
            repository=self.repository,
            session_id=self.session_id,
        )

        # 初始化并启动默认 agents
        default_agents = ["governor_zhili", "minister_of_revenue"]
        for agent_id in default_agents:
            if self.agent_manager.initialize_agent(agent_id):
                self.agent_manager.add_agent(agent_id)
                logger.info(f"Agent {agent_id} started")

        logger.info(f"AgentManager initialized with {len(default_agents)} agents")

        # 4. 初始化 Calculator（传入 AgentManager）
        self.calculator = TurnCoordinator(self.event_bus, self.repository, self.agent_manager)
        self.calculator.start()
        logger.info("Calculator started")
        self._running = True

    async def shutdown(self) -> None:
        """关闭会话"""
        if not self._running:
            return

        logger.info(f"Shutting down session for chat_id={self.chat_id}")

        if self.agent_manager:
            self.agent_manager.stop_all()

        if self.calculator:
            self.calculator.stop()

        if self.session_context_manager:
            await self.session_context_manager.stop_cleanup_task()

        if self.repository:
            await close_database()

        self._running = False
        logger.info(f"Session {self.chat_id} shut down")

    async def _on_response(self, event: Event) -> None:
        """
        处理 Agent 响应 - 实时发送到 Telegram

        Args:
            event: 响应事件
        """
        if event.type != EventType.RESPONSE:
            return

        narrative = event.payload.get("narrative", "")
        agent_name = event.src.replace("agent:", "")

        logger.info(f"📨 Received response from {agent_name}: {narrative[:50]}...")

        # 重试配置
        max_retries = 3
        base_delay = 1.0  # 基础延迟时间（秒）

        for attempt in range(max_retries):
            try:
                await self.bot_application.bot.send_message(
                    chat_id=self.chat_id,
                    text=f"📜 <b>{agent_name}</b>:\n\n{narrative}",
                    parse_mode="HTML",
                )
                logger.info(f"✅ Sent response from {agent_name} to chat {self.chat_id}")
                return  # 成功发送，退出

            except Exception as e:
                if attempt < max_retries - 1:
                    # 计算指数退避延迟
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        f"⚠️  Failed to send response (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    # 最后一次尝试失败
                    logger.error(
                        f"❌ Failed to send response after {max_retries} attempts: {e}",
                        exc_info=True,
                    )
                    logger.error(f"Failed to send message to {self.chat_id}: {e}")

    async def _on_turn_resolved(self, event: Event) -> None:
        """
        处理回合结算完成事件 - 发送通知到 Telegram

        Args:
            event: turn_resolved 事件
        """
        if event.type != EventType.TURN_RESOLVED:
            return

        # 检查事件是否来自当前会话
        event_chat_id = event.payload.get("chat_id")
        if event_chat_id != self.chat_id:
            return

        turn = event.payload.get("turn", 0)

        # 重试配置
        max_retries = 3
        base_delay = 1.0  # 基础延迟时间（秒）

        for attempt in range(max_retries):
            try:
                await self.bot_application.bot.send_message(
                    chat_id=self.chat_id,
                    text=f"✅ <b>第 {turn} 回合结算完成</b>\n\n可以继续与官员交互或再次结束回合。",
                    parse_mode="HTML",
                )
                logger.info(
                    f"Sent turn resolved notification to chat {self.chat_id} for turn {turn}"
                )
                return  # 成功发送，退出

            except Exception as e:
                if attempt < max_retries - 1:
                    # 计算指数退避延迟
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        f"⚠️  Failed to send turn notification (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    # 最后一次尝试失败
                    logger.error(
                        f"Failed to send turn resolved message to {self.chat_id} after {max_retries} attempts: {e}"
                    )

    async def _initialize_game_state(self) -> None:
        """初始化游戏状态（如果数据库为空）"""
        # 检查是否已有数据
        state = await self.repository.load_state()

        if state.get("provinces"):
            logger.info("Game state already initialized")
            return

        # 创建初始游戏状态
        from simu_emperor.engine.models.base_data import (
            ProvinceBaseData,
            NationalBaseData,
            PopulationData,
            AgricultureData,
            CommerceData,
            TradeData,
            MilitaryData,
            TaxationData,
            ConsumptionData,
            AdministrationData,
            CropData,
            CropType,
        )
        from decimal import Decimal

        # 创建直隶省
        zhili = ProvinceBaseData(
            province_id="zhili",
            name="直隶",
            population=PopulationData(
                total=Decimal("2600000"),
                happiness=Decimal("0.7"),
                growth_rate=Decimal("0.002"),
                labor_ratio=Decimal("0.55"),
            ),
            agriculture=AgricultureData(
                irrigation_level=Decimal("0.3"),
                crops=[
                    CropData(
                        crop_type=CropType.WHEAT,
                        area_mu=Decimal("300000"),
                        yield_per_mu=Decimal("1.3"),
                    ),
                    CropData(
                        crop_type=CropType.RICE,
                        area_mu=Decimal("100000"),
                        yield_per_mu=Decimal("3"),
                    ),
                ],
            ),
            commerce=CommerceData(
                merchant_households=Decimal("150000"),
                market_prosperity=Decimal("0.7"),
            ),
            trade=TradeData(
                trade_volume=Decimal("500000"),
                trade_route_quality=Decimal("0.6"),
            ),
            military=MilitaryData(
                soldiers=Decimal("50000"),
                morale=Decimal("0.7"),
                garrison_size=Decimal("30000"),
                equipment_level=Decimal("0.5"),
                upkeep_per_soldier=Decimal("3"),
            ),
            taxation=TaxationData(
                land_tax_rate=Decimal("0.03"),
                commercial_tax_rate=Decimal("0.05"),
                tariff_rate=Decimal("0.1"),
            ),
            consumption=ConsumptionData(
                civilian_grain_per_capita=Decimal("3"),
                military_grain_per_soldier=Decimal("5"),
            ),
            administration=AdministrationData(
                official_count=Decimal("5000"),
                official_salary=Decimal("20"),
                infrastructure_value=Decimal("0.5"),
            ),
            granary_stock=Decimal("1200000"),
            local_treasury=Decimal("80000"),
        )

        # 创建初始国家数据
        initial_state = NationalBaseData(
            turn=0,
            provinces=[zhili],
            imperial_treasury=Decimal("100000"),
            national_tax_modifier=Decimal("1.0"),
            tribute_rate=Decimal("0.1"),
        )

        # 保存到数据库（使用 JSON 序列化模式）
        state_dict = initial_state.model_dump(mode="json")
        await self.repository.save_state(state_dict)

        logger.info(f"Initialized game state with {len(initial_state.provinces)} province(s)")

    async def get_session_id_for_event(self, event_category: str = "other") -> str:
        """
        根据事件类型返回对应的 session_id

        Args:
            event_category: 事件类别
                - "chat": CHAT/QUERY 事件，使用聊天会话
                - "command": COMMAND 事件，使用命令会话
                - "other": 其他事件，使用基础会话 ID

        Returns:
            session_id
        """
        if self.session_context_manager is None:
            # 回退到基础 session_id
            return self.session_id

        return await self.session_context_manager.get_session_for_event(event_category)


class SessionManager:
    """
    管理多个 Telegram 会话

    负责：
    - 创建和获取会话（懒加载）
    - 清理过期会话
    - 会话超时管理
    """

    def __init__(
        self, settings: GameConfig, bot_application: Application, llm_provider: LLMProvider
    ):
        """
        初始化会话管理器

        Args:
            settings: 游戏配置
            bot_application: Telegram Bot 应用实例
            llm_provider: LLM 提供商
        """
        self.settings = settings
        self.bot_application = bot_application
        self.llm_provider = llm_provider
        self._sessions: dict[int, GameSession] = {}
        self._last_access: dict[int, datetime] = {}
        self._cleanup_task: asyncio.Task | None = None

        logger.info("SessionManager initialized")

    async def get_session(self, chat_id: int) -> GameSession:
        """
        获取或创建会话（懒加载）

        Args:
            chat_id: Telegram 聊天 ID

        Returns:
            游戏会话实例
        """
        if chat_id not in self._sessions:
            # 检查会话数量限制
            if len(self._sessions) >= self.settings.telegram.max_sessions:
                # 清理最旧的会话
                oldest_chat_id = min(self._last_access, key=self._last_access.get)
                await self._sessions[oldest_chat_id].shutdown()
                del self._sessions[oldest_chat_id]
                del self._last_access[oldest_chat_id]
                logger.info(f"Removed oldest session {oldest_chat_id} due to limit")

            session = GameSession(chat_id, self.settings, self.bot_application, self.llm_provider)
            await session.start()
            self._sessions[chat_id] = session

            # 启动清理任务
            if self._cleanup_task is None:
                self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        self._last_access[chat_id] = datetime.now(timezone.utc)
        return self._sessions[chat_id]

    async def _cleanup_loop(self) -> None:
        """定期清理过期会话"""
        while True:
            try:
                await asyncio.sleep(3600)  # 每小时检查一次
                await self._cleanup_expired()
            except asyncio.CancelledError:
                logger.info("Cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup_expired(self) -> None:
        """清理过期会话"""
        timeout = timedelta(hours=self.settings.telegram.session_timeout_hours)
        now = datetime.now(timezone.utc)

        expired = [
            chat_id
            for chat_id, last_access in self._last_access.items()
            if now - last_access > timeout
        ]

        for chat_id in expired:
            await self._sessions[chat_id].shutdown()
            del self._sessions[chat_id]
            del self._last_access[chat_id]
            logger.info(f"Cleaned up expired session {chat_id}")

    async def shutdown_all(self) -> None:
        """关闭所有会话"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        for chat_id, session in self._sessions.items():
            await session.shutdown()

        self._sessions.clear()
        self._last_access.clear()
        logger.info("All sessions shut down")

    @property
    def active_count(self) -> int:
        """活跃会话数"""
        return len(self._sessions)
