"""ContextManager for sliding window context management."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from simu_emperor.common import FileOperationsHelper

if TYPE_CHECKING:
    from simu_emperor.llm.base import LLMProvider
    from simu_emperor.memory.tape_metadata import TapeMetadataManager

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
    V4: Updates tape_meta.jsonl segment_index during compaction
    """

    def __init__(
        self,
        session_id: str,
        agent_id: str,
        tape_path: Path,
        config: ContextConfig,
        llm_provider: "LLMProvider",
        manifest_index=None,
        session_manager=None,
        tape_metadata_mgr: "TapeMetadataManager | None" = None,
    ):
        """
        Initialize ContextManager.

        Args:
            session_id: Session identifier
            agent_id: Agent identifier
            tape_path: Path to tape.jsonl file
            config: Context configuration
            llm_provider: LLM provider for summarization
            manifest_index: Optional ManifestIndex for summary storage
            session_manager: Optional SessionManager for ancestor loading
            tape_metadata_mgr: V4 TapeMetadataManager for segment_index updates
        """
        self.session_id = session_id
        self.agent_id = agent_id
        self.tape_path = tape_path
        self.llm = llm_provider
        self.manifest = manifest_index
        self.config = config
        self.session_manager = session_manager
        self.tape_metadata_mgr = tape_metadata_mgr  # V4

        # 初始化max_tokens（如果为None则查询LLM）
        self.max_tokens = config.max_tokens or self._query_llm_context_window()
        self.threshold = int(self.max_tokens * config.threshold_ratio)

        # 窗口状态
        self.events: list[dict] = []  # 当前窗口内的事件（从tape加载）
        self.summary: str = ""  # 历史摘要

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
        elif event_type == EventType.COMMAND:
            command = payload.get("command", "") if isinstance(payload, dict) else ""
            if command:
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
        elif event_type == EventType.CHAT:
            message = payload.get("message", "") if isinstance(payload, dict) else ""
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
            # RESPONSE 事件需要区分来源：
            # - 如果 src 是当前 agent，则是自己的响应 → "assistant"
            # - 如果 src 是其他 agent，则是收到的消息 → "user"
            narrative = payload.get("narrative") if isinstance(payload, dict) else payload
            src = event.get("src", "")

            # 检查是否是当前 agent 的响应
            if src == f"agent:{self.agent_id}":
                # 自己的响应 → assistant
                return [{"role": "assistant", "content": str(narrative)}]
            else:
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
        events = await FileOperationsHelper.read_jsonl_file(self.tape_path)
        self.events.extend(events)

        if include_ancestors and self.session_manager:
            ancestors = self.session_manager.get_parent_chain(self.session_id)
            for ancestor in ancestors:
                ancestor_events = await self._load_session_events(ancestor.session_id)
                self.events.extend(ancestor_events)

            self.events.sort(key=lambda e: e.get("timestamp", ""))

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

    def add_event(self, event: dict, tokens: int) -> bool:
        """
        添加事件到上下文

        Args:
            event: 事件数据
            tokens: 事件的token数

        Returns:
            bool: 是否需要滑动窗口
        """
        event["_tokens"] = tokens

        # 先添加事件
        self.events.append(event)

        # 计算添加后的总token
        current_tokens = self._calc_total_tokens()
        if current_tokens > self.threshold:
            return True  # 需要滑动

        return False

    async def slide_window(self) -> None:
        """
        锚点感知的滑动窗口

        策略：
        1. 识别窗口内所有锚点
        2. 保留最近 N 个事件
        3. 额外保留锚点附近 ±K 个事件
        4. 刷新被丢弃事件的摘要

        SPEC: V3_MEMORY_SYSTEM_SPEC.md §4.3
        V4: Updates tape_meta.jsonl segment_index
        """
        keep_recent = self.config.keep_recent_events
        anchor_buffer = self.config.anchor_buffer

        if len(self.events) <= keep_recent:
            return

        # Track dropped events for V4 segment_index update
        original_count = len(self.events)

        # Step 1: 刷新session总结（基于完整tape）
        if self.manifest:
            try:
                # 调用 ManifestIndex 的 refresh_session_summary 方法
                await self.manifest.refresh_session_summary(
                    session_id=self.session_id,
                    agent_id=self.agent_id,
                    llm_provider=self.llm,
                    tape_path=self.tape_path,
                )

                # Step 2: 从manifest读取最新summary
                summary = await self.manifest.get_session_summary(self.session_id, self.agent_id)
                self.summary = summary or ""
            except Exception as e:
                print(f"Warning: Failed to refresh summary: {e}")

        # Step 3: 如果未启用锚点感知，直接保留最近N条事件
        if not self.config.enable_anchor_aware:
            dropped_events = self.events[:-keep_recent]
            self.events = self.events[-keep_recent:]
            await self._update_segment_index_for_dropped(dropped_events)
            return

        # Step 4: 锚点感知的滑动窗口
        # 4a. 识别锚点位置
        anchor_positions = [
            i for i, event in enumerate(self.events) if self._is_anchor_event(event)
        ]

        # 4b. 确定保留哪些事件
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

        # Step 5: 过滤事件
        keep_indices_sorted = sorted(keep_indices)

        # Track dropped events for V4 segment_index update
        dropped_indices = set(range(original_count)) - set(keep_indices_sorted)
        dropped_events = [self.events[i] for i in sorted(dropped_indices)]

        self.events = [self.events[i] for i in keep_indices_sorted]

        # V4: Update segment_index in tape_meta.jsonl
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
        """计算当前总token数（含摘要）"""
        event_tokens = sum(e.get("_tokens", e.get("tokens", 0)) for e in self.events)
        summary_tokens = count_tokens(self.summary) if self.summary else 0
        return event_tokens + summary_tokens

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
            # Find position range of dropped events
            dropped_positions = []
            for event in dropped_events:
                # Position in tape is inferred from event order
                # For simplicity, we use event index tracking
                pass

            # Calculate segment info
            tick = self._extract_tick_from_events(dropped_events)

            # Generate summary for dropped segment
            dropped_summary = await self._summarize_events(dropped_events)

            if not dropped_summary:
                return

            # Get start/end positions from events
            # Note: In a real implementation, we'd track absolute positions
            # For V4, we use event count as proxy
            segment_info = {
                "start": 0,  # Placeholder - would need absolute position tracking
                "end": len(dropped_events) - 1,
                "summary": dropped_summary,
                "tick": tick,
            }

            await self.tape_metadata_mgr.update_segment_index(
                agent_id=self.agent_id,
                session_id=self.session_id,
                segment_info=segment_info,
            )

            logger.debug(f"Updated segment_index for {self.session_id}: {len(dropped_events)} events")
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
                if query:
                    event_summaries.append(f"{event_type}: {query[:50]}")
                elif intent:
                    event_summaries.append(f"{event_type}: {intent}")

        if not event_summaries:
            return None

        # Use LLM for summary if available
        try:
            prompt = f"Summarize these events in 1 sentence (≤100 chars):\n" + "\n".join(event_summaries[:10])
            summary = await self.llm.call(
                prompt=prompt,
                system_prompt="You are a summarizer for event logs.",
                temperature=0.3,
                max_tokens=100,
            )
            return summary.strip()[:100] if summary else None
        except Exception:
            # Fallback: simple concatenation
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
