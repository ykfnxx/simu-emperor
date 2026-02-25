"""AgentRuntime：三阶段生命周期（summarize/respond/execute）。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from decimal import Decimal

from simu_emperor.agents.context_builder import AgentContext, ContextBuilder, DataScope
from simu_emperor.agents.file_manager import FileManager
from simu_emperor.agents.llm.client import LLMClient
from simu_emperor.agents.llm.providers import (
    ExecutionResult,
    LLMProvider,
)
from simu_emperor.agents.memory_manager import MemoryManager
from simu_emperor.agents.tools.builtin import BuiltinTools
from simu_emperor.agents.tools.executor import ToolExecutor
from simu_emperor.agents.tools.loop import ToolCallLoop
from simu_emperor.agents.tools.registry import ToolRegistry
from simu_emperor.engine.models.base_data import NationalBaseData
from simu_emperor.engine.models.effects import EventEffect
from simu_emperor.engine.models.events import AgentEvent, EventSource, PlayerEvent

logger = logging.getLogger(__name__)


def validate_effects(
    effects: list[EventEffect],
    data_scope: DataScope,
    command: PlayerEvent | None = None,
    agent_id: str | None = None,
) -> list[EventEffect]:
    """规则校验 effects，过滤掉越权的效果。

    校验规则：
    1. effect.target 是否在 data_scope 的 execute_command.fields 范围内
    2. effect.scope.province_ids 是否与命令的 target_province_id 一致（如有）

    Args:
        effects: LLM 生成的效果列表
        data_scope: Agent 的数据权限声明
        command: 触发执行的玩家命令（可选）
        agent_id: Agent ID（用于日志）

    Returns:
        通过校验的效果列表
    """
    exec_scope = data_scope.skills.get("execute_command")
    if exec_scope is None:
        logger.warning(
            f"[{agent_id}] No execute_command scope defined, "
            f"all {len(effects)} effects filtered out"
        )
        return []

    allowed_fields = set(exec_scope.fields)
    # 也允许 national 级字段作为 target
    allowed_fields.update(exec_scope.national)

    valid: list[EventEffect] = []
    for effect in effects:
        # 校验 target 在可写范围内
        if effect.target not in allowed_fields:
            logger.warning(
                f"[{agent_id}] Effect filtered: target '{effect.target}' not in allowed fields. "
                f"Allowed: {sorted(allowed_fields)}"
            )
            continue

        # 校验 province_ids 与命令一致
        if command and command.target_province_id and effect.scope.province_ids:
            if command.target_province_id not in effect.scope.province_ids:
                logger.warning(
                    f"[{agent_id}] Effect filtered: province_ids {effect.scope.province_ids} "
                    f"don't match command target '{command.target_province_id}'"
                )
                continue

        valid.append(effect)

    if len(valid) != len(effects):
        logger.warning(
            f"[{agent_id}] {len(valid)}/{len(effects)} effects passed validation, "
            f"{len(effects) - len(valid)} filtered out"
        )

    return valid


class AgentRuntime:
    """Agent 三阶段生命周期运行时。

    三阶段：
    1. summarize — 汇总阶段：生成报告，写入 workspace 和记忆
    2. respond — 交互阶段：回答玩家问题
    3. execute — 执行阶段：执行命令，生成 AgentEvent
    """

    def __init__(
        self,
        llm_client: LLMClient,
        context_builder: ContextBuilder,
        memory_manager: MemoryManager,
        file_manager: FileManager,
    ) -> None:
        self._llm = llm_client
        self._context_builder = context_builder
        self._memory = memory_manager
        self._file_manager = file_manager

    async def summarize(
        self,
        agent_id: str,
        turn: int,
        national_data: NationalBaseData,
    ) -> str:
        """汇总阶段：生成报告。

        1. 组装 context（soul + write_report skill + data + memory）
        2. 调用 LLM 生成报告
        3. 写入 workspace/{turn:03d}_report.md
        4. 写入短期记忆 recent/turn_{NNN}.md

        Args:
            agent_id: Agent ID
            turn: 当前回合
            national_data: 全国数据

        Returns:
            报告内容（markdown）
        """
        # 读取记忆
        mem = self._memory.read_context(agent_id)

        # 组装上下文
        context = self._context_builder.build_context(
            agent_id=agent_id,
            skill_name="write_report",
            national_data=national_data,
            memory_summary=mem.summary,
            recent_memories=mem.recent,
        )

        # 调用 LLM
        report = await self._llm.generate(context)

        # 写入 workspace
        filename = f"{turn:03d}_report.md"
        self._file_manager.write_workspace_file(agent_id, filename, report)

        # 写入短期记忆
        self._memory.write_recent(agent_id, turn, report)

        return report

    async def respond(
        self,
        agent_id: str,
        turn: int,
        player_message: str,
        national_data: NationalBaseData,
    ) -> str:
        """交互阶段：回答玩家问题。

        1. 组装 context（soul + query_data skill + data + memory）
        2. 将玩家问题附加到 skill prompt 中
        3. 调用 LLM 生成回答

        Args:
            agent_id: Agent ID
            turn: 当前回合
            player_message: 玩家消息
            national_data: 全国数据

        Returns:
            Agent 的回答
        """
        # 读取记忆
        mem = self._memory.read_context(agent_id)

        # 组装上下文
        context = self._context_builder.build_context(
            agent_id=agent_id,
            skill_name="query_data",
            national_data=national_data,
            memory_summary=mem.summary,
            recent_memories=mem.recent,
        )

        # 将玩家消息附加到 skill prompt 中
        context = AgentContext(
            agent_id=context.agent_id,
            soul=context.soul,
            skill=context.skill + f"\n\n## 玩家问话\n{player_message}",
            data=context.data,
            memory_summary=context.memory_summary,
            recent_memories=context.recent_memories,
        )

        # 调用 LLM
        return await self._llm.generate(context)

    async def respond_stream(
        self,
        agent_id: str,
        turn: int,
        player_message: str,
        national_data: NationalBaseData,
    ) -> AsyncIterator[str]:
        """交互阶段：流式回答玩家问题。

        Args:
            agent_id: Agent ID
            turn: 当前回合
            player_message: 玩家消息
            national_data: 全国数据

        Yields:
            Agent 回答的文本块
        """
        # 读取记忆
        mem = self._memory.read_context(agent_id)

        # 组装上下文
        context = self._context_builder.build_context(
            agent_id=agent_id,
            skill_name="query_data",
            national_data=national_data,
            memory_summary=mem.summary,
            recent_memories=mem.recent,
        )

        # 将玩家消息附加到 skill prompt 中
        context = AgentContext(
            agent_id=context.agent_id,
            soul=context.soul,
            skill=context.skill + f"\n\n## 玩家问话\n{player_message}",
            data=context.data,
            memory_summary=context.memory_summary,
            recent_memories=context.recent_memories,
            rule=context.rule,
        )

        # 流式调用 LLM
        async for chunk in self._llm.generate_stream(context):
            yield chunk

    async def execute(
        self,
        agent_id: str,
        turn: int,
        command: PlayerEvent,
        national_data: NationalBaseData,
    ) -> AgentEvent:
        """执行阶段：执行玩家命令，生成 AgentEvent。

        1. 组装 context（soul + execute_command skill + data + memory）
        2. 将命令内容附加到 prompt
        3. 调用 LLM 生成 ExecutionResult（结构化输出）
        4. 规则校验 effects
        5. 生成 AgentEvent

        Args:
            agent_id: Agent ID
            turn: 当前回合
            command: 玩家命令
            national_data: 全国数据

        Returns:
            AgentEvent 事件
        """
        # 读取记忆
        mem = self._memory.read_context(agent_id)

        # 组装上下文
        context = self._context_builder.build_context(
            agent_id=agent_id,
            skill_name="execute_command",
            national_data=national_data,
            memory_summary=mem.summary,
            recent_memories=mem.recent,
        )

        # 附加命令内容
        command_info = (
            f"\n\n## 皇帝命令\n"
            f"- 命令类型: {command.command_type}\n"
            f"- 目标省份: {command.target_province_id or '全国'}\n"
        )
        if command.parameters:
            command_info += "- 参数:\n"
            for k, v in command.parameters.items():
                command_info += f"  - {k}: {v}\n"
        command_info += f"- 命令描述: {command.description}\n"

        context = AgentContext(
            agent_id=context.agent_id,
            soul=context.soul,
            skill=context.skill + command_info,
            data=context.data,
            memory_summary=context.memory_summary,
            recent_memories=context.recent_memories,
        )

        # 调用 LLM 获取结构化输出
        result: ExecutionResult = await self._llm.generate_structured(context, ExecutionResult)

        # 规则校验
        data_scope = self._context_builder.load_data_scope(agent_id)
        valid_effects = validate_effects(result.effects, data_scope, command)

        # 校验失败时降级
        if len(valid_effects) != len(result.effects):
            fidelity = Decimal("0")
            valid_effects = []
        else:
            fidelity = result.fidelity

        # 写入 workspace
        exec_filename = f"{turn:03d}_exec_{command.command_type}.md"
        self._file_manager.write_workspace_file(agent_id, exec_filename, result.narrative)

        # 生成 AgentEvent
        return AgentEvent(
            source=EventSource.AGENT,
            turn_created=turn,
            description=result.narrative,
            effects=valid_effects,
            agent_event_type=command.command_type,
            agent_id=agent_id,
            fidelity=fidelity,
        )

    async def respond_with_tools(
        self,
        agent_id: str,
        turn: int,
        player_message: str,
        national_data: NationalBaseData,
        provider: LLMProvider | None = None,
        max_iterations: int = 5,
    ) -> str:
        """交互阶段：使用 function calling 回答玩家问题。

        与 respond() 不同，此方法允许 LLM 调用工具查询数据，
        而不是预先提供所有数据。

        Args:
            agent_id: Agent ID
            turn: 当前回合
            player_message: 玩家消息
            national_data: 全国数据
            provider: LLM provider（如果 None 则使用 _llm 的 provider）
            max_iterations: 最大工具调用迭代次数

        Returns:
            Agent 的回答
        """
        # 获取 provider
        if provider is None:
            provider = self._llm._provider

        # 读取 soul 和 memory
        soul = self._file_manager.read_soul(agent_id)
        mem = self._memory.read_context(agent_id)
        data_scope = self._context_builder.load_data_scope(agent_id)

        # 获取 query_data skill 的权限范围
        skill_scope = data_scope.skills.get("query_data")
        if skill_scope is None:
            # 降级到普通 respond
            return await self.respond(agent_id, turn, player_message, national_data)

        # 读取 skill 模板
        skill = self._file_manager.read_skill("query_data")

        # 构建 system prompt
        from simu_emperor.agents.context_builder import load_rule_md
        rule = load_rule_md(self._file_manager.template_base.parent)
        system_parts = []
        if rule:
            system_parts.append(rule)
            system_parts.append("")
        system_parts.append(soul)
        system_prompt = "\n".join(system_parts)

        # 构建 user prompt
        user_parts = [
            "## 技能指令",
            skill,
            "",
            "## 玩家问话",
            player_message,
        ]

        # 添加记忆
        if mem.summary:
            user_parts.extend(["", "## 长期记忆", mem.summary])
        if mem.recent:
            user_parts.extend(["", "## 近期记忆"])
            for t, content in mem.recent:
                user_parts.append(f"回合 {t}: {content}")

        user_prompt = "\n".join(user_parts)

        # 创建 tool registry 和 builtin tools
        registry = ToolRegistry()
        builtin_tools = BuiltinTools(national_data, skill_scope)

        for tool, handler in builtin_tools.get_tools_and_handlers():
            registry.register(tool, handler)

        # 创建 executor 和 loop
        executor = ToolExecutor(registry, skill_scope)
        loop = ToolCallLoop(
            llm_client=provider,
            executor=executor,
            max_iterations=max_iterations,
        )

        # 构建初始消息
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # 运行工具调用循环
        response = await loop.run(messages, registry.list_tools())

        return response

    async def execute_with_tools(
        self,
        agent_id: str,
        turn: int,
        command: PlayerEvent,
        national_data: NationalBaseData,
        provider: LLMProvider | None = None,
        max_iterations: int = 5,
    ) -> AgentEvent:
        """执行阶段：使用 function calling 执行命令。

        与 execute() 不同，此方法允许 LLM 调用工具查询数据，
        然后生成结构化的 ExecutionResult。

        Args:
            agent_id: Agent ID
            turn: 当前回合
            command: 玩家命令
            national_data: 全国数据
            provider: LLM provider（如果 None 则使用 _llm 的 provider）
            max_iterations: 最大工具调用迭代次数

        Returns:
            AgentEvent 事件
        """
        # 获取 provider
        if provider is None:
            provider = self._llm._provider

        # 读取 soul 和 memory
        soul = self._file_manager.read_soul(agent_id)
        mem = self._memory.read_context(agent_id)
        data_scope = self._context_builder.load_data_scope(agent_id)

        # 获取 execute_command skill 的权限范围
        skill_scope = data_scope.skills.get("execute_command")
        if skill_scope is None:
            raise ValueError(f"Agent {agent_id} has no execute_command skill scope")

        # 读取 skill 模板
        skill = self._file_manager.read_skill("execute_command")

        # 构建 system prompt
        from simu_emperor.agents.context_builder import load_rule_md
        rule = load_rule_md(self._file_manager.template_base.parent)
        system_parts = []
        if rule:
            system_parts.append(rule)
            system_parts.append("")
        system_parts.append(soul)
        system_prompt = "\n".join(system_parts)

        # 构建 user prompt
        user_parts = [
            "## 技能指令",
            skill,
        ]

        # 添加命令内容
        command_info = (
            "\n\n## 皇帝命令\n"
            f"- 命令类型: {command.command_type}\n"
            f"- 目标省份: {command.target_province_id or '全国'}\n"
        )
        if command.parameters:
            command_info += "- 参数:\n"
            for k, v in command.parameters.items():
                command_info += f"  - {k}: {v}\n"
        command_info += f"- 命令描述: {command.description}\n"
        user_parts.append(command_info)

        # 添加记忆
        if mem.summary:
            user_parts.extend(["", "## 长期记忆", mem.summary])
        if mem.recent:
            user_parts.extend(["", "## 近期记忆"])
            for t, content in mem.recent:
                user_parts.append(f"回合 {t}: {content}")

        user_prompt = "\n".join(user_parts)

        # 创建 tool registry 和 builtin tools（只读工具）
        registry = ToolRegistry()
        builtin_tools = BuiltinTools(national_data, skill_scope)

        for tool, handler in builtin_tools.get_tools_and_handlers():
            registry.register(tool, handler)

        # 创建 executor 和 loop
        executor = ToolExecutor(registry, skill_scope)
        loop = ToolCallLoop(
            llm_client=provider,
            executor=executor,
            max_iterations=max_iterations,
        )

        # 构建初始消息
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # 运行工具调用循环
        final_response = await loop.run(messages, registry.list_tools())

        # 解析最终响应为 ExecutionResult
        # 使用结构化输出获取最终结果
        structured_context = AgentContext(
            agent_id=agent_id,
            soul=soul,
            skill=skill + f"\n\n## 工具调用后的分析\n{final_response}\n\n## 皇帝命令\n{command.description}",
            data={},
            memory_summary=mem.summary,
            recent_memories=mem.recent,
            rule=rule if rule else None,
        )

        result: ExecutionResult = await self._llm.generate_structured(
            structured_context, ExecutionResult
        )

        # 规则校验
        valid_effects = validate_effects(result.effects, data_scope, command)

        # 校验失败时降级
        if len(valid_effects) != len(result.effects):
            fidelity = Decimal("0")
            valid_effects = []
        else:
            fidelity = result.fidelity

        # 写入 workspace
        exec_filename = f"{turn:03d}_exec_{command.command_type}.md"
        self._file_manager.write_workspace_file(agent_id, exec_filename, result.narrative)

        # 生成 AgentEvent
        return AgentEvent(
            source=EventSource.AGENT,
            turn_created=turn,
            description=result.narrative,
            effects=valid_effects,
            agent_event_type=command.command_type,
            agent_id=agent_id,
            fidelity=fidelity,
        )
