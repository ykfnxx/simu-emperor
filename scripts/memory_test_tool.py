#!/usr/bin/env python3
"""记忆模块测试工具 - 专注于 compact 和检索能力.

这是一个交互式测试工具，不需要启动完整的 Agent/Engine。
可以直接测试记忆模块的核心功能：
    1. 写入事件到 tape
    2. 触发自动 compact
    3. 测试检索功能

用法:
    # 启动交互式测试
    uv run python scripts/memory_test_tool.py

    # 在代码中使用
    from scripts.memory_test_tool import MemoryTestTool
    tool = MemoryTestTool()
    await tool.init()
    await tool.add_event(...)
    await tool.test_search(...)
"""

import asyncio
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from simu_emperor.memory import (
    TapeMetadataManager,
    TapeMetadataIndex,
    SegmentSearcher,
    TwoLevelSearcher,
    QueryParser,
    ContextManager,
    ContextConfig,
    count_tokens,
)
from simu_emperor.llm.mock import MockProvider


@dataclass
class LLMCall:
    """记录 LLM 调用，用于用户交互式响应."""

    prompt: str
    system_prompt: str = ""
    response_placeholder: str | None = None
    response: str | None = None

    def format_for_display(self) -> str:
        """格式化显示给用户."""
        lines = [
            "\n" + "=" * 60,
            "🤖 LLM 调用请求",
            "=" * 60,
        ]
        if self.system_prompt:
            lines.extend(["\n[System Prompt]", self.system_prompt])
        lines.extend(["\n[User Prompt]", self.prompt])
        if self.response_placeholder:
            lines.extend(["\n[建议响应]", self.response_placeholder])
        lines.append("\n" + "-" * 60)
        return "\n".join(lines)


