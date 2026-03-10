"""
CLI 命令处理器

提供斜杠命令的处理函数。
"""

import logging
from typing import Any

from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType


logger = logging.getLogger(__name__)


class CommandHandler:
    """
    命令处理器

    处理各种斜杠命令。
    """

    def __init__(self, event_bus: EventBus, repository: Any):
        """
        初始化命令处理器

        Args:
            event_bus: 事件总线
            repository: 数据库仓储
        """
        self.event_bus = event_bus
        self.repository = repository

    async def handle_help(self, *args) -> None:
        """
        显示帮助信息

        Args:
            *args: 命令参数
        """
        help_text = """
=== 命令帮助 ===

斜杠命令:
  /help              显示此帮助
  /chat [agent_id]   进入对话模式
  /exit              退出对话模式
  /quit              退出游戏

自然语言:
  直接输入命令或问题，系统会自动解析意图

示例:
  调整直隶的税率到 10%
  查询人口统计
  /chat revenue_minister
  你好
  /exit
"""
        print(help_text)

    async def handle_chat(self, agent_id: str | None = None) -> None:
        """
        进入对话模式

        Args:
            agent_id: Agent ID
        """
        if agent_id is None:
            # TODO: 显示可用 Agent 列表
            print("可用 Agent: -")
            return

        logger.info(f"Entering chat mode with agent: {agent_id}")
        print(f"\n进入与 {agent_id} 的对话模式")
        print("输入 /exit 退出对话模式")

        # 返回 agent_id，供 CLI 设置状态
        return agent_id

    async def handle_exit(self) -> None:
        """退出对话模式"""
        logger.info("Exiting chat mode")
        print("\n退出对话模式")

    async def handle_quit(self) -> None:
        """退出游戏"""
        logger.info("Quitting game")
        print("\n再见！")
