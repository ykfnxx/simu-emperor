"""
Telegram Bot 服务

负责：
- 初始化 Telegram Bot
- 注册命令处理器
- 启动轮询模式
- 处理传入消息
"""

import asyncio
import logging
from typing import Any, Callable, Awaitable

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import httpx

from simu_emperor.adapters.telegram.session import SessionManager


logger = logging.getLogger(__name__)


class TelegramBotService:
    """
    Telegram Bot 服务

    管理 Telegram Bot 的生命周期和消息路由。

    Attributes:
        token: Bot Token
        session_manager: 会话管理器
        application: Telegram Bot 应用实例
    """

    # 命令处理器映射
    _COMMAND_HANDLERS: dict[str, Callable[["TelegramBotService", Update, Any], Awaitable[None]]] = {}

    def __init__(self, token: str, session_manager: SessionManager, enabled_commands: list[str] | None = None):
        """
        初始化 Telegram Bot 服务

        Args:
            token: Bot Token
            session_manager: 会话管理器
            enabled_commands: 启用的命令列表（None 表示全部启用）
        """
        self.token = token
        self.session_manager = session_manager
        self.enabled_commands = set(enabled_commands) if enabled_commands else None
        self.application: Application | None = None

        logger.info(f"TelegramBotService initialized (commands: {self.enabled_commands or 'all'})")

    async def start_polling(self) -> None:
        """
        启动轮询模式

        初始化 Application 并注册消息处理器。
        """
        logger.info("🤖 [Bot] ========== Initializing Telegram Bot ==========")

        try:
            # 配置 httpx 客户端，增加超时时间以避免连接超时
            timeout = httpx.Timeout(
                connect=30.0,  # 连接超时 30 秒
                read=60.0,     # 读取超时 60 秒
                write=30.0,    # 写入超时 30 秒
                pool=10.0,     # 连接池超时 10 秒
            )
            # 创建自定义 httpx 客户端
            client = httpx.AsyncClient(timeout=timeout)

            self.application = (
                Application.builder()
                .token(self.token)
                .httpx_client(client)  # 使用自定义客户端
                .build()
            )
            logger.info("✅ [Bot] Application builder created with custom timeout")

        except Exception as e:
            logger.error(f"❌ [Bot] Failed to build application: {e}", exc_info=True)
            raise

        # 注册命令处理器（根据配置）
        self._register_commands()

        # 注册消息处理器（@agent, @all, /cmd）
        # 使用 group=1 确保命令处理器（group=0）优先执行
        # 在 handler 中手动过滤已注册的命令，但允许 /cmd 通过
        self.application.add_handler(MessageHandler(filters.TEXT, self._handle_message), group=1)
        logger.info("✅ [Bot] Message handler registered (group=1)")

        # 启动应用
        try:
            await self.application.initialize()
            logger.info("✅ [Bot] Application initialized")

            await self.application.start()
            logger.info("✅ [Bot] Application started")

            await self.application.updater.start_polling()
            logger.info("✅ [Bot] Polling started")

        except Exception as e:
            logger.error(f"❌ [Bot] Failed to start bot: {e}", exc_info=True)
            raise

        logger.info("🚀 [Bot] ========== Telegram Bot is now running ==========")

    def _register_commands(self) -> None:
        """根据配置注册命令处理器"""
        registered = []

        # 命令映射
        commands = {
            "start": self._cmd_start,
            "help": self._cmd_help,
            "agents": self._cmd_agents,
            "stat": self._cmd_stat,
            "end_turn": self._cmd_end_turn,
        }

        for cmd_name, handler in commands.items():
            # 检查是否启用此命令
            if self.enabled_commands is None or cmd_name in self.enabled_commands:
                # 使用 group=0 确保命令处理器优先于消息处理器
                self.application.add_handler(CommandHandler(cmd_name, handler), group=0)
                registered.append(cmd_name)
                logger.debug(f"Registered command: /{cmd_name}")
            else:
                logger.debug(f"Command disabled: /{cmd_name}")

        logger.info(f"✅ Registered {len(registered)} commands: {registered}")

    async def stop(self) -> None:
        """停止 Bot"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

            # 关闭自定义 httpx 客户端
            if hasattr(self.application, 'httpx_client') and self.application.httpx_client:
                await self.application.httpx_client.aclose()
                logger.info("HTTPX client closed")

            logger.info("Telegram Bot stopped")

    async def _cmd_start(self, update: Update, context: Any) -> None:
        """
        /start 命令处理器

        Args:
            update: Telegram 更新对象
            context: 上下文对象
        """
        chat_id = update.effective_chat.id
        logger.info(f"🎬 [Bot] ========== /start command triggered from chat_id={chat_id} ==========")

        try:
            await update.message.reply_text(
                "🏯 <b>欢迎来到皇帝模拟器！</b>\n\n"
                "你是一国之君，AI Agent 扮演你的官员。\n\n"
                "<b>常用命令：</b>\n"
                + self._get_enabled_commands_list()
                + "\n<b>聊天格式：</b>\n"
                "@agent_name 消息内容 - 与官员对话\n"
                "@all 消息内容 - 向所有官员广播\n"
                "/cmd @agent_name 命令 - 下达命令",
                parse_mode="HTML",
            )
            logger.info(f"✅ [Bot] Successfully replied to /start from chat_id={chat_id}")
        except Exception as e:
            logger.error(f"❌ [Bot] Error replying to /start: {e}", exc_info=True)

    async def _cmd_help(self, update: Update, context: Any) -> None:
        """
        /help 命令处理器

        Args:
            update: Telegram 更新对象
            context: 上下文对象
        """
        enabled = self._get_enabled_commands_list()

        help_text = f"""📖 <b>帮助文档</b>

