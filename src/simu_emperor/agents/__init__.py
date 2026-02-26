"""
Agents 模块 - AI 官员系统

文件驱动的被动 Agent：
- 只响应事件，不主动发起
- personality 和权限由文件定义（soul.md, data_scope.yaml）
- 三个工作流：summarize → respond → execute
- 使用 LLM 生成响应
"""

from simu_emperor.agents.agent import Agent
from simu_emperor.agents.response_parser import (
    parse_chat_result,
    parse_execution_result,
    parse_query_result,
)

__all__ = [
    "Agent",
    "parse_execution_result",
    "parse_query_result",
    "parse_chat_result",
]
