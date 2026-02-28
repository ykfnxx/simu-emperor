"""
响应收集器

注意：响应处理已集成到 GameSession._on_response() 方法中。
此模块保留用于未来的扩展功能。
"""

import logging

from telegram.ext import Application

from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.adapters.telegram.session import GameSession


logger = logging.getLogger(__name__)


class ResponseCollector:
    """
    响应收集器

    收集 Agent 响应并发送到 Telegram。

    注意：当前实现中，响应处理直接在 GameSession 中完成。
    此类保留用于未来扩展（如响应聚合、格式化等）。
    """

    def __init__(self, session: GameSession, bot: Application):
        """
        初始化响应收集器

        Args:
            session: 游戏会话
            bot: Telegram Bot 应用实例
        """
        self.session = session
        self.bot = bot
        logger.info("ResponseCollector initialized")

    async def on_response(self, event: Event) -> None:
        """
        处理 Agent 响应

        Args:
            event: 响应事件
        """
        if event.type != EventType.RESPONSE:
            return

        narrative = event.payload.get("narrative", "")
        agent_name = event.src.replace("agent:", "")

        try:
            await self.bot.bot.send_message(
                chat_id=self.session.chat_id,
                text=f"📜 **{agent_name}**:\n\n{narrative}",
                parse_mode="Markdown",
            )
            logger.info(f"Sent response from {agent_name} to chat {self.session.chat_id}")
        except Exception as e:
            logger.error(f"Failed to send message to {self.session.chat_id}: {e}")
