"""
Agent 基类 - 文件驱动的 AI 官员
"""

import logging
from pathlib import Path
from typing import Any

from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.llm.base import LLMProvider


logger = logging.getLogger(__name__)


class Agent:
    """
    AI 官员 Agent

    文件驱动的被动 Agent：
    - 只响应事件，不主动发起
    - personality 和权限由文件定义（soul.md, data_scope.yaml）
    - 三个工作流：summarize → respond → execute
    - 使用 LLM 生成响应

    Attributes:
        agent_id: Agent 唯一标识符
        event_bus: 事件总线
        llm_provider: LLM 提供商
        data_dir: 数据目录
    """

    def __init__(
        self,
        agent_id: str,
        event_bus: EventBus,
        llm_provider: LLMProvider,
        data_dir: str | Path,
    ):
        """
        初始化 Agent

        Args:
            agent_id: Agent 唯一标识符
            event_bus: 事件总线
            llm_provider: LLM 提供商
            data_dir: 数据目录（包含 soul.md 和 data_scope.yaml）
        """
        self.agent_id = agent_id
        self.event_bus = event_bus
        self.llm_provider = llm_provider
        self.data_dir = Path(data_dir)

        # 加载 soul 和 data_scope
        self._soul: str | None = None
        self._data_scope: dict[str, Any] | None = None
        self._load_soul()
        self._load_data_scope()

        logger.info(f"Agent {agent_id} initialized")

    def start(self) -> None:
        """
        启动 Agent

        订阅相关事件：
        - command: 玩家命令
        - query: 玩家查询
        - chat: 玩家对话
        - agent_message: Agent 间消息
        - turn_resolved: 回合结算完成
        """
        # 订阅发往此 Agent 的事件
        self.event_bus.subscribe(f"agent:{self.agent_id}", self._on_event)
        self.event_bus.subscribe("agent:*", self._on_event)

        logger.info(f"Agent {self.agent_id} started")

    def stop(self) -> None:
        """停止 Agent"""
        # 取消订阅
        self.event_bus.unsubscribe(f"agent:{self.agent_id}", self._on_event)
        self.event_bus.unsubscribe("agent:*", self._on_event)

        logger.info(f"Agent {self.agent_id} stopped")

    async def _on_event(self, event: Event) -> None:
        """
        事件分发器

        根据事件类型调用相应的处理方法。

        Args:
            event: 事件对象
        """
        # 过滤不是发往此 Agent 的事件
        if f"agent:{self.agent_id}" not in event.dst and "agent:*" not in event.dst:
            return

        # 根据事件类型分发
        if event.type == EventType.COMMAND:
            await self._handle_command(event)
        elif event.type == EventType.QUERY:
            await self._handle_query(event)
        elif event.type == EventType.CHAT:
            await self._handle_chat(event)
        elif event.type == EventType.AGENT_MESSAGE:
            await self._handle_agent_message(event)
        elif event.type == EventType.END_TURN:
            await self._handle_end_turn(event)
        elif event.type == EventType.TURN_RESOLVED:
            await self._handle_turn_resolved(event)

    async def _handle_command(self, event: Event) -> None:
        """
        处理命令事件

        Args:
            event: command 事件
        """
        logger.info(f"Agent {self.agent_id} received command: {event.payload}")

        # TODO: 实现 command 处理逻辑
        # 1. 构建上下文（使用 context_builder）
        # 2. 调用 LLM
        # 3. 解析响应（使用 response_parser）
        # 4. 执行动作
        # 5. 写 workspace 文件
        # 6. 发送响应事件

    async def _handle_query(self, event: Event) -> None:
        """
        处理查询事件

        Args:
            event: query 事件
        """
        logger.info(f"Agent {self.agent_id} received query: {event.payload}")

        # TODO: 实现 query 处理逻辑

    async def _handle_chat(self, event: Event) -> None:
        """
        处理对话事件

        Args:
            event: chat 事件
        """
        logger.info(f"Agent {self.agent_id} received chat: {event.payload}")

        # TODO: 实现 chat 处理逻辑

    async def _handle_agent_message(self, event: Event) -> None:
        """
        处理 Agent 间消息

        Args:
            event: agent_message 事件
        """
        logger.info(f"Agent {self.agent_id} received agent message: {event.payload}")

        # TODO: 实现 agent_message 处理逻辑

    async def _handle_end_turn(self, event: Event) -> None:
        """
        处理回合结束事件

        发送 ready 信号给 Calculator。

        Args:
            event: end_turn 事件
        """
        logger.info(f"Agent {self.agent_id} received end_turn")

        # 发送 ready 事件
        ready_event = Event(
            src=f"agent:{self.agent_id}",
            dst=["system:calculator"],
            type=EventType.READY,
            payload={},
        )
        await self.event_bus.send_event(ready_event)

    async def _handle_turn_resolved(self, event: Event) -> None:
        """
        处理回合结算完成事件

        写总结到 memory。

        Args:
            event: turn_resolved 事件
        """
        turn = event.payload.get("turn", 0)
        logger.info(f"Agent {self.agent_id} received turn_resolved: turn {turn}")

        # TODO: 实现 memory 写入逻辑
        # 1. 调用 LLM 生成本回合总结
        # 2. 写入 memory/summary.md 和 memory/recent/turn_{turn}.md

    def _load_soul(self) -> None:
        """
        加载 soul.md

        soul.md 定义 Agent 的 personality、behavior 等。
        """
        soul_path = self.data_dir / "soul.md"

        if soul_path.exists():
            with open(soul_path, "r", encoding="utf-8") as f:
                self._soul = f.read()
            logger.info(f"Agent {self.agent_id} loaded soul from {soul_path}")
        else:
            logger.warning(f"Soul file not found: {soul_path}")
            self._soul = "# Default Soul\nYou are a loyal official."

    def _load_data_scope(self) -> None:
        """
        加载 data_scope.yaml

        data_scope.yaml 定义 Agent 的数据访问权限。
        """
        import yaml

        scope_path = self.data_dir / "data_scope.yaml"

        if scope_path.exists():
            with open(scope_path, "r", encoding="utf-8") as f:
                self._data_scope = yaml.safe_load(f)
            logger.info(f"Agent {self.agent_id} loaded data_scope from {scope_path}")
        else:
            logger.warning(f"Data scope file not found: {scope_path}")
            self._data_scope = {}

    async def _call_llm(
        self, prompt: str, system_prompt: str | None = None, temperature: float = 0.7
    ) -> str:
        """
        调用 LLM 生成响应

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（使用 soul 作为默认值）
            temperature: 温度参数

        Returns:
            LLM 响应文本
        """
        if system_prompt is None:
            system_prompt = self._soul or "You are a helpful assistant."

        response = await self.llm_provider.call(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )

        return response
