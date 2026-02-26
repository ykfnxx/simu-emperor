"""
IntentParser - 自然语言意图解析器

使用 LLM 解析用户的自然语言输入。
"""

import logging
from typing import Any

from simu_emperor.llm.base import LLMProvider


logger = logging.getLogger(__name__)


class IntentParser:
    """
    意图解析器

    使用 LLM 解析用户输入，提取：
    - 目标 Agent
    - 意图类型
    - 动作
    - 参数
    """

    def __init__(self, llm_provider: LLMProvider):
        """
        初始化意图解析器

        Args:
            llm_provider: LLM 提供商
        """
        self.llm_provider = llm_provider

        # 系统提示词
        self.system_prompt = """你是一个意图解析器。你的任务是分析玩家的输入，提取结构化信息。

输入格式：
- 玩家可以用自然语言描述命令或问题
- 玩家可能指定某个官员（Agent）

输出格式（JSON）：
{
    "target_agent": "agent_id 或 null",
    "intent": "command/query/chat",
    "action": "具体动作",
    "params": {"key": "value"}
}

示例：
输入: "调整直隶的税率到 10%"
输出: {"target_agent": "revenue_minister", "intent": "command", "action": "adjust_tax", "params": {"province": "zhili", "rate": 0.1}}

输入: "查询人口统计"
输出: {"target_agent": null, "intent": "query", "action": "query_population", "params": {}}

输入: "你好"
输出: {"target_agent": null, "intent": "chat", "action": "greet", "params": {}}
"""

    async def parse(self, user_input: str, active_agents: list[str]) -> dict[str, Any]:
        """
        解析用户输入

        Args:
            user_input: 用户输入字符串
            active_agents: 活跃的 Agent ID 列表

        Returns:
            解析结果字典，包含 target_agent, intent, action, params
        """
        # 构建提示词
        active_agents_str = ", ".join(active_agents) if active_agents else "无"
        prompt = f"""活跃的官员列表: {active_agents_str}

玩家输入: {user_input}

请解析玩家的意图，返回 JSON 格式。"""

        try:
            # 调用 LLM
            response = await self.llm_provider.call(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.3,  # 使用较低的温度以获得更确定的结果
            )

            # 解析 JSON
            import json

            result = json.loads(response.strip())

            # 验证必需字段
            if "target_agent" not in result:
                result["target_agent"] = None
            if "intent" not in result:
                result["intent"] = "command"
            if "action" not in result:
                result["action"] = "unknown"
            if "params" not in result:
                result["params"] = {}

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            # 返回默认值
            return {
                "target_agent": None,
                "intent": "command",
                "action": "unknown",
                "params": {"raw_input": user_input},
            }
        except Exception as e:
            logger.error(f"Error parsing intent: {e}", exc_info=True)
            return {
                "target_agent": None,
                "intent": "command",
                "action": "unknown",
                "params": {"raw_input": user_input},
            }
