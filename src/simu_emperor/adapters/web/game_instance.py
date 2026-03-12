"""Web游戏实例管理器 (V4 - 应用层集成)

Web模式的游戏实例管理器（单例，全局共享）。
通过应用服务层委托业务逻辑，仅负责生命周期管理。

V4重构：移除所有业务逻辑，委托给ApplicationServices。
"""

import logging

from simu_emperor.config import GameConfig
from simu_emperor.application import ApplicationServices


logger = logging.getLogger(__name__)


class WebGameInstance:
    """Web模式游戏实例管理器

    职责（V4重构后）：
    - 单例模式（全局共享）
    - 应用服务层的生命周期容器
    - 依赖注入入口

    不再负责：
    - 游戏状态初始化（委托给GameService）
    - Session管理（委托给SessionService）
    - Agent管理（委托给AgentService）
    - 群聊管理（委托给GroupChatService）
    - Tape查询（委托给TapeService）
    - 消息处理（委托给MessageService）
    """

    def __init__(self, settings: GameConfig) -> None:
        """初始化Web游戏实例

        Args:
            settings: 游戏配置
        """
        self.settings = settings
        self.services: ApplicationServices | None = None
        self._running: bool = False

        logger.info("WebGameInstance created")

    async def start(self) -> None:
        """启动游戏实例

        初始化应用服务层。
        """
        if self._running:
            logger.warning("WebGameInstance already running")
            return

        logger.info("Starting WebGameInstance...")

        # 创建并初始化应用服务层
        self.services = await ApplicationServices.create(self.settings)
        await self.services.start()

        # 加载群聊数据
        await self.services.group_chat_service.load_from_storage()

        # 订阅响应事件
        if self.services.event_bus:
            self.services.event_bus.subscribe("player:web", self._on_response)

        self._running = True
        logger.info("WebGameInstance started successfully")

    async def shutdown(self) -> None:
        """关闭游戏实例

        关闭应用服务层。
        """
        if not self._running:
            return

        logger.info("Shutting down WebGameInstance...")

        # 保存群聊数据
        if self.services:
            await self.services.group_chat_service.save_to_storage()
            await self.services.shutdown()

        self._running = False
        logger.info("WebGameInstance shut down")

    async def _on_response(self, event) -> None:
        """处理响应事件（由WebSocket连接管理器实际发送）

        Args:
            event: 响应事件
        """
        # 实际发送逻辑在server.py的WebSocket处理中
        # 这里只是订阅点，响应通过connection_manager广播
        pass

    # 便捷属性：访问各服务

    @property
    def game_service(self):
        """获取游戏服务"""
        if self.services:
            return self.services.game_service
        return None

    @property
    def session_service(self):
        """获取会话服务"""
        if self.services:
            return self.services.session_service
        return None

    @property
    def agent_service(self):
        """获取Agent服务"""
        if self.services:
            return self.services.agent_service
        return None

    @property
    def group_chat_service(self):
        """获取群聊服务"""
        if self.services:
            return self.services.group_chat_service
        return None

    @property
    def message_service(self):
        """获取消息服务"""
        if self.services:
            return self.services.message_service
        return None

    @property
    def tape_service(self):
        """获取Tape服务"""
        if self.services:
            return self.services.tape_service
        return None

    @property
    def event_bus(self):
        """获取事件总线"""
        if self.services:
            return self.services.event_bus
        return None

    @property
    def repository(self):
        """获取仓储"""
        if self.services:
            return self.services.repository
        return None

    @property
    def agent_manager(self):
        """获取Agent管理器"""
        if self.services:
            return self.services.agent_manager
        return None

    @property
    def session_manager(self):
        """获取会话管理器"""
        if self.services:
            return self.services.session_manager
        return None

    @property
    def is_running(self) -> bool:
        """检查是否运行中"""
        return self._running
