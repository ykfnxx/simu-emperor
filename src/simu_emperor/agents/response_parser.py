"""
响应解析器 - 解析 LLM 结构化输出
"""

import json
import logging
import re
from typing import Any


logger = logging.getLogger(__name__)


def parse_execution_result(response: str) -> dict[str, Any]:
    """
    解析 LLM 执行结果

    LLM 应该返回 JSON 格式的结构化输出：
    ```json
    {
        "narrative": "叙述性文本",
        "action": "动作名称",
        "effects": [...],
        "fidelity": 1.0,
        "notifications": ["agent1", "agent2"]
    }
    ```

    所有额外字段（effects, fidelity, notifications）都会被放入 params 中。

    Args:
        response: LLM 响应文本

    Returns:
        解析后的字典，包含 narrative, action, params
        解析失败时返回默认值
    """
    # 尝试直接解析 JSON
    try:
        data = json.loads(response.strip())
        if isinstance(data, dict):
            # 提取必需字段
            narrative = data.get("narrative", response)
            action = data.get("action", "unknown")

            # 提取可选字段到 params
            params = {}
            for key in ["effects", "fidelity", "notifications"]:
                if key in data:
                    params[key] = data[key]

            # 如果有 params 字段，合并它
            if "params" in data and isinstance(data["params"], dict):
                params.update(data["params"])

            return {
                "narrative": narrative,
                "action": action,
                "params": params,
            }
    except json.JSONDecodeError:
        pass

    # 尝试从 Markdown 代码块中提取 JSON
    json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1).strip())
            if isinstance(data, dict):
                # 提取必需字段
                narrative = data.get("narrative", response)
                action = data.get("action", "unknown")

                # 提取可选字段到 params
                params = {}
                for key in ["effects", "fidelity", "notifications"]:
                    if key in data:
                        params[key] = data[key]

                # 如果有 params 字段，合并它
                if "params" in data and isinstance(data["params"], dict):
                    params.update(data["params"])

                return {
                    "narrative": narrative,
                    "action": action,
                    "params": params,
                }
        except json.JSONDecodeError:
            pass

    # 尝试匹配简单的动作模式
    action_match = re.search(r"动作[：:]\s*(\w+)", response)
    if action_match:
        action = action_match.group(1)
        return {
            "narrative": response,
            "action": action,
            "params": {},
        }

    # 解析失败，返回默认值
    logger.warning(f"Failed to parse execution result, using default. Response: {response[:200]}")
    return _get_default_result(response)


def _validate_result(data: dict[str, Any]) -> bool:
    """
    验证解析结果是否有效

    Args:
        data: 解析后的字典

    Returns:
        是否有效
    """
    # 必需字段：narrative, action
    if "narrative" not in data or "action" not in data:
        return False

    # 字段类型检查
    if not isinstance(data["narrative"], str):
        return False

    if not isinstance(data["action"], str):
        return False

    # params 是可选的
    if "params" in data and not isinstance(data["params"], dict):
        return False

    return True


def _get_default_result(response: str) -> dict[str, Any]:
    """
    获取默认解析结果

    Args:
        response: 原始响应文本

    Returns:
        默认结果字典
    """
    return {
        "narrative": response,
        "action": "unknown",
        "params": {},
    }


def parse_query_result(response: str) -> str:
    """
    解析查询结果

    Args:
        response: LLM 响应文本

    Returns:
        提取的查询结果
    """
    # 尝试提取 JSON
    try:
        data = json.loads(response.strip())
        if isinstance(data, dict) and "result" in data:
            return str(data["result"])
    except json.JSONDecodeError:
        pass

    # 返回原始响应
    return response


def parse_chat_result(response: str) -> str:
    """
    解析对话结果

    Args:
        response: LLM 响应文本

    Returns:
        对话文本
    """
    # 去除可能的 JSON 代码块
    json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
    if json_match:
        # 如果整个响应都是 JSON，提取 narrative 字段
        try:
            data = json.loads(json_match.group(1).strip())
            if isinstance(data, dict) and "narrative" in data:
                return data["narrative"]
        except json.JSONDecodeError:
            pass

    # 返回原始响应
    return response
