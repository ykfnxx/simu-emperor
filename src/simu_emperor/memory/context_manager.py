from __future__ import annotations

"""ContextManager for sliding window context management（V4 重构）."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from simu_emperor.common import FileOperationsHelper

if TYPE_CHECKING:
    from simu_emperor.event_bus.event import Event
    from simu_emperor.llm.base import LLMProvider
    from simu_emperor.memory.tape_metadata import TapeMetadataManager
    from simu_emperor.memory.tape_writer import TapeWriter

logger = logging.getLogger(__name__)


def count_tokens(text: str, model: Literal["gpt-4", "claude-3"] = "gpt-4") -> int:
    """
    使用tiktoken精确计算token数

    Args:
        text: 待计算的文本
        model: 模型名称（用于选择编码器）

    Returns:
        token数量
    """
    try:
        import tiktoken

        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception:
        # Fallback: 粗略估算（2字符 ≈ 1 token）
        return len(text) // 2


@dataclass
class ContextConfig:
    """Configuration for ContextManager."""

    max_tokens: int | None = 8000  # None = 从LLM API获取
    threshold_ratio: float = 0.95  # 触发滑动窗口的阈值比例
    keep_recent_events: int = 20  # 滑动窗口后保留的事件数
    anchor_buffer: int = 3  # 锚点附近保留的事件数
    enable_anchor_aware: bool = True  # 启用锚点感知滑动窗口


class ContextManager:
    """
    管理当前session上下文窗口，从tape加载历史并控制token数量

    SPEC: V3_MEMORY_SYSTEM_SPEC.md §4.3
    V4: 完全接管上下文管理，同步写入 tape，更新 tape_meta.jsonl segment_index
    """

    def __init__(
        self,
        session_id: str,
        agent_id: str,
        tape_path: Path,
        config: ContextConfig,
        llm_provider: "LLMProvider",
        session_manager=None,
        # V4: 新增参数
        tape_metadata_mgr: "TapeMetadataManager | None" = None,
        tape_writer: "TapeWriter | None" = None,
        system_prompt: str | None = None,
    ):
        """
        Initialize ContextManager（V4 重构）。

        Args:
            session_id: Session identifier
            agent_id: Agent identifier
            tape_path: Path to tape.jsonl file
            config: Context configuration
            llm_provider: LLM provider for summarization
            session_manager: Optional SessionManager for ancestor loading
            tape_metadata_mgr: V4 TapeMetadataManager for segment_index updates
            tape_writer: V4 TapeWriter for synchronous tape writing
            system_prompt: V4 System prompt to store
        """
        self.session_id = session_id
        self.agent_id = agent_id
        self.tape_path = tape_path
        self.llm = llm_provider
        self.config = config
        self.session_manager = session_manager
        self.tape_metadata_mgr = tape_metadata_mgr  # V4

        # V4: 新增属性
        self._tape_writer = tape_writer
        self._system_prompt = system_prompt

        # 初始化max_tokens（如果为None则查询LLM）
        self.max_tokens = config.max_tokens or self._query_llm_context_window()
        self.threshold = int(self.max_tokens * config.threshold_ratio)

        # 窗口状态
        self.events: list[dict] = []  # 当前窗口内的事件（从tape加载）
        self.summary: str = ""  # 历史摘要

        # V4: Track absolute tape position for segment_index updates
        self._tape_position_counter: int = 0  # Current position in tape.jsonl
        self._window_offset: int = 0  # Position anchor for incremental loading

    def event_to_messages(self, event: dict) -> list[dict]:
        """
        将事件转换为messages格式

        SPEC: V3_MEMORY_SYSTEM_SPEC.md §4.3

        Args:
            event: 事件字典

        Returns:
            消息列表
        """
        from simu_emperor.event_bus.event_types import EventType

        event_type = event.get("event_type", event.get("type", "UNKNOWN"))
        payload = event.get("payload", event.get("content", {}))

        if event_type == EventType.USER_QUERY:
            query = payload.get("query") if isinstance(payload, dict) else payload
            return [{"role": "user", "content": str(query)}]
        elif event_type == EventType.CHAT:
            # 先检查 message（普通聊天），再检查 command（命令）
            message = payload.get("message", "") if isinstance(payload, dict) else ""
            command = payload.get("command", "") if isinstance(payload, dict) else ""

            if message:
                parts = [
                    "# 收到的事件",
                    f"- 来源: {event.get('src', 'unknown')}",
                    f"- 类型: {event_type}",
                    f"- 时间: {event.get('timestamp', '')}",
                    "\n# 皇帝的消息：",
                    "```",
                    message,
                    "```",
                ]
                return [{"role": "user", "content": "\n".join(parts)}]
            elif command:
                parts = [
                    "# 收到的事件",
                    f"- 来源: {event.get('src', 'unknown')}",
                    f"- 类型: {event_type}",
                    f"- 时间: {event.get('timestamp', '')}",
                    "\n# 皇帝的命令：",
                    "```",
                    command,
                    "```",
                    "\n**重要**：你需要**执行**这个命令，不仅仅是查询数据！",
                ]
                return [{"role": "user", "content": "\n".join(parts)}]
            else:
                return []
        elif event_type == EventType.AGENT_MESSAGE:
            message = payload.get("message", "") if isinstance(payload, dict) else str(payload)
            source_agent = event.get("src", "unknown").replace("agent:", "")

            if message:
                formatted_content = f"# 来自 {source_agent} 的消息：\n```\n{message}\n```"
                return [{"role": "user", "content": formatted_content}]
            else:
                return []
        elif event_type == EventType.RESPONSE:
            # RESPONSE 事件需要区分：
            # - 如果 dst 是非空列表且包含当前 agent → 旧格式数据（dst 是自己），跳过
            # - 如果 dst 是非空列表且 src 是当前 agent → 新格式（dst 是玩家），跳过
            # - 如果 dst 不存在或为空 → 旧格式但可能没有 ASSISTANT_RESPONSE，转换
            # - 如果 dst 不包含当前 agent → 来自其他 agent 的消息 → "user"
            narrative = payload.get("narrative") if isinstance(payload, dict) else payload
            src = event.get("src", "")
            dst = event.get("dst", None)

            # 检查是否 dst 是非空列表且包含当前 agent（旧格式：dst 是自己）
            if dst and isinstance(dst, list) and f"agent:{self.agent_id}" in dst:
                # 旧格式：dst 是自己 → 跳过（ASSISTANT_RESPONSE 已记录相同内容）
                return []

            # 检查是否 dst 是非空列表且 src 是当前 agent（新格式：有 dst 字段但不是自己）
            if dst and isinstance(dst, list) and src == f"agent:{self.agent_id}":
                # 新格式：自己的响应且 dst 存在（ASSISTANT_RESPONSE 已记录）
                return []

            # 旧格式（没有 dst 字段或 dst 为空）且 src 是当前 agent → 转换为 assistant
            if (
                not dst or (isinstance(dst, list) and len(dst) == 0)
            ) and src == f"agent:{self.agent_id}":
                return [{"role": "assistant", "content": str(narrative)}]

            # 其他 agent 的响应 → user (格式化为来自其他 agent 的消息)
            source_agent = src.replace("agent:", "")
            formatted_content = f"# 来自 {source_agent} 的回复：\n```\n{narrative}\n```"
            return [{"role": "user", "content": formatted_content}]
        elif event_type == EventType.TASK_CREATED:
            goal = payload.get("goal", "")
            constraints = payload.get("constraints", "")
            description = payload.get("description", "")
            task_session_id = payload.get("task_session_id", "")
            parent_session = payload.get("parent_session_id", "")

            if goal or description:
                parts = ["\n# 📋 任务会话已创建"]
                parts.append(f"\n**当前任务会话 ID**: `{task_session_id}`")
                if parent_session:
                    parts.append(f"- 父会话: {parent_session}")
                if description:
                    parts.append(f"- 任务描述: {description}")
                if goal:
                    parts.append("\n## 任务目标")
                    parts.append(goal)
                if constraints:
                    parts.append("\n## 成功约束")
                    parts.append(constraints)
                parts.append("\n**你需要根据以上目标和约束执行任务**")
                parts.append(
                    "\n**任务完成后，使用以下 ID 调用 finish_task_session 或 fail_task_session**:"
                )
                parts.append(f"- task_session_id: `{task_session_id}`")

                return [{"role": "user", "content": "\n".join(parts)}]
            else:
                return []

        elif event_type == EventType.ASSISTANT_RESPONSE:
            response = payload.get("response") if isinstance(payload, dict) else payload
            tool_calls = payload.get("tool_calls") if isinstance(payload, dict) else None

            msg = {"role": "assistant", "content": str(response) or None}

            if tool_calls:
                msg["tool_calls"] = [
                    {
                        "id": tc.get("id") or "",
                        "type": tc.get("type") or "function",
                        "function": {
                            "name": tc.get("function", {}).get("name") or "",
                            "arguments": tc.get("function", {}).get("arguments") or "{}",
                        },
                    }
                    for tc in tool_calls
                ]

            return [msg]
        elif event_type == EventType.TOOL_RESULT:
            tool_call_id = payload.get("tool_call_id", "") if isinstance(payload, dict) else ""
            result = payload.get("result") if isinstance(payload, dict) else payload
            return [
                {
                    "role": "tool",
                    "tool_call_id": str(tool_call_id),
                    "content": str(result),
                }
            ]
        else:
            return [{"role": "system", "content": f"[{event_type}] {str(payload)}"}]

    def _query_llm_context_window(self) -> int:
        """查询LLM API获取context window大小"""
        try:
            return self.llm.get_context_window_size()
        except (AttributeError, NotImplementedError):
            return 8192  # 默认值

    async def load_from_tape(self, include_ancestors: bool = False) -> None:
        """
        从tape加载历史事件

        Args:
            include_ancestors: 是否包含祖先 Session 的事件

        SPEC: V3_MEMORY_SYSTEM_SPEC.md §4.3
        """
        # 从 tape_meta 读取 window_offset 和 summary
        if self.tape_metadata_mgr:
            metadata = await self.tape_metadata_mgr._find_entry(
                self.tape_metadata_mgr._get_metadata_path(self.agent_id),
                self.session_id
            )
            if metadata:
                self._window_offset = metadata.window_offset
                self.summary = metadata.summary

        # 从 window_offset 开始读取 tape.jsonl（增量加载）
        events = await self._read_tape_from_offset(self.tape_path, self._window_offset)

        self.events.extend(events)

        # V4: Initialize tape position counter based on actual tape file length
        # (not the loaded events length, since we might load incrementally)
        # We need to read the full file to get the actual length
        all_events = await FileOperationsHelper.read_jsonl_file(self.tape_path)
        self._tape_position_counter = len(all_events)

        if include_ancestors and self.session_manager:
            ancestors = self.session_manager.get_parent_chain(self.session_id)
            for ancestor in ancestors:
                ancestor_events = await self._load_session_events(ancestor.session_id)

                # 为祖先事件也计算 token 数
                for event in ancestor_events:
                    if "_tokens" not in event and "tokens" not in event:
                        event["_tokens"] = self._calc_event_tokens(event)

                self.events.extend(ancestor_events)

            self.events.sort(key=lambda e: e.get("timestamp", ""))

        # 加载后检查 token 是否超过阈值，超过则自动 compact
        if self._calc_total_tokens() > self.threshold:
            logger.info(
                f"加载 tape 后 token 总数 {self._calc_total_tokens()} > 阈值 {self.threshold}，"
                f"触发自动 compact（原始事件数: {len(self.events)}）"
            )
            # 记录原始事件列表
            original_events = self.events.copy()

            # 如果事件数 <= keep_recent，直接删除最旧事件直到 token <= 阈值
            # 因为 slide_window() 在这种情况下会直接返回
            if len(self.events) <= self.config.keep_recent_events:
                while self._calc_total_tokens() > self.threshold and len(self.events) > 1:
                    self.events.pop(0)
                    logger.debug(
                        f"删除最旧事件（事件数较少但 token 超阈值），"
                        f"剩余事件数: {len(self.events)}, token: {self._calc_total_tokens()}"
                    )
            else:
                await self.slide_window()

            # 计算 dropped_events 并更新 segment_index（使用事件 ID 比较）
            original_event_ids = {e.get("event_id") for e in original_events}
            current_event_ids = {e.get("event_id") for e in self.events}
            dropped_event_ids = original_event_ids - current_event_ids

            if dropped_event_ids:
                dropped_events = [e for e in original_events if e.get("event_id") in dropped_event_ids]
                await self._update_segment_index_for_dropped(dropped_events)

            logger.info(
                f"自动 compact 完成，最终事件数: {len(self.events)}，"
                f"token 总数: {self._calc_total_tokens()}"
            )

    async def _load_session_events(self, session_id: str) -> list[dict]:
        """加载指定 session 的事件"""
        tape_path = self._get_tape_path(session_id)
        if not tape_path.exists():
            return []
        return await FileOperationsHelper.read_jsonl_file(tape_path)

    def _get_tape_path(self, session_id: str) -> Path:
        """获取 tape 文件路径"""
        if self.session_manager:
            return self.session_manager.get_tape_path(session_id, self.agent_id)
        return self.tape_path

    async def _read_tape_from_offset(
        self,
        tape_path: Path,
        offset: int,
    ) -> list[dict]:
        """
        从指定位置开始读取 tape.jsonl，跳过已压缩的部分。

        Args:
            tape_path: Path to tape.jsonl file
            offset: Starting position (line number) in the file

        Returns:
            List of event dicts from offset onwards
        """
        if not tape_path.exists():
            return []

        all_events = await FileOperationsHelper.read_jsonl_file(tape_path)

        # 从 offset 开始读取（跳过已压缩的部分）
        events = all_events[offset:] if offset < len(all_events) else []

        # 为没有 _tokens 的事件计算 token 数
        for event in events:
            if "_tokens" not in event and "tokens" not in event:
                event["_tokens"] = self._calc_event_tokens(event)

        return events

    def add_event(self, event: dict, tokens: int) -> bool:
        """
        添加事件到上下文（V4 修改：同步写入 tape.jsonl）。

        Args:
            event: 事件数据
            tokens: 事件的token数

        Returns:
            bool: 是否需要滑动窗口
        """
        event["_tokens"] = tokens

        # 先添加事件
        self.events.append(event)

        # V4: Increment tape position counter for new events
        self._tape_position_counter += 1

        # 计算添加后的总token
        current_tokens = self._calc_total_tokens()
        if current_tokens > self.threshold:
            return True  # 需要滑动

        return False

    async def add_event_and_maybe_compact(
        self, event: dict | Event, tokens: int | None = None
    ) -> None:
        """
        添加事件并自动处理 compact（V4 重构：同步写入 tape）。

        V4 架构：ContextManager 是事件写入的唯一入口。
        - 添加事件到内存（events 列表）
        - 写入 tape.jsonl（通过 TapeWriter）
        - 必要时触发 compact（滑动窗口）

        Args:
            event: 事件数据（dict 或 Event 对象）
            tokens: 事件的token数（可选，自动计算）
        """
        from simu_emperor.event_bus.event import Event

        # 如果是 Event 对象，转换为 dict
        if isinstance(event, Event):
            event_dict = event.to_dict()
            event_obj = event  # 保存原始 Event 对象用于 TapeWriter
        else:
            event_dict = event
            event_obj = None

        # 自动计算 tokens（如果未提供）
        if tokens is None:
            tokens = self._calc_event_tokens(event_dict)

        # 添加到内存
        needs_compact = self.add_event(event_dict, tokens)

        # V4: 同步写入 tape.jsonl
        if self._tape_writer:
            if event_obj:
                # 使用原始 Event 对象
                await self._tape_writer.write_event(event_obj, agent_id=self.agent_id)
            else:
                # 从 dict 重建 Event 对象
                await self._tape_writer.write_event(Event(**event_dict), agent_id=self.agent_id)

        # 必要时触发 compact
        if needs_compact:
            await self.slide_window()

    def _calc_event_tokens(self, event: dict) -> int:
        """计算事件的 token 数"""
        # 简单估算：event 的 JSON 字符串长度
        import json

        return len(json.dumps(event, ensure_ascii=False)) // 2

    async def get_llm_messages(self) -> list[dict]:
        """
        获取 LLM-ready messages（V4 新增）。

        Returns:
            [{"role": "system", "content": "..."}, {"role": "user", ...}, ...]
        """
        messages = []

        # V4: 添加 system_prompt
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})

        # 添加历史摘要（如果有）
        if self.summary:
            messages.append({"role": "system", "content": f"[历史会话摘要] {self.summary}"})

        # V4: 转换事件为消息
        messages.extend(self._events_to_messages(self.events))

        return messages

    def _events_to_messages(self, events: list[dict]) -> list[dict]:
        """
        将事件列表转换为 LLM 消息格式（V4 从 Agent 移入）。

        Args:
            events: 事件列表

        Returns:
            LLM messages 列表
        """
        messages = []
        pending_tool_call_ids = set()

        for event in events:
            converted = self.event_to_messages(event)
            # ContextManager.event_to_messages() 返回 list[dict]
            for msg in converted:
                # 追踪 assistant 消息中的 tool_calls
                if msg.get("role") == "assistant" and msg.get("tool_calls"):
                    for tc in msg.get("tool_calls", []):
                        pending_tool_call_ids.add(tc.get("id", ""))

                # 仅当 tool_call_id 在待处理列表中时才添加 tool 消息
                if msg.get("role") == "tool":
                    tool_call_id = msg.get("tool_call_id", "")
                    if tool_call_id in pending_tool_call_ids:
                        messages.append(msg)
                        pending_tool_call_ids.remove(tool_call_id)
                    else:
                        # 跳过孤立的 tool 消息（没有匹配的 tool_calls）
                        logger.debug(
                            f"Skipping orphaned tool message with tool_call_id: {tool_call_id}"
                        )
                else:
                    messages.append(msg)

        return messages

    async def slide_window(self) -> None:
        """
        锚点感知的滑动窗口

        策略：
        1. 如果事件数 <= keep_recent，不做处理
        2. 否则识别锚点并保留最近 N 个事件
        3. 额外保留锚点附近 ±K 个事件
        4. 确保保留的事件 token 总数 <= 阈值（继续删除最旧事件）
        5. 更新 tape_meta.jsonl 的 segment_index 和 summary

        SPEC: V3_MEMORY_SYSTEM_SPEC.md §4.3
        V4: Updates tape_meta.jsonl segment_index and cumulative summary
        """
        keep_recent = self.config.keep_recent_events
        anchor_buffer = self.config.anchor_buffer

        # 检查是否需要 compact：token 超过阈值 或 事件数超过 keep_recent
        if len(self.events) <= keep_recent and self._calc_total_tokens() <= self.threshold:
            return

        # 记录原始事件列表和旧摘要，用于计算 dropped_events 和生成新摘要
        original_events = self.events.copy()
        old_summary = self.summary

        # Step 1: 如果未启用锚点感知，直接保留最近N条事件
        if not self.config.enable_anchor_aware:
            self.events = self.events[-keep_recent:]
        else:
            # Step 2: 锚点感知的滑动窗口
            # 2a. 识别锚点位置
            anchor_positions = [
                i for i, event in enumerate(self.events) if self._is_anchor_event(event)
            ]

            # 2b. 确定保留哪些事件
            keep_indices = set()

            # 总是保留最近的事件
            recent_start = max(0, len(self.events) - keep_recent)
            keep_indices.update(range(recent_start, len(self.events)))

            # 保留锚点附近的事件（如果不在最近范围内）
            for pos in anchor_positions:
                if pos < recent_start:
                    buffer_start = max(0, pos - anchor_buffer)
                    buffer_end = min(recent_start, pos + anchor_buffer + 1)
                    keep_indices.update(range(buffer_start, buffer_end))

            # 过滤事件
            keep_indices_sorted = sorted(keep_indices)
            self.events = [self.events[i] for i in keep_indices_sorted]

        # Step 3: 如果保留的事件 token 总数仍超过阈值，继续删除最旧事件
        while self._calc_total_tokens() > self.threshold and len(self.events) > 1:
            self.events.pop(0)
            logger.debug(
                f"保留的事件仍超阈值，继续删除最旧事件，"
                f"当前事件数: {len(self.events)}, token: {self._calc_total_tokens()}"
            )

        # Step 4: 计算 dropped_events 并更新 segment_index
        dropped_events = [e for e in original_events if e not in self.events]

        # Step 5: 更新累积摘要（如果有事件被压缩）
        if dropped_events and self.tape_metadata_mgr:
            new_summary = await self._summarize_with_previous(
                dropped_events,
                old_summary
            )
            if new_summary:
                self.summary = new_summary
                await self.tape_metadata_mgr.update_summary(
                    agent_id=self.agent_id,
                    session_id=self.session_id,
                    summary=new_summary,
                )
                logger.debug(f"Updated cumulative summary for {self.session_id}")

        await self._update_segment_index_for_dropped(dropped_events)

    def get_context_messages(self) -> list[dict]:
        """
        获取历史上下文消息

        从 tape 加载的事件转换为 LLM messages 格式
        验证 tool 消息与 assistant 消息的 tool_calls 配对

        Returns:
            messages列表，可直接用于LLM调用
        """
        messages = []

        # 1. 系统提示（由Agent自己添加，这里不添加）

        # 2. 历史摘要（如果有）
        if self.summary:
            messages.append({"role": "system", "content": f"[历史会话摘要] {self.summary}"})

        # 3. 追踪待处理的 tool_call_ids（来自 assistant 消息）
        pending_tool_call_ids = set()

        # 4. 转换事件为消息，并验证 tool 消息配对
        for event in self.events:
            converted = self.event_to_messages(event)
            for msg in converted:
                # 追踪 assistant 消息中的 tool_calls
                if msg.get("role") == "assistant" and msg.get("tool_calls"):
                    for tc in msg.get("tool_calls", []):
                        pending_tool_call_ids.add(tc.get("id", ""))

                # 仅当 tool_call_id 在待处理列表中时才添加 tool 消息
                if msg.get("role") == "tool":
                    tool_call_id = msg.get("tool_call_id", "")
                    if tool_call_id in pending_tool_call_ids:
                        messages.append(msg)
                        pending_tool_call_ids.remove(tool_call_id)
                    else:
                        # 跳过孤立的 tool 消息（没有匹配的 tool_calls）
                        print(
                            f"Debug: Skipping orphaned tool message with tool_call_id: {tool_call_id}"
                        )
                else:
                    messages.append(msg)

        return messages

    def _calc_total_tokens(self) -> int:
        """计算当前总token数（含 system_prompt、摘要、事件）"""
        # system_prompt token
        system_prompt_tokens = count_tokens(self._system_prompt) if self._system_prompt else 0

        # summary token
        summary_tokens = count_tokens(self.summary) if self.summary else 0

        # events token
        event_tokens = sum(e.get("_tokens", e.get("tokens", 0)) for e in self.events)

        return system_prompt_tokens + summary_tokens + event_tokens

    def _is_anchor_event(self, event: dict) -> bool:
        """
        判断事件是否为锚点

        锚点事件包括：
        - 用户查询 (USER_QUERY)
        - Agent 响应 (RESPONSE, ASSISTANT_RESPONSE)
        - 关键游戏状态变化 (GAME_EVENT: allocate_funds, adjust_tax, etc.)

        Args:
            event: 事件数据

        Returns:
            bool: 是否为锚点事件
        """
        event_type = event.get("type", "")

        # 用户和 Agent 消息总是锚点
        if event_type in ("user_query", "response", "assistant_response"):
            return True

        # 关键游戏状态变化是锚点
        if event_type == "GAME_EVENT":
            payload = event.get("payload", {})
            if isinstance(payload, dict):
                # Check if payload contains game action type
                for action_type in [
                    "allocate_funds",
                    "adjust_tax",
                    "build_irrigation",
                    "recruit_troops",
                    "dispatch_troops",
                ]:
                    if action_type in str(payload):
                        return True

        return False

    async def _update_segment_index_for_dropped(self, dropped_events: list[dict]) -> None:
        """
        V4: Update segment_index in tape_meta.jsonl for dropped events.

        Called during window sliding to record compacted segments.

        Args:
            dropped_events: Events that were dropped from the window
        """
        if not dropped_events or not self.tape_metadata_mgr:
            return

        try:
            # Calculate segment info
            tick = self._extract_tick_from_events(dropped_events)

            # Generate summary for dropped segment
            dropped_summary = await self._summarize_events(dropped_events)

            if not dropped_summary:
                return

            # Calculate absolute positions using window_offset
            # The dropped events were at positions [window_offset, window_offset + len(dropped_events))
            start_position = self._window_offset
            end_position = self._window_offset + len(dropped_events) - 1

            segment_info = {
                "start": start_position,
                "end": end_position,
                "summary": dropped_summary,
                "tick": tick,
            }

            await self.tape_metadata_mgr.update_segment_index(
                agent_id=self.agent_id,
                session_id=self.session_id,
                segment_info=segment_info,
            )

            # Move window offset forward after recording segment
            self._window_offset += len(dropped_events)
            await self.tape_metadata_mgr.update_window_offset(
                agent_id=self.agent_id,
                session_id=self.session_id,
                window_offset=self._window_offset,
            )

            logger.debug(
                f"Updated segment_index for {self.session_id}: "
                f"positions [{start_position}-{end_position}], {len(dropped_events)} events, "
                f"new window_offset: {self._window_offset}"
            )
        except Exception as e:
            logger.warning(f"Failed to update segment_index: {e}")

    async def _summarize_events(self, events: list[dict]) -> str | None:
        """
        Generate a summary for a list of events.

        Args:
            events: List of event dicts

        Returns:
            Summary string or None
        """
        if not events:
            return None

        # Build event summary text
        event_summaries = []
        for event in events:
            event_type = event.get("type", "")
            payload = event.get("payload", {})
            if isinstance(payload, dict):
                query = payload.get("query", "")
                intent = payload.get("intent", "")
                message = payload.get("message", "")
                narrative = payload.get("narrative", "")

                if query:
                    event_summaries.append(f"{event_type}: {query[:50]}")
                elif intent:
                    event_summaries.append(f"{event_type}: {intent}")
                elif message:
                    event_summaries.append(f"{event_type}: {message[:50]}")
                elif narrative:
                    event_summaries.append(f"{event_type}: {narrative[:50]}")
                else:
                    # 对于其他类型，使用工具调用信息
                    if event_type == "tool_result":
                        result = payload.get("result", "")
                        if result:
                            event_summaries.append(f"{event_type}: {str(result)[:50]}")
                    elif event_type == "assistant_response":
                        # 检查是否有 tool_calls
                        if payload.get("tool_calls"):
                            event_summaries.append(f"{event_type}: (带工具调用)")
                        else:
                            response = payload.get("response", "")
                            if response:
                                event_summaries.append(f"{event_type}: {response[:50]}")
                    else:
                        event_summaries.append(f"{event_type}: (事件)")

        if not event_summaries:
            # 如果仍然没有摘要，返回一个简单的统计摘要
            return f"{len(events)} 个事件已被压缩"

        # Use LLM for summary if available
        try:
            prompt = "Summarize these events in 1 sentence (≤100 chars):\n" + "\n".join(
                event_summaries[:10]
            )
            summary = await self.llm.call(
                prompt=prompt,
                system_prompt="You are a summarizer for event logs.",
                temperature=0.3,
                max_tokens=100,
            )
            return summary.strip()[:100] if summary else None
        except Exception as e:
            # Fallback: simple concatenation
            logger.debug(f"LLM summarization failed: {type(e).__name__}: {e}")
            return f"{len(events)} events: {', '.join(event_summaries[:3])}"

    def _extract_tick_from_events(self, events: list[dict]) -> int | None:
        """
        Extract tick value from event list.

        Args:
            events: Event dict list

        Returns:
            First tick value found, or None
        """
        for event in events:
            if tick := event.get("tick"):
                return tick
            # Also check payload
            payload = event.get("payload", {})
            if isinstance(payload, dict) and (tick := payload.get("tick")):
                return tick
        return None

    async def _summarize_with_previous(
        self,
        dropped_events: list[dict],
        previous_summary: str,
    ) -> str | None:
        """
        Generate a cumulative summary by combining previous summary with dropped events.

        Args:
            dropped_events: Events that were dropped from the window
            previous_summary: Previous cumulative summary

        Returns:
            New cumulative summary, or None if no events were dropped
        """
        if not dropped_events:
            return None

        dropped_brief = self._format_events_brief(dropped_events)

        try:
            prompt = f"""请根据以下信息，生成一份累积的对话摘要：

