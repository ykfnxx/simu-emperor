"""ContextManager for sliding window context management."""

import aiofiles
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from simu_emperor.llm.base import LLMProvider


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
    keep_recent_events: int = 20   # 滑动窗口后保留的事件数


class ContextManager:
    """
    管理当前session上下文窗口，从tape加载历史并控制token数量

    SPEC: V3_MEMORY_SYSTEM_SPEC.md §4.3
    """

    def __init__(
        self,
        session_id: str,
        agent_id: str,
        tape_path: Path,
        config: ContextConfig,
        llm_provider: "LLMProvider",
        manifest_index=None
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
        """
        self.session_id = session_id
        self.agent_id = agent_id
        self.tape_path = tape_path
        self.llm = llm_provider
        self.manifest = manifest_index  # 用于刷新session总结
        self.config = config  # 保存 config

        # 初始化max_tokens（如果为None则查询LLM）
        self.max_tokens = config.max_tokens or self._query_llm_context_window()
        self.threshold = int(self.max_tokens * config.threshold_ratio)

        # 窗口状态
        self.events: list[dict] = []  # 当前窗口内的事件（从tape加载）
        self.summary: str = ""         # 历史摘要

    def _query_llm_context_window(self) -> int:
        """查询LLM API获取context window大小"""
        try:
            return self.llm.get_context_window_size()
        except (AttributeError, NotImplementedError):
            return 8192  # 默认值

    async def load_from_tape(self) -> None:
        """
        从tape加载历史事件

        SPEC: V3_MEMORY_SYSTEM_SPEC.md §4.3
        """
        if not self.tape_path.exists():
            return

        try:
            async with aiofiles.open(self.tape_path, "r", encoding="utf-8") as f:
                async for line in f:
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                        self.events.append(event)
                    except json.JSONDecodeError:
                        continue  # Skip invalid lines
        except Exception as e:
            print(f"Warning: Failed to load tape: {e}")

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
        滑动窗口：刷新session总结后，保留最近N条事件

        SPEC: V3_MEMORY_SYSTEM_SPEC.md §4.3
        流程：
        1. 调用manifest刷新本session总结（基于完整tape）
        2. 从manifest读取最新summary
        3. 保留最近N条事件，其余丢弃
        """
        keep = self.config.keep_recent_events

        if len(self.events) <= keep:
            return

        # Step 1: 刷新session总结（基于完整tape）
        if self.manifest:
            try:
                # 调用 ManifestIndex 的 refresh_session_summary 方法
                await self.manifest.refresh_session_summary(
                    session_id=self.session_id,
                    agent_id=self.agent_id,
                    llm_provider=self.llm,
                    tape_path=self.tape_path
                )

                # Step 2: 从manifest读取最新summary
                summary = await self.manifest.get_session_summary(self.session_id, self.agent_id)
                self.summary = summary or ""
            except Exception as e:
                print(f"Warning: Failed to refresh summary: {e}")

        # Step 3: 保留最近N条事件
        self.events = self.events[-keep:]

    def build_messages(self) -> list[dict]:
        """
        组装为LLM messages格式

        Returns:
            messages列表，可直接用于LLM调用
        """
        messages = []

        # 1. 系统提示（由Agent自己添加，这里不添加）

        # 2. 历史摘要（如果有）
        if self.summary:
            messages.append({
                "role": "system",
                "content": f"[历史会话摘要] {self.summary}"
            })

        # 3. 窗口内事件
        for event in self.events:
            messages.extend(self._event_to_messages(event))

        return messages

    def _calc_total_tokens(self) -> int:
        """计算当前总token数（含摘要）"""
        event_tokens = sum(e.get("_tokens", e.get("tokens", 0)) for e in self.events)
        summary_tokens = count_tokens(self.summary) if self.summary else 0
        return event_tokens + summary_tokens

    def _event_to_messages(self, event: dict) -> list[dict]:
        """
        将事件转换为messages格式

        SPEC: V3_MEMORY_SYSTEM_SPEC.md §4.3
        """
        event_type = event.get("event_type", event.get("type", "UNKNOWN"))
        content = event.get("content", {})

        if event_type in ("USER_QUERY", "user_query"):
            query = content.get("query") if isinstance(content, dict) else content
            return [{"role": "user", "content": str(query)}]
        elif event_type in ("AGENT_RESPONSE", "agent_response"):
            response = content.get("response") if isinstance(content, dict) else content
            return [{"role": "assistant", "content": str(response)}]
        elif event_type in ("TOOL_CALL", "tool_call"):
            # 工具调用作为system消息
            tool = content.get("tool") if isinstance(content, dict) else content
            return [{"role": "system", "content": f"[调用工具] {tool}"}]
        elif event_type in ("TOOL_RESULT", "tool_result"):
            # 工具结果不添加到context（避免token过多）
            return []
        else:
            # 其他事件类型
            return [{"role": "system", "content": f"[{event_type}] {str(content)}"}]
