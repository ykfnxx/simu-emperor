"""
EmperorCLI - 命令行界面主类
"""

import asyncio
import logging
from typing import Any
from asyncio import Queue

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

    def __init__(self, event_bus: EventBus, repository: Any, agent_manager: Any = None, session_id: str = "session:cli:default"):
        """
        初始化 CLI

        Args:
            event_bus: 事件总线
            repository: 数据库仓储
            agent_manager: Agent 管理器（可选）
            session_id: 会话标识符
        """
        self.event_bus = event_bus
        self.repository = repository
        self.agent_manager = agent_manager
        self.session_id = session_id
        self._running = False
        self._chat_mode = False
        self._chat_agent_id = ""
        self._response_queue: Queue = Queue()

        # 订阅响应事件
        self.event_bus.subscribe("player", self._on_response)

        logger.info("EmperorCLI initialized")

    async def run(self) -> None:
        """
        运行 CLI 主循环

        - 显示游戏状态
        - 处理队列中的响应
        - 获取用户输入
        - 处理命令/自然语言
        """
        self._running = True

        logger.info("EmperorCLI started")

        # 启动后台任务处理响应
        response_task = asyncio.create_task(self._response_loop())

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
            # 停止后台任务
            response_task.cancel()
            try:
                await response_task
            except asyncio.CancelledError:
                pass
            self._running = False
            logger.info("EmperorCLI stopped")

    async def _response_loop(self) -> None:
        """
        后台循环：持续处理响应队列

        这个任务在后台运行，不断检查并显示 Agent 的响应。
        """
        while self._running:
            try:
                # 等待响应（带超时，以便可以定期检查 _running 标志）
                event = await asyncio.wait_for(
                    self._response_queue.get(),
                    timeout=0.5
                )

                narrative = event.payload.get("narrative", "")
                print(f"\n{event.src}: {narrative}\n")
            except asyncio.TimeoutError:
                # 超时是正常的，继续下一次循环
                continue
            except asyncio.CancelledError:
                # 任务被取消，退出循环
                break

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
                session_id=self.session_id,
                parent_event_id=None,  # 根事件
                root_event_id="",  # EventBus 自动设置
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
            # 显示可用 Agent 列表
            if self.agent_manager:
                active_agents = self.agent_manager.get_active_agents()
                if active_agents:
                    print("\n=== 可用的 Agent ===")
                    for aid in active_agents:
                        display_name = self._get_agent_display_name(aid)
                        print(f"  - {aid}: {display_name}")
                    print("\n使用方法: /chat <agent_id>")
                    print("例如: /chat governor_zhili")
                else:
                    print("\n当前没有活跃的 Agent")
            else:
                print("\nAgentManager 未初始化")
            return

        # 验证 agent 是否存在
        if self.agent_manager and agent_id not in self.agent_manager.get_active_agents():
            print(f"\n错误: Agent '{agent_id}' 不存在或未激活")
            print("使用 /chat 查看可用的 Agent")
            return

        self._chat_mode = True
        self._chat_agent_id = agent_id
        display_name = self._get_agent_display_name(agent_id)
        print(f"\n=== 进入与 {display_name} ({agent_id}) 的对话模式 ===")
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
            session_id=self.session_id,
            parent_event_id=None,  # 根事件
            root_event_id="",  # EventBus 自动设置
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

        # 将响应放入队列，由主循环显示
        await self._response_queue.put(event)

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