【之前的对话摘要】
{previous_summary if previous_summary else "(这是对话开始，无之前摘要)"}

【刚刚结束的对话】
{dropped_brief}

请生成新的摘要，要求：
1. 整合两部分内容，保持时间线连贯
2. 简洁但保留关键信息
3. 控制在 150 字以内
"""

            new_summary = await self.llm.call(
                prompt=prompt,
                system_prompt="你是历史记录整理员。",
                temperature=0.3,
                max_tokens=200,
            )

            return new_summary.strip()[:200] if new_summary else previous_summary
        except Exception as e:
            logger.debug(f"LLM cumulative summarization failed: {type(e).__name__}: {e}")
            # Fallback: append brief to previous summary
            if previous_summary:
                return f"{previous_summary} | {dropped_brief[:100]}"
            return dropped_brief[:150]

    def _format_events_brief(self, events: list[dict]) -> str:
        """
        Format a list of events into a brief summary.

        Args:
            events: Event dict list

        Returns:
            Brief summary string
        """
        parts = []
        for event in events[:10]:  # 最多 10 个
            event_type = event.get("type", event.get("event_type", ""))
            payload = event.get("payload", event.get("content", {}))
            if isinstance(payload, dict):
                msg = (
                    payload.get("query") or
                    payload.get("message") or
                    payload.get("narrative") or
                    payload.get("intent") or
                    ""
                )
                if msg:
                    parts.append(f"- {event_type}: {msg[:30]}")
                else:
                    parts.append(f"- {event_type}")
            else:
                parts.append(f"- {event_type}: {str(payload)[:30]}")
        return "\n".join(parts) if parts else f"{len(events)} 个事件"
