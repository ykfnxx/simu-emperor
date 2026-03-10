"""
消息转换器

将 EventBus Event 转换为前端友好的 WSMessage 格式。
"""

from typing import Any
from datetime import datetime, timezone

from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType


class MessageConverter:
    """
    EventBus Event 到 WSMessage 的转换器

    职责：
    - 隐藏 EventBus 实现细节
    - 提供类型安全的消息格式
    - 支持多种消息类型（chat, state, event, error）
    """

    def __init__(self, repository=None):
        """
        初始化消息转换器

        Args:
            repository: Repository实例，用于获取GameState数据（如imperial_treasury）
        """
        self._repository = repository

    async def convert(self, event: Event) -> dict[str, Any] | None:
        """
        转换 EventBus Event 为 WSMessage

        Args:
            event: EventBus 原始事件

        Returns:
            WSMessage 或 None（如果不支持的类型）

        WSMessage 格式:
        {
            "kind": "chat" | "state" | "event" | "error" | "session_state",
            "data": {...}
        }
        """
        if event.type == EventType.SESSION_STATE:
            return self._convert_session_state(event)

        if event.type == EventType.RESPONSE:
            return self._convert_response(event)
        elif event.type == EventType.CHAT:
            return self._convert_chat(event)
        return None

    def _convert_response(self, event: Event) -> dict[str, Any]:
        """转换 Agent 响应事件"""
        return {
            "kind": "chat",
            "data": {
                "agent": self._extract_agent_name(event.src),
                "agentDisplayName": self._get_agent_display_name(event.src),
                "text": event.payload.get("narrative", ""),
                "timestamp": event.timestamp or datetime.now(timezone.utc).isoformat(),
                "session_id": event.session_id,
            },
        }

    def _convert_chat(self, event: Event) -> dict[str, Any]:
        """转换聊天消息（用户消息确认）"""
        return {
            "kind": "chat",
            "data": {
                "agent": "player",  # 用户消息
                "agentDisplayName": "皇帝",
                "text": event.payload.get("message", ""),
                "timestamp": event.timestamp or datetime.now(timezone.utc).isoformat(),
                "session_id": event.session_id,
            },
        }

    def _convert_session_state(self, event: Event) -> dict[str, Any]:
        """转换session状态更新事件"""
        payload = event.payload
        return {
            "kind": "session_state",
            "data": {
                "session_id": payload.get("session_id", event.session_id),
                "agent_id": payload.get("agent_id", ""),
                "event_count": payload.get("event_count", 0),
                "last_update": payload.get("last_update", datetime.now(timezone.utc).isoformat()),
            },
        }

    @staticmethod
    def _extract_agent_name(src: str) -> str:
        """
        从 event.src 提取 agent 名称

        Args:
            src: 事件源 ID（如 "agent:governor_zhili"）

        Returns:
            Agent 名称（如 "governor_zhili"）

        Examples:
            >>> MessageConverter._extract_agent_name("agent:governor_zhili")
            "governor_zhili"
            >>> MessageConverter._extract_agent_name("player:web")
            "player:web"
        """
        return src.replace("agent:", "")

    @staticmethod
    def _get_agent_display_name(src: str) -> str:
        """
        获取 agent 显示名称

        Args:
            src: 事件源 ID

        Returns:
            Agent 显示名称（中文名）

        Examples:
            >>> MessageConverter._get_agent_display_name("agent:governor_zhili")
            "直隶巡抚"
        """
        agent_name = MessageConverter._extract_agent_name(src)

        # Agent ID 到显示名称的映射
        display_names = {
            "governor_zhili": "直隶巡抚",
            "minister_of_revenue": "户部尚书",
            "player:web": "皇帝",
        }

        return display_names.get(agent_name, agent_name)

    @staticmethod
    def _describe_agriculture(metrics: dict) -> str:
        """
        描述农业产量

        Args:
            metrics: 回合指标字典

        Returns:
            农业产量描述（如 "丰收", "正常", "歉收"）
        """
        # TODO: 根据实际农业数据计算
        total_food = metrics.get("total_food_production", 0)
        if total_food > 1000000:
            return "丰收"
        elif total_food > 500000:
            return "正常"
        else:
            return "歉收"