{enabled}

<b>聊天格式：</b>
@agent_name 消息内容 - 与特定官员对话
@all 消息内容 - 向所有官员广播

<b>下达命令：</b>
/cmd @agent1 @agent2 命令描述 - 向多个官员下达命令

<b>示例：</b>
@governor_zhili 直隶省最近如何？
@all 各位卿家，局势如何？
/cmd @minister_of_revenue 提高税收
"""
        await update.message.reply_text(help_text, parse_mode="HTML")

    async def _cmd_agents(self, update: Update, context: Any) -> None:
        """
        /agents 命令处理器

        列出所有活跃的 Agent。

        Args:
            update: Telegram 更新对象
            context: 上下文对象
        """
        chat_id = update.effective_chat.id
        session = await self.session_manager.get_session(chat_id)

        if not session.agent_manager:
            await update.message.reply_text("❌ 会话未初始化")
            return

        active_agents = list(session.agent_manager._active_agents.keys())
        if not active_agents:
            await update.message.reply_text("当前没有活跃的官员")
        else:
            agents_list = "\n".join(f"• {agent_id}" for agent_id in active_agents)
            await update.message.reply_text(f"👥 <b>活跃官员：</b>\n\n{agents_list}", parse_mode="HTML")

    async def _cmd_stat(self, update: Update, context: Any) -> None:
        """
        /stat 命令处理器

        查看游戏状态。

        Args:
            update: Telegram 更新对象
            context: 上下文对象
        """
        chat_id = update.effective_chat.id
        session = await self.session_manager.get_session(chat_id)

        if not session.repository:
            await update.message.reply_text("❌ 会话未初始化")
            return

        try:
            state_dict = await session.repository.load_state()
            turn = state_dict.get("turn", 0)
            provinces_list = state_dict.get("provinces", [])
            treasury = state_dict.get("imperial_treasury", 0)

            stat_text = f"""📊 <b>游戏状态</b>

<b>回合：</b> {turn}
<b>省份数：</b> {len(provinces_list) if isinstance(provinces_list, list) else 0}
<b>国库：</b> {float(treasury):.2f} 两

输入 /stat all 查看详细信息
"""
            await update.message.reply_text(stat_text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error loading game state: {e}", exc_info=True)
            await update.message.reply_text("❌ 加载游戏状态失败")

    async def _cmd_end_turn(self, update: Update, context: Any) -> None:
        """
        /end_turn 命令处理器

        结束当前回合。

        Args:
            update: Telegram 更新对象
            context: 上下文对象
        """
        chat_id = update.effective_chat.id
        session = await self.session_manager.get_session(chat_id)

        if not session.event_bus:
            await update.message.reply_text("❌ 会话未初始化")
            return

        from simu_emperor.event_bus.event import Event
        from simu_emperor.event_bus.event_types import EventType

        event = Event(
            src=session.player_id,
            dst=["*"],
            type=EventType.END_TURN,
            payload={"chat_id": chat_id},
            session_id=session.session_id,  # ✅ 添加 session_id
            parent_event_id=None,           # ✅ 根事件
            root_event_id="",                # ✅ EventBus 自动设置
        )

        await session.event_bus.send_event(event)
        await update.message.reply_text("⏳ 回合结束中，请稍候...")
        logger.info(f"User {chat_id} ended turn")

    async def _handle_message(self, update: Update, context: Any) -> None:
        """
        处理所有消息

        路由消息到对应的处理器。跳过已注册的命令。

        Args:
            update: Telegram 更新对象
            context: 上下文对象
        """
        chat_id = update.effective_chat.id
        text = update.message.text

        if not text:
            return

        # 检查是否是已注册的命令
        import re
        if re.match(r'^/(start|help|agents|stat|end_turn)(\s+|$)', text):
            logger.debug(f"⏭️  [Bot] MessageHandler skipping registered command: {text}")
            return

        logger.info(f"📨 [Bot] MessageHandler processing: {text[:80]}")

        # 获取会话
        logger.debug(f"🔍 [Bot] Getting session for chat_id={chat_id}")
        session = await self.session_manager.get_session(chat_id)

        # 路由消息
        from simu_emperor.adapters.telegram.router import MessageRouter

        logger.debug("🔀 [Bot] Routing message to MessageRouter")
        router = MessageRouter(session)
        await router.route_and_send(text, chat_id, update.message.reply_text)

    def _get_enabled_commands_list(self) -> str:
        """获取启用的命令列表（格式化）"""
        # 命令描述
        command_descriptions = {
            "start": "开始游戏",
            "help": "查看帮助",
            "agents": "列出所有官员",
            "stat": "查看游戏状态",
            "end_turn": "结束回合",
        }

        # 获取启用的命令
        if self.enabled_commands is None:
            enabled_cmds = list(command_descriptions.keys())
        else:
            enabled_cmds = [cmd for cmd in self.enabled_commands if cmd in command_descriptions]

        # 格式化输出
        lines = [f"/{cmd} - {command_descriptions[cmd]}" for cmd in enabled_cmds]
        return "\n".join(lines)
