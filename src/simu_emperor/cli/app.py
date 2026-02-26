"""
EmperorCLI - 命令行界面主类
"""

import asyncio
import logging
from typing import Any

from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType


logger = logging.getLogger(__name__)


class EmperorCLI:
    """
    皇帝模拟器 CLI

    基于 Rich/TUI 的玩家交互界面。

    Attributes:
        event_bus: 事件总线
        repository: 数据库仓储
        _running: 是否运行中
        _chat_mode: 是否在对话模式
        _chat_agent_id: 当前对话的 Agent ID
    """

    def __init__(self, event_bus: EventBus, repository: Any):
        """
        初始化 CLI

        Args:
            event_bus: 事件总线
            repository: 数据库仓储
        """
        self.event_bus = event_bus
        self.repository = repository
        self._running = False
        self._chat_mode = False
        self._chat_agent_id = ""

        # 订阅响应事件
        self.event_bus.subscribe("player", self._on_response)

        logger.info("EmperorCLI initialized")

    async def run(self) -> None:
        """
        运行 CLI 主循环

        - 显示游戏状态
        - 获取用户输入
        - 处理命令/自然语言
        """
        self._running = True

        logger.info("EmperorCLI started")

        try:
            while self._running:
                # 显示状态
                self._display_status()

                # 获取输入
                user_input = await self._get_input()

                if not user_input:
                    continue

                # 处理输入
                await self._handle_input(user_input)

        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt, shutting down...")
        finally:
            self._running = False
            logger.info("EmperorCLI stopped")

    def _display_status(self) -> None:
        """
        显示游戏状态

        显示：
        - 当前回合
        - 人口统计
        - 财政状况
        - 幸福度
        """
        # TODO: 实现状态显示
        # 需要等待 persistence 模块完成
        print("\n=== 皇帝模拟器 V2 ===")
        print("回合: 1")
        print("人口: -")
        print("国库: -")
        print("幸福度: -")

        if self._chat_mode:
            print(f"\n[对话模式] 与 {self._chat_agent_id} 对话中")

    async def _get_input(self) -> str:
        """
        获取用户输入

        Returns:
            用户输入字符串
        """
        try:
            return await asyncio.to_thread(input, "\n> ")
        except EOFError:
            return "/quit"

    async def _handle_input(self, user_input: str) -> None:
        """
        处理用户输入

        Args:
            user_input: 用户输入字符串
        """
        user_input = user_input.strip()

        if not user_input:
            return

        # 处理斜杠命令
        if user_input.startswith("/"):
            await self._handle_command(user_input)
        else:
            # 处理自然语言
            await self._handle_natural_language(user_input)

    async def _handle_command(self, cmd: str) -> None:
        """
        处理斜杠命令

        Args:
            cmd: 命令字符串
        """
        parts = cmd.split()
        command = parts[0].lower()

        if command == "/help":
            self._show_help()
        elif command == "/chat":
            await self._enter_chat_mode(parts[1] if len(parts) > 1 else None)
        elif command == "/exit":
            self._exit_chat_mode()
        elif command == "/end_turn":
            await self._end_turn()
        elif command == "/quit":
            self._running = False
        else:
            print(f"未知命令: {command}")
            print("输入 /help 查看帮助")

    async def _handle_natural_language(self, user_input: str) -> None:
        """
        处理自然语言输入

        Args:
            user_input: 自然语言字符串
        """
        # TODO: 实现意图解析
        # 需要等待 LLM 集成

        if self._chat_mode:
            # 对话模式：发送 chat 事件
            event = Event(
                src="player",
                dst=[f"agent:{self._chat_agent_id}"],
                type=EventType.CHAT,
                payload={"message": user_input},
            )
            await self.event_bus.send_event(event)
        else:
            # 命令模式：解析意图
            print(f"解析意图: {user_input}")
            # TODO: 调用 IntentParser

    async def _enter_chat_mode(self, agent_id: str | None = None) -> None:
        """
        进入对话模式

        Args:
            agent_id: Agent ID，如果为 None 则显示可用 Agent
        """
        if agent_id is None:
            # TODO: 显示可用 Agent 列表
            print("可用 Agent: -")
            return

        self._chat_mode = True
        self._chat_agent_id = agent_id
        print(f"\n进入与 {agent_id} 的对话模式")
        print("输入 /exit 退出对话模式")

    def _exit_chat_mode(self) -> None:
        """退出对话模式"""
        if self._chat_mode:
            print(f"\n退出与 {self._chat_agent_id} 的对话")
            self._chat_mode = False
            self._chat_agent_id = ""

    async def _end_turn(self) -> None:
        """结束回合"""
        print("\n结束回合...")

        # 发送 end_turn 事件
        event = Event(
            src="player",
            dst=["*"],
            type=EventType.END_TURN,
            payload={},
        )
        await self.event_bus.send_event(event)

    def _show_help(self) -> None:
        """显示帮助信息"""
        help_text = """
=== 命令帮助 ===

斜杠命令:
  /help              显示此帮助
  /chat [agent_id]   进入对话模式
  /exit              退出对话模式
  /end_turn          结束当前回合
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

    async def _on_response(self, event: Event) -> None:
        """
        处理 Agent 响应事件

        Args:
            event: response 事件
        """
        if event.type != EventType.RESPONSE:
            return

        # 显示响应
        narrative = event.payload.get("narrative", "")
        print(f"\n{event.src}: {narrative}")

    def _get_agent_display_name(self, agent_id: str) -> str:
        """
        获取 Agent 显示名称

        Args:
            agent_id: Agent ID

        Returns:
            显示名称
        """
        # TODO: 从 soul.md 读取显示名称
        return agent_id.replace("_", " ").title()
