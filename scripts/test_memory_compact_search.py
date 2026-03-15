#!/usr/bin/env python3
"""记忆模块 Compact 和检索专项测试.

专注于测试：
1. 滑动窗口 compact 机制
2. segment_index 更新
3. 两级检索功能

用法:
    # 完整测试（自动 LLM）
    uv run python scripts/test_memory_compact_search.py

    # 指定测试目录（保存结果用于分析）
    MEMORY_TEST_DIR=./test_memory_output uv run python scripts/test_memory_compact_search.py
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

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
from unittest.mock import MagicMock
from simu_emperor.event_bus.event import Event
from simu_emperor.llm.mock import MockProvider


class MemoryCompactSearchTest:
    """记忆模块 Compact 和检索测试."""

    def __init__(self, output_dir: str | None = None):
        if output_dir:
            self.output_dir = Path(output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.memory_dir = self.output_dir / "memory"
        else:
            import tempfile
            self.memory_dir = Path(tempfile.mkdtemp(prefix="memory_test_"))
            self.output_dir = None

        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.llm = MockProvider()

        # 测试配置
        self.agent_id = "test_agent"
        self.session_id = "test_session"

    def print(self, *args, **kwargs):
        """打印输出."""
        print(*args, **kwargs)
        if self.output_dir:
            with open(self.output_dir / "test_log.txt", "a", encoding="utf-8") as f:
                print(*args, **kwargs, file=f)

    def print_section(self, title: str):
        """打印分节标题."""
        self.print("\n" + "=" * 60)
        self.print(f"  {title}")
        self.print("=" * 60)

    async def setup(self):
        """设置测试环境."""
        self.print_section("1. 初始化测试环境")

        # 初始化组件
        self.metadata_mgr = TapeMetadataManager(memory_dir=self.memory_dir)
        self.metadata_index = TapeMetadataIndex(memory_dir=self.memory_dir)
        self.segment_searcher = SegmentSearcher(memory_dir=self.memory_dir)
        self.two_level_searcher = TwoLevelSearcher(
            tape_metadata_index=self.metadata_index,
            segment_searcher=self.segment_searcher,
        )
        self.query_parser = QueryParser(llm_provider=self.llm)

        # 创建 tape 路径
        tape_dir = self.memory_dir / "agents" / self.agent_id / "sessions" / self.session_id
        tape_dir.mkdir(parents=True, exist_ok=True)
        self.tape_path = tape_dir / "tape.jsonl"

        # 创建 metadata entry
        await self._create_metadata_entry()

        self.print("✅ 测试环境初始化完成")
        self.print(f"   内存目录: {self.memory_dir}")
        self.print(f"   Tape 路径: {self.tape_path}")

    async def _create_metadata_entry(self):
        """创建 metadata entry."""
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

    async def test_compact_mechanism(self):
        """测试 Compact 机制."""
        self.print_section("2. 测试 Compact 机制")

        # 配置 ContextManager（小阈值便于测试）
        config = ContextConfig(
            max_tokens=300,  # 更小的阈值确保触发 compact
            threshold_ratio=0.95,
            keep_recent_events=3,  # 保留更少，使 compact 效果更明显
            enable_anchor_aware=False,  # 禁用锚点感知，简单保留最近 N 个事件
        )

        context_mgr = ContextManager(
            session_id=self.session_id,
            agent_id=self.agent_id,
            tape_path=self.tape_path,
            config=config,
            llm_provider=self.llm,
            tape_metadata_mgr=self.metadata_mgr,
        )

        # 添加事件直到触发 compact
        test_queries = [
            ("第1次", "调整直隶省税收至5%"),
            ("第2次", "拨付赈灾款项1000两"),
            ("第3次", "任免户部尚书"),
            ("第4次", "修建黄河水利"),
            ("第5次", "招募士兵500人"),
            ("第6次", "调整商业税率"),  # 这个可能会触发 compact
            ("第7次", "处理边关奏折"),
            ("第8次", "接见外国使臣"),
        ]

        self.print(f"\n配置: max_tokens={config.max_tokens}, threshold={int(config.max_tokens * config.threshold_ratio)}")
        self.print(f"      keep_recent_events={config.keep_recent_events}\n")

        total_added = 0
        compact_triggered = False

        for label, query in test_queries:
            event = {
                "event_id": f"evt_{total_added + 1:03d}",
                "type": "user_query",
                "payload": {"query": query},
                "timestamp": datetime.now().isoformat(),
                "tick": total_added + 1,
            }

            # 写入 tape
            with open(self.tape_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

            # 计算 tokens
            tokens = count_tokens(json.dumps(event, ensure_ascii=False))

            # 添加到 ContextManager
            need_compact = context_mgr.add_event(event, tokens)
            total_added += 1

            status = f"  {label}: {query} (tokens={tokens}, total={context_mgr._calc_total_tokens()})"
            if need_compact:
                status += " ⚠️  需要compact!"
                compact_triggered = True

            self.print(status)

            # 如果需要 compact，执行 compact
            if need_compact:
                self.print("\n  📦 执行 Compact...")
                before = len(context_mgr.events)
                before_tokens = context_mgr._calc_total_tokens()
                self.print(f"     前: {before} 事件, {before_tokens} tokens")

                # 打印锚点信息
                anchor_positions = [i for i, e in enumerate(context_mgr.events) if context_mgr._is_anchor_event(e)]
                self.print(f"     锚点位置: {anchor_positions}")

                await context_mgr.slide_window()

                after = len(context_mgr.events)
                after_tokens = context_mgr._calc_total_tokens()
                self.print(f"     后: {after} 事件, {after_tokens} tokens")
                self.print()

        # 检查 segment_index
        await self._check_segment_index()

        return compact_triggered

    async def _check_segment_index(self):
        """检查 segment_index 更新."""
        self.print("📋 检查 segment_index 更新:")

        metadata_path = self.memory_dir / "agents" / self.agent_id / "tape_meta.jsonl"
        if not metadata_path.exists():
            self.print("   ⚠️  tape_meta.jsonl 不存在")
            return

        with open(metadata_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    self.print(f"   Session: {entry.get('session_id')}")
                    segment_index = entry.get('segment_index', [])
                    if segment_index:
                        self.print(f"   Segment 条目数: {len(segment_index)}")
                        for i, seg in enumerate(segment_index):
                            self.print(f"     [{i}] 位置 {seg['start']}-{seg['end']}, tick={seg['tick']}")
                            self.print(f"         摘要: {seg['summary']}")
                    else:
                        self.print("   ⚠️  segment_index 为空")

    async def test_search_functionality(self):
        """测试检索功能."""
        self.print_section("3. 测试检索功能")

        # 创建多个 session 测试跨会话检索
        # 注意：title 需要包含搜索关键词，因为 Level 1 搜索基于 title 匹配
        sessions = {
            "session_tax": (["调整税收", "查询税收情况", "减免税收政策"], "税收调整事务"),
            "session_military": (["招募士兵500人", "征召民夫运输", "边关战事"], "招募士兵征召民夫边关军事"),
            "session_admin": (["任免户部尚书", "处理边关奏折", "接见外国使臣"], "任免官员处理奏折接见行政"),
        }

        for session_id, (queries, title) in sessions.items():
            await self._create_session_with_events(session_id, queries, title)

        # 测试检索
        test_queries = [
            ("税收相关", ["税收"]),
            ("军事操作", ["士兵", "征召"]),
            ("行政事务", ["任免", "奏折"]),
        ]

        for query_desc, action_keywords in test_queries:
            self.print(f"\n🔍 搜索: {query_desc}")

            # 创建结构化查询 - 使用实际事件中出现的关键词
            from simu_emperor.memory.models import StructuredQuery

            structured_query = StructuredQuery(
                raw_query=query_desc,
                intent="query_history",
                entities={"action": action_keywords, "target": [], "time": ""},
                scope="cross_session",
                depth="tape",
            )

            results = await self.two_level_searcher.search(
                query=structured_query,
                agent_id=self.agent_id,
                max_results=5,
            )

            self.print(f"   找到 {len(results)} 个片段:")
            for i, segment in enumerate(results[:3]):  # 只显示前3个
                self.print(f"     [{i+1}] Session: {segment.session_id}, 事件数: {len(segment.events)}")

    async def _create_session_with_events(self, session_id: str, queries: list[str], title: str):
        """创建带事件的测试 session."""
        # 创建 metadata entry，使用自定义 title（确保包含关键词）
        mock_event = MagicMock(spec=Event)
        mock_event.type = "command"
        mock_event.payload = {"query": queries[0]}
        mock_event.session_id = session_id

        # 创建 entry 并手动设置 title
        await self.metadata_mgr.append_or_update_entry(
            agent_id=self.agent_id,
            session_id=session_id,
            first_event=mock_event,
            llm=self.llm,
            current_tick=0,
        )

        # 手动更新 title
        metadata_path = self.memory_dir / "agents" / self.agent_id / "tape_meta.jsonl"
        entries = []
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        if entry.get("session_id") == session_id:
                            entry["title"] = title
                        entries.append(entry)

            # 写回
            with open(metadata_path, "w", encoding="utf-8") as f:
                for entry in entries:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # 创建 tape 文件
        tape_dir = self.memory_dir / "agents" / self.agent_id / "sessions" / session_id
        tape_dir.mkdir(parents=True, exist_ok=True)
        tape_path = tape_dir / "tape.jsonl"

        events = []
        for i, query in enumerate(queries):
            events.append({
                "event_id": f"evt_{i:03d}",
                "type": "user_query",
                "payload": {"query": f"{query}操作"},
                "timestamp": datetime.now().isoformat(),
                "tick": i,
            })

        with open(tape_path, "w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

        self.print(f"   创建 session '{session_id}': {len(events)} 个事件 (title: {title})")

    async def test_token_counting(self):
        """测试 Token 计数."""
        self.print_section("4. 测试 Token 计数")

        test_strings = [
            ("短文本", "你好"),
            ("中文", "这是一段中文文本，用于测试 token 计数功能。"),
            ("英文", "This is an English text for testing token counting."),
            ("混合", "中英文 mixed text 测试 test."),
            ("JSON", json.dumps({"query": "调整税收", "province": "直隶"}, ensure_ascii=False)),
        ]

        for label, text in test_strings:
            tokens = count_tokens(text)
            self.print(f"  {label}: {text[:30]}... → {tokens} tokens")

    async def run_all_tests(self):
        """运行所有测试."""
        start_time = datetime.now()

        self.print("🧪 记忆模块 Compact 和检索专项测试")
        self.print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            await self.setup()
            await self.test_compact_mechanism()
            await self.test_search_functionality()
            await self.test_token_counting()

            self.print_section("测试完成")
            duration = (datetime.now() - start_time).total_seconds()
            self.print(f"耗时: {duration:.2f} 秒")

            if self.output_dir:
                self.print(f"\n📁 测试结果保存在: {self.output_dir}")
                self.print("   - tape_meta.jsonl: 元数据索引")
                self.print("   - test_log.txt: 测试日志")
                self.print("   - memory/: 完整内存目录")

        except Exception as e:
            self.print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """主函数."""
    import os
    output_dir = os.environ.get("MEMORY_TEST_DIR")
    test = MemoryCompactSearchTest(output_dir=output_dir)
    await test.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