@dataclass
class InteractiveLLM:
    """交互式 LLM Provider - 记录所有调用，允许用户注入响应."""

    pending_calls: list[LLMCall] = field(default_factory=list)
    call_count: int = 0
    auto_mode: bool = False  # True = 自动使用 MockProvider，False = 等待用户输入

    def __post_init__(self):
        self._mock = MockProvider()

    async def call(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """记录 LLM 调用."""
        self.call_count += 1
        call = LLMCall(
            prompt=prompt,
            system_prompt=system_prompt,
        )

        if self.auto_mode:
            # 自动模式：使用 mock 响应
            response = await self._mock.call(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            call.response = response
            self.pending_calls.append(call)
            return response
        else:
            # 交互模式：记录调用，等待用户响应
            self.pending_calls.append(call)
            raise NeedsUserResponse(call_index=len(self.pending_calls) - 1)

    async def respond_to(self, call_index: int, response: str) -> None:
        """响应对应的 LLM 调用."""
        if 0 <= call_index < len(self.pending_calls):
            self.pending_calls[call_index].response = response

    def get_context_window_size(self) -> int:
        """返回上下文窗口大小."""
        return 8192


class NeedsUserResponse(Exception):
    """需要用户响应 LLM 调用时抛出."""

    def __init__(self, call_index: int):
        self.call_index = call_index


@dataclass
class MemoryTestTool:
    """记忆模块测试工具.

    提供简化的 API 来测试记忆模块的核心功能：
    - compact: 滑动窗口压缩
    - search: 两级检索
    """

    # 配置
    agent_id: str = "test_agent"
    session_id: str = "test_session"
    memory_dir: Path | None = None
    auto_llm: bool = False  # True = 自动模式，False = 交互模式

    # 内部组件
    llm: InteractiveLLM = field(default_factory=InteractiveLLM)
    memory_dir_path: Path = field(init=False)

    # 核心组件
    metadata_mgr: TapeMetadataManager = field(init=False)
    metadata_index: TapeMetadataIndex = field(init=False)
    segment_searcher: SegmentSearcher = field(init=False)
    two_level_searcher: TwoLevelSearcher = field(init=False)
    query_parser: QueryParser = field(init=False)
    context_manager: ContextManager = field(init=False)
    tape_path: Path = field(init=False)

    # 状态
    event_count: int = 0
    compact_count: int = 0

    def __post_init__(self):
        if self.memory_dir is None:
            # 使用临时目录
            import tempfile
            self.memory_dir_path = Path(tempfile.mkdtemp(prefix="memory_test_"))
        else:
            self.memory_dir_path = Path(self.memory_dir)

        self.llm.auto_mode = self.auto_llm

    async def init(self):
        """初始化测试工具."""
        memory_dir = self.memory_dir_path / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)

        # 初始化组件
        self.metadata_mgr = TapeMetadataManager(memory_dir=memory_dir)
        self.metadata_index = TapeMetadataIndex(memory_dir=memory_dir)
        self.segment_searcher = SegmentSearcher(memory_dir=memory_dir)
        self.two_level_searcher = TwoLevelSearcher(
            tape_metadata_index=self.metadata_index,
            segment_searcher=self.segment_searcher,
        )
        self.query_parser = QueryParser(llm_provider=self.llm)

        # 初始化 tape
        tape_dir = memory_dir / "agents" / self.agent_id / "sessions" / self.session_id
        tape_dir.mkdir(parents=True, exist_ok=True)
        self.tape_path = tape_dir / "tape.jsonl"

        # 初始化 ContextManager
        config = ContextConfig(
            max_tokens=1000,  # 小阈值便于测试 compact
            threshold_ratio=0.95,
            keep_recent_events=5,  # 保留少量事件
        )
        self.context_manager = ContextManager(
            session_id=self.session_id,
            agent_id=self.agent_id,
            tape_path=self.tape_path,
            config=config,
            llm_provider=self.llm,
            tape_metadata_mgr=self.metadata_mgr,
        )

        # 创建初始 metadata entry
        await self._create_metadata_entry()

        print("✅ 测试工具初始化完成")
        print(f"   内存目录: {self.memory_dir_path}")
        print(f"   Tape 路径: {self.tape_path}")
        print(f"   自动 LLM: {self.auto_llm}")

    async def _create_metadata_entry(self):
        """创建 metadata entry."""
        from unittest.mock import MagicMock
        from simu_emperor.event_bus.event import Event

        mock_event = MagicMock(spec=Event)
        mock_event.type = "command"
        mock_event.payload = {"query": "测试会话"}
        mock_event.session_id = self.session_id

        await self.metadata_mgr.append_or_update_entry(
            agent_id=self.agent_id,
            session_id=self.session_id,
            first_event=mock_event,
            llm=self.llm,
            current_tick=0,
        )

    async def add_event(
        self,
        event_type: str,
        query: str,
        tick: int | None = None,
        auto_compact: bool = True,
    ) -> dict[str, Any]:
        """添加事件到 tape.

        Args:
            event_type: 事件类型 (user_query, response, game_event, etc.)
            query: 事件内容
            tick: 游戏回合数
            auto_compact: 是否自动触发 compact

        Returns:
            事件信息和状态
        """
        self.event_count += 1
        if tick is None:
            tick = self.event_count

        event = {
            "event_id": f"evt_{self.event_count:03d}",
            "type": event_type,
            "payload": {"query": query},
            "timestamp": datetime.now().isoformat(),
            "tick": tick,
        }

        # 计算 tokens
        event_text = json.dumps(event, ensure_ascii=False)
        tokens = count_tokens(event_text)

        # 写入 tape
        with open(self.tape_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        # 添加到 ContextManager
        need_compact = self.context_manager.add_event(event, tokens)

        result = {
            "event": event,
            "tokens": tokens,
            "total_tokens": self.context_manager._calc_total_tokens(),
            "threshold": self.context_manager.threshold,
            "need_compact": need_compact,
            "event_count": self.event_count,
        }

        # 自动 compact
        if auto_compact and need_compact:
            await self.compact()

        return result

    async def compact(self) -> dict[str, Any]:
        """手动触发 compact.

        Returns:
            compact 操作的状态信息
        """
        before_count = len(self.context_manager.events)
        before_tokens = self.context_manager._calc_total_tokens()

        try:
            await self.context_manager.slide_window()
        except NeedsUserResponse as e:
            return {
                "status": "needs_llm",
                "call_index": e.call_index,
                "message": "Compact 需要 LLM 生成摘要，请调用 respond_to_llm()",
            }

        after_count = len(self.context_manager.events)
        after_tokens = self.context_manager._calc_total_tokens()

        self.compact_count += 1

        return {
            "status": "success",
            "before": {"events": before_count, "tokens": before_tokens},
            "after": {"events": after_count, "tokens": after_tokens},
            "dropped": before_count - after_count,
            "compact_count": self.compact_count,
        }

    async def respond_to_llm(self, call_index: int, response: str) -> None:
        """响应对应的 LLM 调用."""
        await self.llm.respond_to(call_index, response)

    def get_pending_llm_calls(self) -> list[LLMCall]:
        """获取待响应的 LLM 调用."""
        return [c for c in self.llm.pending_calls if c.response is None]

    def get_status(self) -> dict[str, Any]:
        """获取当前状态."""
        # 读取 tape 文件
        tape_events = []
        if self.tape_path.exists():
            with open(self.tape_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        tape_events.append(json.loads(line))

        # 读取 metadata
        metadata_path = self.memory_dir_path / "memory" / "agents" / self.agent_id / "tape_meta.jsonl"
        metadata_entries = []
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        metadata_entries.append(json.loads(line))

        return {
            "tape_events": len(tape_events),
            "context_events": len(self.context_manager.events),
            "summary": self.context_manager.summary[:100] + "..." if self.context_manager.summary else "",
            "total_tokens": self.context_manager._calc_total_tokens(),
            "threshold": self.context_manager.threshold,
            "metadata_entries": len(metadata_entries),
            "pending_llm_calls": len(self.get_pending_llm_calls()),
        }

    def print_status(self):
        """打印当前状态."""
        status = self.get_status()

        print("\n" + "=" * 50)
        print("📊 当前状态")
        print("=" * 50)
        print(f"  Tape 事件总数: {status['tape_events']}")
        print(f"  上下文事件数: {status['context_events']}")
        print(f"  总 Tokens: {status['total_tokens']} / {status['threshold']}")
        print(f"  摘要: {status['summary']}")
        print(f"  Metadata 条目: {status['metadata_entries']}")
        print(f"  待处理 LLM 调用: {status['pending_llm_calls']}")
        print("=" * 50)

    async def test_search(self, query: str) -> dict[str, Any]:
        """测试检索功能.

        Args:
            query: 搜索查询

        Returns:
            检索结果
        """
        try:
            # 解析查询
            parse_result = await self.query_parser.parse(query)

            # 搜索
            results = await self.two_level_searcher.search(
                query=parse_result.structured,
                agent_id=self.agent_id,
                max_results=5,
            )

            return {
                "query": query,
                "parsed": parse_result,
                "result_count": len(results),
                "results": results,
            }
        except NeedsUserResponse as e:
            return {
                "status": "needs_llm",
                "call_index": e.call_index,
                "message": "搜索需要 LLM 解析查询",
            }

    def print_search_results(self, result: dict):
        """打印搜索结果."""
        if result.get("status") == "needs_llm":
            print(f"⏸️  需要 LLM 响应 (call_index={result['call_index']})")
            return

        print(f"\n🔍 搜索: '{result['query']}'")
        print(f"   找到 {result['result_count']} 个片段:\n")

        for i, segment in enumerate(result.get("results", [])):
            print(f"  [{i+1}] Session: {segment.session_id}")
            print(f"      事件数: {len(segment.events)}")
            if segment.events:
                first_evt = segment.events[0]
                print(f"      首个事件: {first_evt.get('type')}: {first_evt.get('payload', {}).get('query', '')[:50]}")
            print()

    def cleanup(self):
        """清理测试目录."""
        import shutil
        if self.memory_dir_path.exists():
            shutil.rmtree(self.memory_dir_path)
            print(f"🧹 已清理: {self.memory_dir_path}")


# ============================================================================
# 交互式命令行界面
# ============================================================================

class MemoryTestCLI:
    """交互式命令行界面."""

    def __init__(self):
        self.tool: MemoryTestTool | None = None
        self.running = True

    async def run(self):
        """运行交互式界面."""
        print("🧪 记忆模块测试工具")
        print("=" * 50)
        print("命令:")
        print("  init [auto]     - 初始化 (auto=自动 LLM)")
        print("  add <query>     - 添加事件")
        print("  compact         - 手动触发 compact")
        print("  search <query>  - 搜索")
        print("  status          - 显示状态")
        print("  respond <idx> <response> - 响应 LLM 调用")
        print("  pending         - 显示待处理的 LLM 调用")
        print("  quit            - 退出")
        print("=" * 50)

        while self.running:
            try:
                line = await asyncio.to_thread(input, "\n> ")
                if not line.strip():
                    continue

                parts = line.split(maxsplit=1)
                cmd = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""

                await self.handle_command(cmd, args)
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\n使用 'quit' 退出")
            except Exception as e:
                print(f"❌ 错误: {e}")

    async def handle_command(self, cmd: str, args: str):
        """处理命令."""
        if cmd == "init":
            auto_llm = args.strip().lower() == "auto"
            self.tool = MemoryTestTool(auto_llm=auto_llm)
            try:
                await self.tool.init()
            except NeedsUserResponse as e:
                await self.handle_llm_request(e)

        elif cmd == "add":
            if not self.tool:
                print("❌ 请先运行 init")
                return
            result = await self.tool.add_event("user_query", args)
            print(f"✅ 添加事件 (tokens={result['tokens']}, total={result['total_tokens']}/{result['threshold']})")
            if result.get('need_compact'):
                print("   📦 已自动触发 compact")

        elif cmd == "compact":
            if not self.tool:
                print("❌ 请先运行 init")
                return
            result = await self.tool.compact()
            if result['status'] == 'success':
                print(f"✅ Compact 完成: {result['before']['events']} → {result['after']['events']} 事件")
                print(f"   Tokens: {result['before']['tokens']} → {result['after']['tokens']}")
            elif result['status'] == 'needs_llm':
                print("⏸️  需要 LLM 响应，使用 'pending' 查看详情")

        elif cmd == "search":
            if not self.tool:
                print("❌ 请先运行 init")
                return
            result = await self.tool.test_search(args)
            self.tool.print_search_results(result)

        elif cmd == "status":
            if not self.tool:
                print("❌ 请先运行 init")
                return
            self.tool.print_status()

        elif cmd == "pending":
            if not self.tool:
                print("❌ 请先运行 init")
                return
            calls = self.tool.get_pending_llm_calls()
            if not calls:
                print("✅ 没有待处理的 LLM 调用")
            else:
                for i, call in enumerate(calls):
                    print(f"\n[调用 #{i}]")
                    print(call.format_for_display())

        elif cmd == "respond":
            if not self.tool:
                print("❌ 请先运行 init")
                return
            parts = args.split(maxsplit=1)
            if len(parts) < 2:
                print("❌ 用法: respond <index> <response>")
                return
            idx = int(parts[0])
            response = parts[1]
            await self.tool.respond_to_llm(idx, response)
            print(f"✅ 已响应调用 #{idx}")

        elif cmd in ("quit", "exit", "q"):
            self.running = False
            if self.tool:
                self.tool.cleanup()

        else:
            print(f"❌ 未知命令: {cmd}")

    async def handle_llm_request(self, exc: NeedsUserResponse):
        """处理 LLM 请求."""
        print(f"\n⏸️  需要 LLM 响应 (调用 #{exc.call_index})")
        call = self.tool.llm.pending_calls[exc.call_index]
        print(call.format_for_display())
        print("\n请输入响应 (或输入 'skip' 跳过):")

        try:
            response = await asyncio.to_thread(input, "> ")
            if response.lower() != "skip":
                await self.tool.respond_to_llm(exc.call_index, response)
        except (EOFError, KeyboardInterrupt):
            print("\n跳过")


async def main():
    """主函数."""
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "auto":
        # 自动模式演示
        print("🤖 自动模式演示\n")

        tool = MemoryTestTool(auto_llm=True)
        await tool.init()

        # 添加事件
        queries = [
            "调整直隶省税收",
            "查询国库状况",
            "拨付赈灾款项",
            "任免官员",
            "修建水利",
            "招募士兵",
            "调整商业税率",
            "处理奏折",
            "接见使臣",
            "视察军营",
        ]

        for q in queries:
            result = await tool.add_event("user_query", q)
            print(f"  添加: {q} (tokens={result['tokens']}, total={result['total_tokens']})")

        print("\n📊 Compact 触发次数:", tool.compact_count)

        # 测试搜索
        result = await tool.test_search("我之前做过什么税收相关的操作?")
        tool.print_search_results(result)

        tool.print_status()
        tool.cleanup()

    else:
        # 交互模式
        cli = MemoryTestCLI()
        await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
