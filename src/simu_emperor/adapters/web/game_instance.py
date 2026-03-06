"""
游戏实例管理

Web 模式的游戏实例管理器（单例，全局共享）。
"""

import asyncio
import logging
from pathlib import Path

from simu_emperor.config import GameConfig
from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.event_bus.logger import FileEventLogger, DatabaseEventLogger
from simu_emperor.persistence import init_database, close_database
from simu_emperor.persistence.repositories import GameRepository
from simu_emperor.core.calculator import Calculator
from simu_emperor.agents.manager import AgentManager
from simu_emperor.llm.base import LLMProvider
from simu_emperor.llm.anthropic import AnthropicProvider
from simu_emperor.llm.openai import OpenAIProvider
from simu_emperor.llm.mock import MockProvider


logger = logging.getLogger(__name__)


class WebGameInstance:
    """
    Web 模式的游戏实例管理器

    单例模式，所有 WebSocket 连接共享同一个游戏实例。

    职责：
    - 单例模式（全局共享，不同于 telegram 的多会话）
    - 参考 telegram adapter 的 GameSession 初始化逻辑
    - 生命周期管理

    Attributes:
        settings: 游戏配置
        player_id: 玩家 ID（"player:web"）
        session_id: 会话 ID（"session:web:main"）
        db_path: 数据库路径
        event_bus: 事件总线
        repository: 数据库仓储
        calculator: 游戏状态管理器
        agent_manager: Agent 管理器
        llm_provider: LLM 提供商
        _running: 运行状态标志
    """

    def __init__(self, settings: GameConfig) -> None:
        """
        初始化游戏实例管理器

        Args:
            settings: 游戏配置
        """
        self.settings = settings
        self.player_id = "player:web"
        self.session_id = "session:web:main"

        # 数据库路径（共享，而非每个会话独立）
        self.db_path = str(settings.data_dir / "game.db")

        # 延迟初始化的组件
        self.event_bus: EventBus | None = None
        self.repository: GameRepository | None = None
        self.calculator: Calculator | None = None
        self.agent_manager: AgentManager | None = None
        self.llm_provider: LLMProvider | None = None
        self._running: bool = False

        logger.info("WebGameInstance created")

    def create_llm_provider(self) -> LLMProvider:
        """
        创建 LLM Provider（根据配置）

        Returns:
            LLM Provider 实例
        """
        config = self.settings.llm

        if config.provider == "anthropic":
            return AnthropicProvider(api_key=config.api_key)
        elif config.provider == "openai":
            return OpenAIProvider(
                api_key=config.api_key,
                api_base=config.api_base
            )
        else:  # mock
            return MockProvider()

    async def start(self) -> None:
        """
        启动游戏实例

        初始化顺序（参考 telegram adapter 的 GameSession.start()）：
        1. LLM Provider
        2. Database + Repository
        3. EventBus（带日志）
        4. AgentManager
        5. Calculator
        """
        if self._running:
            logger.warning("WebGameInstance already running")
            return

        logger.info("Starting WebGameInstance...")

        # 1. 初始化 LLM Provider
        self.llm_provider = self.create_llm_provider()
        logger.info(f"LLM provider initialized: {self.settings.llm.provider}")

        # 2. 初始化数据库
        conn = await init_database(self.db_path)
        self.repository = GameRepository(conn)
        logger.info(f"Database initialized: {self.db_path}")

        # 2.5. 初始化游戏状态（如果为空）
        await self._initialize_game_state()

        # 3. 初始化 EventBus（带日志）
        log_dir = self.settings.log_dir / "events"
        log_dir.mkdir(parents=True, exist_ok=True)

        file_logger = FileEventLogger(log_dir)
        db_logger = DatabaseEventLogger(conn)

        self.event_bus = EventBus(file_logger=file_logger, db_logger=db_logger)

        # 订阅响应事件
        self.event_bus.subscribe(self.player_id, self._on_response)
        # 订阅回合结算完成事件
        self.event_bus.subscribe(self.player_id, self._on_turn_resolved)

        logger.info("EventBus initialized")

        # 4. 初始化 AgentManager（在 Calculator 之前）
        agent_dir = self.settings.data_dir / "agent" / "web"
        agent_dir.mkdir(parents=True, exist_ok=True)

        self.agent_manager = AgentManager(
            event_bus=self.event_bus,
            llm_provider=self.llm_provider,
            template_dir=self.settings.data_dir / "default_agents",
            agent_dir=str(agent_dir),
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

        # 5. 初始化 Calculator（传入 AgentManager）
        self.calculator = Calculator(
            self.event_bus,
            self.repository,
            self.agent_manager
        )
        self.calculator.start()
        logger.info("Calculator started")

        self._running = True
        logger.info("WebGameInstance started successfully")

    async def shutdown(self) -> None:
        """关闭游戏实例"""
        if not self._running:
            return

        logger.info("Shutting down WebGameInstance...")

        if self.agent_manager:
            self.agent_manager.stop_all()

        if self.calculator:
            self.calculator.stop()

        if self.repository:
            await close_database(self.repository.conn)

        self._running = False
        logger.info("WebGameInstance shut down")

    async def _initialize_game_state(self) -> None:
        """
        初始化游戏状态（如果为空）

        检查数据库中是否有游戏状态，如果没有则创建初始状态。
        """
        if not self.repository:
            logger.warning("Repository not initialized, skipping game state initialization")
            return

        state = await self.repository.load_state()
        if state is None:
            logger.info("Game state is empty, initializing default state")
            # TODO: 创建默认游戏状态
            # 这里可以调用 engine 中的初始化逻辑
            pass
        else:
            logger.info(f"Game state loaded, turn={state.turn}")

    async def _on_response(self, event: Event) -> None:
        """
        处理 Agent 响应事件

        Args:
            event: 响应事件
        """
        if event.type != EventType.RESPONSE:
            return

        agent_name = event.src.replace("agent:", "")
        narrative = event.payload.get("narrative", "")

        logger.info(f"📨 Received response from {agent_name}: {narrative[:50]}...")
        # 注意：实际的 WebSocket 发送由 server.py 中的事件监听器处理

    async def _on_turn_resolved(self, event: Event) -> None:
        """
        回合结算事件处理器

        Args:
            event: 回合结算事件
        """
        turn = event.payload.get("turn")
        logger.info(f"🔄 Turn {turn} resolved")
        # 注意：实际的 WebSocket 发送由 server.py 中的事件监听器处理
