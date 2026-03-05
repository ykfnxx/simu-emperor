"""
Mock LLM 提供商（用于测试）
"""

import json
import re
from typing import Any

from simu_emperor.llm.base import LLMProvider


class MockProvider(LLMProvider):
    """
    Mock LLM 提供商

    返回预定义的响应，用于测试。

    如果没有设置 tool_calls，会根据事件类型智能生成合适的 tool calls。
    """

    def __init__(self, response: str = "臣遵旨！", tool_calls: list[dict] | None = None):
        """
        初始化 Mock 提供商

        Args:
            response: 预定义的响应文本
            tool_calls: 预定义的 tool calls（可选，如果为 None 则智能生成）
        """
        self.response = response
        self.tool_calls = tool_calls  # None 表示智能生成，[] 表示不生成
        self.call_count = 0

    async def call(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """
        模拟 LLM 调用

        Args:
            prompt: 用户提示词（忽略）
            system_prompt: 系统提示词（忽略）
            temperature: 温度参数（忽略）
            max_tokens: 最大 token 数（忽略）

        Returns:
            预定义的响应文本
        """
        self.call_count += 1
        return self.response

    async def call_with_functions(
        self,
        prompt: str | None = None,
        functions: list[dict] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        messages: list[dict] | None = None,
    ) -> dict[str, Any]:
        """
        模拟 LLM 调用（支持 function calling）

        Args:
            prompt: 用户提示词（如果提供了messages，此参数会被忽略）
            functions: 可用函数列表
            system_prompt: 系统提示词（可选）
            temperature: 温度参数（忽略）
            max_tokens: 最大 token 数（忽略）
            messages: 历史消息列表（用于多轮对话）

        Returns:
            包含 response_text 和 tool_calls 的字典
        """
        self.call_count += 1

        # 确定要使用的prompt
        if messages:
            # 从messages中提取最后一个user消息作为prompt
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    prompt = msg.get("content", "")
                    break
            else:
                prompt = ""

            # 检查是否有tool结果（表示这是多轮对话）
            has_tool_results = any(msg.get("role") == "tool" for msg in messages)

            if has_tool_results:
                # 多轮对话：结束循环，返回最终响应
                return {"response_text": "启禀陛下，国库现有白银 100 万两。", "tool_calls": []}

        # 如果有预定义 tool_calls，使用它们（只在第一次调用时）
        # 如果 tool_calls 是列表，说明是预定义的，只在第一次调用时返回
        if (
            self.tool_calls is not None
            and isinstance(self.tool_calls, list)
            and len(self.tool_calls) > 0
        ):
            # 第一次调用：返回预定义的tool calls
            if self.call_count == 1:
                return {"response_text": self.response, "tool_calls": self.tool_calls}
            else:
                # 后续调用：返回空
                return {"response_text": "", "tool_calls": []}

        # 如果 tool_calls 是 None，智能生成
        if self.tool_calls is None:
            tool_calls = self._generate_smart_tool_calls(prompt, system_prompt)
        else:
            tool_calls = []

        return {"response_text": self.response, "tool_calls": tool_calls}

    def _generate_smart_tool_calls(self, prompt: str, system_prompt: str | None) -> list[dict]:
        """
        根据事件类型智能生成 tool calls

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词

        Returns:
            tool calls 列表
        """
        # 解析事件类型
        event_type = self._extract_event_type(prompt, system_prompt)

        if event_type == "COMMAND":
            # 命令事件：发送游戏事件 + 通知其他 agent + 回复玩家
            return [
                {
                    "id": "call_1",
                    "function": {
                        "name": "send_game_event",
                        "arguments": json.dumps(
                            {
                                "event_type": "adjust_tax",
                                "payload": {"province": "zhili", "rate": 0.05},
                            },
                            ensure_ascii=False,
                        ),
                    },
                },
                {
                    "id": "call_2",
                    "function": {
                        "name": "send_message_to_agent",
                        "arguments": json.dumps(
                            {
                                "target_agent": "governor_zhili",
                                "message": "户部已拨下银两，请查收。",
                            },
                            ensure_ascii=False,
                        ),
                    },
                },
                {
                    "id": "call_3",
                    "function": {
                        "name": "respond_to_player",
                        "arguments": json.dumps(
                            {"content": "臣遵旨！已给直隶拨款5万两白银，并通知李卫查收。"},
                            ensure_ascii=False,
                        ),
                    },
                },
            ]

        elif event_type == "QUERY":
            # 查询事件：查询数据 + 回复玩家
            return [
                {
                    "id": "call_1",
                    "function": {
                        "name": "query_national_data",
                        "arguments": json.dumps(
                            {"field_name": "imperial_treasury"}, ensure_ascii=False
                        ),
                    },
                },
                {
                    "id": "call_2",
                    "function": {
                        "name": "respond_to_player",
                        "arguments": json.dumps(
                            {"content": "启禀陛下，国库现有白银100万两。"}, ensure_ascii=False
                        ),
                    },
                },
            ]

        elif event_type == "CHAT":
            # 聊天事件：只回复玩家
            return [
                {
                    "id": "call_1",
                    "function": {
                        "name": "respond_to_player",
                        "arguments": json.dumps(
                            {"content": "臣惶恐！陛下垂询，臣不胜感激。"}, ensure_ascii=False
                        ),
                    },
                }
            ]

        elif event_type == "END_TURN":
            # 回合结束：发送 ready 信号
            return [
                {
                    "id": "call_1",
                    "function": {
                        "name": "send_ready",
                        "arguments": json.dumps({}, ensure_ascii=False),
                    },
                }
            ]

        elif event_type == "TURN_RESOLVED":
            # 回合结算完成：写入记忆
            return [
                {
                    "id": "call_1",
                    "function": {
                        "name": "write_memory",
                        "arguments": json.dumps(
                            {"content": "本回合臣完成了陛下的命令。"}, ensure_ascii=False
                        ),
                    },
                }
            ]

        else:
            # 默认：只回复
            return [
                {
                    "id": "call_default",
                    "function": {
                        "name": "respond_to_player",
                        "arguments": f'{{"content": "{self.response}"}}',
                    },
                }
            ]

    def _extract_event_type(self, prompt: str, system_prompt: str | None) -> str:
        """
        从提示词中提取事件类型

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词

        Returns:
            事件类型（COMMAND, QUERY, CHAT, END_TURN, TURN_RESOLVED）
        """
        # 检查 system_prompt 中的任务说明
        if system_prompt:
            if "皇帝下达了命令" in system_prompt:
                return "COMMAND"
            elif "皇帝要查询数据" in system_prompt:
                return "QUERY"
            elif "皇帝想和你聊天" in system_prompt:
                return "CHAT"
            elif "回合即将结束" in system_prompt:
                return "END_TURN"
            elif "回合结算完成" in system_prompt:
                return "TURN_RESOLVED"

        # 检查 prompt 中的事件类型
        if "- 类型:" in prompt:
            match = re.search(r"- 类型:\s*(\w+)", prompt)
            if match:
                event_type = match.group(1).upper()
                if event_type in ["COMMAND", "QUERY", "CHAT", "END_TURN", "TURN_RESOLVED"]:
                    return event_type

        return "UNKNOWN"

    def set_response(self, response: str) -> None:
        """
        设置响应文本

        Args:
            response: 新的响应文本
        """
        self.response = response

    def set_tool_calls(self, tool_calls: list[dict]) -> None:
        """
        设置 tool calls

        Args:
            tool_calls: tool calls 列表（设为 None 启用智能生成）
        """
        self.tool_calls = tool_calls

    def reset(self) -> None:
        """重置调用计数"""
        self.call_count = 0
