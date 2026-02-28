"""
消息路由器

负责解析用户输入并转换为 EventBus 事件。
"""

import logging
import re
import uuid
from typing import Any, Callable, Awaitable

from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.adapters.telegram.session import GameSession


logger = logging.getLogger(__name__)


class MessageRouter:
    """
    消息路由器

    解析用户输入的消息并发送到 EventBus。

    支持的格式：
    - @agent_name 消息内容 - 聊天
    - @all 消息内容 - 广播
    - /cmd @agent1 @agent2 命令 - 命令
    """

    def __init__(self, session: GameSession):
        """
        初始化消息路由器

        Args:
            session: 游戏会话
        """
        self.session = session
        logger.info("MessageRouter initialized")

    async def route_and_send(
        self,
        text: str,
        chat_id: int,
        reply_func: Callable[[str], Awaitable[Any]],
    ) -> None:
        """
        解析消息并发送事件

        Args:
            text: 消息文本
            chat_id: Telegram 聊天 ID
            reply_func: 回复函数
        """
        # 生成唯一的请求ID用于追踪
        request_id = str(uuid.uuid4())[:8]

        if not self.session.event_bus:
            await reply_func("❌ 会话未初始化")
            return

        logger.info(f"🔀 [Router:{request_id}] Routing message: {text[:80]}")

        # 1. 解析 @agent 或 @all
        mentions, message = self._parse_mentions(text)
        logger.info(f"🔍 [Router:{request_id}] Parsed mentions: {mentions}, message: {message[:80] if message else 'None'}")

        if not mentions and not message:
            await reply_func("❌ 格式错误。使用 /help 查看帮助。")
            return

        # 2. 检测命令类型
        if text.strip().startswith("/cmd "):
            # /cmd @agent1 @agent2 command
            intent, payload = self._parse_command(text)
            targets = [f"agent:{agent}" for agent in mentions] if mentions != ["all"] else ["*"]
            event_type = EventType.COMMAND
            logger.info(f"📋 [Router:{request_id}] Detected COMMAND event, targets: {targets}")
        elif mentions:
            # @agent message 或 @all message
            intent, payload = self._parse_chat(text)
            targets = [f"agent:{agent}" for agent in mentions] if mentions != ["all"] else ["*"]
            event_type = EventType.CHAT
            logger.info(f"💬 [Router:{request_id}] Detected CHAT event, targets: {targets}")
        else:
            # 没有提及任何 agent
            await reply_func("❌ 请使用 @agent_name 或 @all 来发送消息。使用 /help 查看帮助。")
            return

        # 3. 发送事件
        payload_with_tracking = {**payload, "chat_id": chat_id, "_request_id": request_id}
        event = Event(
            src=self.session.player_id,
            dst=targets,
            type=event_type,
            payload=payload_with_tracking,
        )

        logger.info(f"📤 [Router:{request_id}] Sending {event_type} event to EventBus: src={self.session.player_id}, dst={targets}")
        await self.session.event_bus.send_event(event)
        logger.info(f"✅ [Router:{request_id}] Event sent successfully")

        # 4. 确认发送
        target_display = ", ".join(mentions) if mentions != ["all"] else "所有官员"
        await reply_func(f"✅ 消息已发送给: {target_display}")

    def _parse_mentions(self, text: str) -> tuple[list[str], str]:
        """
        解析 @mentions

        Args:
            text: 消息文本

        Returns:
            (mentions列表, 去除mentions后的消息)
        """
        # 匹配 @word 格式
        mentions = re.findall(r"@(\w+)", text)
        # 移除所有 @mentions
        message = re.sub(r"@\w+\s*", "", text).strip()
        return mentions, message

    def _parse_command(self, text: str) -> tuple[str, dict[str, Any]]:
        """
        解析命令格式

        格式: /cmd @agent1 @agent2 命令描述

        Args:
            text: 消息文本

        Returns:
            (intent, payload)
        """
        # 移除 /cmd
        text = text[5:].strip()

        # 解析 mentions 和 命令
        mentions, command = self._parse_mentions(text)

        return "command", {
            "intent": "execute_command",
            "command": command,
            "agents": mentions,
        }

    def _parse_chat(self, text: str) -> tuple[str, dict[str, Any]]:
        """
        解析聊天格式

        格式: @agent 消息内容 或 @all 消息内容

        Args:
            text: 消息文本

        Returns:
            (intent, payload)
        """
        mentions, message = self._parse_mentions(text)

        return "chat", {
            "intent": "chat",
            "message": message,
            "agents": mentions,
        }
