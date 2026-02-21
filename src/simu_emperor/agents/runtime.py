"""AgentRuntime：三阶段生命周期（summarize/respond/execute）。"""

from __future__ import annotations

import time
from decimal import Decimal

from simu_emperor.agents.context_builder import AgentContext, ContextBuilder, DataScope
from simu_emperor.agents.file_manager import FileManager
from simu_emperor.agents.llm.client import LLMClient
from simu_emperor.agents.llm.providers import ExecutionResult
from simu_emperor.agents.memory_manager import MemoryManager
from simu_emperor.engine.models.base_data import NationalBaseData
from simu_emperor.engine.models.effects import EventEffect
from simu_emperor.engine.models.events import AgentEvent, EventSource, PlayerEvent
from simu_emperor.infrastructure.logging import get_logger, log_context

logger = get_logger(__name__)


def validate_effects(
    effects: list[EventEffect],
    data_scope: DataScope,
    command: PlayerEvent | None = None,
) -> list[EventEffect]:
    """规则校验 effects，过滤掉越权的效果。

    校验规则：
    1. effect.target 是否在 data_scope 的 execute_command.fields 范围内
    2. effect.scope.province_ids 是否与命令的 target_province_id 一致（如有）

    Args:
        effects: LLM 生成的效果列表
        data_scope: Agent 的数据权限声明
        command: 触发执行的玩家命令（可选）

    Returns:
        通过校验的效果列表
    """
    exec_scope = data_scope.skills.get("execute_command")
    if exec_scope is None:
        return []

    allowed_fields = set(exec_scope.fields)
    # 也允许 national 级字段作为 target
    allowed_fields.update(exec_scope.national)

    valid: list[EventEffect] = []
    for effect in effects:
        # 校验 target 在可写范围内
        if effect.target not in allowed_fields:
            continue

        # 校验 province_ids 与命令一致
        if command and command.target_province_id and effect.scope.province_ids:
            if command.target_province_id not in effect.scope.province_ids:
                continue

        valid.append(effect)

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
        start_time = time.time()
        async with log_context(agent_id=agent_id, turn=turn):
            logger.info("agent_phase_started", phase="summarize")

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

            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "agent_phase_completed",
                phase="summarize",
                duration_ms=round(duration_ms, 2),
                report_length=len(report),
            )

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
        start_time = time.time()
        async with log_context(agent_id=agent_id, turn=turn):
            logger.info("agent_phase_started", phase="respond", message_length=len(player_message))

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
            response = await self._llm.generate(context)

            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "agent_phase_completed",
                phase="respond",
                duration_ms=round(duration_ms, 2),
                response_length=len(response),
            )

        return response

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
        start_time = time.time()
        async with log_context(agent_id=agent_id, turn=turn):
            logger.info(
                "agent_phase_started",
                phase="execute",
                command_type=command.command_type,
                target_province=command.target_province_id,
            )

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

            # 记录效果校验结果
            original_count = len(result.effects)
            valid_count = len(valid_effects)
            if original_count > 0:
                logger.info(
                    "effects_validated",
                    agent_id=agent_id,
                    original_count=original_count,
                    valid_count=valid_count,
                    filtered_count=original_count - valid_count,
                )

            # 校验失败时降级
            if len(valid_effects) != len(result.effects):
                fidelity = Decimal("0")
                valid_effects = []
            else:
                fidelity = result.fidelity

            # 写入 workspace
            exec_filename = f"{turn:03d}_exec_{command.command_type}.md"
            self._file_manager.write_workspace_file(agent_id, exec_filename, result.narrative)

            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "agent_phase_completed",
                phase="execute",
                duration_ms=round(duration_ms, 2),
                effects_count=len(valid_effects),
                fidelity=float(fidelity),
            )

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
