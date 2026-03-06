"""
消息转换器

将 EventBus Event 转换为前端友好的 WSMessage 格式。
"""

from typing import Any
from datetime import datetime

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

    def convert(self, event: Event) -> dict[str, Any] | None:
        """
        转换 EventBus Event 为 WSMessage

        Args:
            event: EventBus 原始事件

        Returns:
            WSMessage 或 None（如果不支持的类型）

        WSMessage 格式:
        {
            "kind": "chat" | "state" | "event" | "error",
            "data": {...}
        }
        """
        if event.type == EventType.RESPONSE:
            return self._convert_response(event)
        elif event.type == EventType.TURN_RESOLVED:
            return self._convert_turn_resolved(event)
        elif event.type == EventType.CHAT:
            # Chat 消息也转换为 chat 类型（用户聊天）
            return self._convert_chat(event)
        # COMMAND 事件不广播（避免循环）
        return None

    def _convert_response(self, event: Event) -> dict[str, Any]:
        """转换 Agent 响应事件"""
        return {
            "kind": "chat",
            "data": {
                "agent": self._extract_agent_name(event.src),
                "agentDisplayName": self._get_agent_display_name(event.src),
                "text": event.payload.get("narrative", ""),
                "timestamp": event.timestamp or datetime.utcnow().isoformat() + "Z",
            }
        }

    def _convert_turn_resolved(self, event: Event) -> dict[str, Any]:
        """转换回合结算事件"""
        turn = event.payload.get("turn", 0)
        metrics = event.payload.get("metrics", {})

        # 从 metrics (NationalTurnMetrics) 中提取可用数据
        # NationalTurnMetrics 包含: turn, province_metrics, imperial_treasury_change, tribute_total

        # 从 province_metrics 聚合数据
        province_metrics = metrics.get("province_metrics", [])
        total_population = sum(p.get("population", {}).get("total", 0) for p in province_metrics)
        total_military = sum(p.get("military", {}).get("soldiers", 0) for p in province_metrics)

        # 计算平均幸福度
        avg_happiness = 0
        if province_metrics:
            total_happiness = sum(p.get("population", {}).get("happiness", 0) for p in province_metrics)
            avg_happiness = total_happiness / len(province_metrics)

        # 计算农业总产量
        total_food = 0
        for p in province_metrics:
            crops = p.get("agriculture", {}).get("crops", [])
            for crop in crops:
                area = crop.get("area_mu", 0)
                yield_per = crop.get("yield_per_mu", 0)
                total_food += area * yield_per

        # 农业状况描述
        agriculture = "正常"
        if total_food > 1000000:
            agriculture = "丰收"
        elif total_food < 500000:
            agriculture = "歉收"

        # 获取国库变动（这是实际可用的数据）
        treasury_change = metrics.get("imperial_treasury_change", 0)

        return {
            "kind": "state",
            "data": {
                "turn": turn,
                "treasury_change": treasury_change,  # 国库变动
                "population": total_population,
                "military": total_military,
                "happiness": round(avg_happiness, 2),
                "agriculture": agriculture,
                "corruption": 0,  # TODO: 计算贪腐指数
            }
        }

    def _convert_chat(self, event: Event) -> dict[str, Any]:
        """转换聊天消息（用户消息确认）"""
        return {
            "kind": "chat",
            "data": {
                "agent": "player",  # 用户消息
                "agentDisplayName": "皇帝",
                "text": event.payload.get("query", ""),
                "timestamp": event.timestamp or datetime.utcnow().isoformat() + "Z",
            }
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
