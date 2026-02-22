"""Route 机制：LLM agent 充当 router（带超时和置信度检查）。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import filelock


class RouterTimeoutError(Exception):
    """Router 超时错误。"""

    pass


class RouterAgent:
    """异步路由命令到合适的 agent，带超时保护。"""

    def __init__(
        self,
        llm_client: Any,
        timeout: float = 5.0,
        role_map_path: Path | None = None,
    ) -> None:
        """初始化 Router。

        Args:
            llm_client: LLM 客户端（需要有 complete 方法）
            timeout: 超时时间（秒）
            role_map_path: role_map.md 文件路径，默认为 data/role_map.md
        """
        self.llm_client = llm_client
        self.timeout = timeout
        self.role_map_path = role_map_path or Path("data/role_map.md")
        self._role_map: str | None = None

    def _load_role_map(self) -> str:
        """加载 role_map.md 内容（带缓存）。"""
        if self._role_map is None:
            if self.role_map_path.exists():
                self._role_map = self.role_map_path.read_text(encoding="utf-8")
            else:
                self._role_map = ""
        return self._role_map

    def _get_valid_agents(self) -> list[str]:
        """从 role_map 中提取有效的 agent_id 列表。"""
        role_map = self._load_role_map()
        agents: list[str] = []
        for line in role_map.split("\n"):
            # 匹配格式：## 角色 (agent_id)
            if line.startswith("## ") and "(" in line and ")" in line:
                start = line.index("(") + 1
                end = line.index(")")
                agent_id = line[start:end].strip()
                if agent_id:
                    agents.append(agent_id)
        return agents

    async def route_command(self, command: str, context: dict[str, Any]) -> str:
        """异步路由命令到合适的 agent，带超时保护。

        Args:
            command: 命令内容
            context: 上下文信息（如当前回合等）

        Returns:
            选中的 agent_id

        Raises:
            RouterTimeoutError: 超时时抛出
            ValueError: 无效的 agent_id 时抛出
        """
        role_map = self._load_role_map()
        valid_agents = self._get_valid_agents()

        prompt = f"""根据以下职责表，选择最适合执行该命令的官员。

## 职责表
{role_map}

## 命令
{command}

## 上下文
{context}

请只返回官员的 agent_id（如 governor_zhili、minister_of_revenue 等），不要返回其他内容。"""

        try:
            result = await asyncio.wait_for(
                self._call_llm(prompt),
                timeout=self.timeout,
            )
            agent_id = self._parse_agent_id(result)

            # 验证 agent_id 有效
            if valid_agents and agent_id not in valid_agents:
                raise ValueError(f"Invalid agent_id: {agent_id}")

            return agent_id
        except asyncio.TimeoutError:
            raise RouterTimeoutError(f"Router timeout after {self.timeout}s")

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM 生成响应。"""
        # 使用简单的 generate 方法
        # llm_client 可能是 LLMClient，需要构造一个简单的 context
        from simu_emperor.agents.context_builder import AgentContext

        context = AgentContext(
            agent_id="router",
            soul="你是一个命令路由器，负责将皇帝的命令分配给最合适的官员。",
            skill=prompt,
            data={},
        )
        return await self.llm_client.generate(context)

    def _parse_agent_id(self, result: str) -> str:
        """解析 LLM 返回的 agent_id。"""
        # 提取结果中的 agent_id
        text = result.strip()

        # 如果包含括号，提取括号内容
        if "(" in text and ")" in text:
            start = text.rindex("(") + 1
            end = text.rindex(")")
            return text[start:end].strip()

        # 如果包含空格，取最后一个单词
        if " " in text:
            return text.split()[-1].strip()

        return text


def update_role_map(
    agent_id: str,
    role_name: str,
    role_description: str,
    role_map_path: Path | None = None,
) -> None:
    """更新 role_map.md，带文件锁保护并发写入。

    Args:
        agent_id: Agent ID
        role_name: 角色名称
        role_description: 角色描述
        role_map_path: role_map.md 文件路径，默认为 data/role_map.md
    """
    role_map_path = role_map_path or Path("data/role_map.md")
    lock_path = role_map_path.with_suffix(".md.lock")

    with filelock.FileLock(str(lock_path), timeout=10):
        # 读取现有内容
        if role_map_path.exists():
            content = role_map_path.read_text(encoding="utf-8")
        else:
            content = "# 大庆帝国官员职责表\n"

        # 检查是否已存在该 agent
        if f"({agent_id})" in content:
            # 更新现有条目
            lines = content.split("\n")
            new_lines: list[str] = []
            in_target_section = False
            for line in lines:
                if f"## {role_name} ({agent_id})" in line:
                    in_target_section = True
                    new_lines.append(f"## {role_name} ({agent_id})")
                    continue
                if in_target_section:
                    if line.startswith("## "):
                        in_target_section = False
                        new_lines.append(f"- 职责：{role_description}")
                    else:
                        continue
                new_lines.append(line)
            content = "\n".join(new_lines)
        else:
            # 添加新条目
            if not content.endswith("\n"):
                content += "\n"
            content += f"\n## {role_name} ({agent_id})\n"
            content += f"- 职责：{role_description}\n"

        # 写入文件
        role_map_path.write_text(content, encoding="utf-8")
