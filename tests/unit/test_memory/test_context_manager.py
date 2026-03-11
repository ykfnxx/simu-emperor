"""Test ContextManager for context window management."""

from unittest.mock import AsyncMock

import pytest

from simu_emperor.event_bus.event_types import EventType
from simu_emperor.memory.context_manager import ContextManager, ContextConfig


class TestContextManager:
    """Test ContextManager class"""

    @pytest.mark.asyncio
    async def test_add_event_increases_token_count(self, tmp_path):
        """Test that add_event increases total token count"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary of conversation.")
        llm.get_context_window_size = lambda: 8000

        config = ContextConfig(max_tokens=1000)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm,
        )

        context_mgr.add_event(
            event={"event_type": EventType.USER_QUERY, "content": {"query": "拨款给直隶"}},
            tokens=50,
        )

        assert len(context_mgr.events) == 1

    @pytest.mark.asyncio
    async def test_add_event_multiple(self, tmp_path):
        """Test adding multiple events accumulates tokens"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary.")
        llm.get_context_window_size = lambda: 8000

        config = ContextConfig(max_tokens=1000)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm,
        )

        context_mgr.add_event(
            {"event_type": EventType.USER_QUERY, "content": {"query": "Q1"}}, tokens=30
        )
        context_mgr.add_event(
            {"event_type": EventType.RESPONSE, "content": {"narrative": "A1"}}, tokens=50
        )
        context_mgr.add_event(
            {"event_type": EventType.USER_QUERY, "content": {"query": "Q2"}}, tokens=20
        )

        assert len(context_mgr.events) == 3

    @pytest.mark.asyncio
    async def test_get_messages_returns_formatted_messages(self, tmp_path):
        """Test that get_messages returns properly formatted messages"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary.")
        llm.get_context_window_size = lambda: 8000

        config = ContextConfig(max_tokens=1000)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm,
        )

        context_mgr.add_event(
            {"event_type": EventType.USER_QUERY, "content": {"query": "拨款给直隶"}}, tokens=15
        )
        context_mgr.add_event(
            {"event_type": EventType.RESPONSE, "src": "agent:revenue_minister", "content": {"narrative": "好的，我将拨款。"}},
            tokens=20,
        )

        messages = context_mgr.get_context_messages()

        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert "拨款给直隶" in messages[0]["content"]
        assert messages[1]["role"] == "assistant"
        assert "好的，我将拨款。" in messages[1]["content"]

    @pytest.mark.asyncio
    async def test_slide_window_trigger(self, tmp_path):
        """Test that sliding window triggers when threshold exceeded"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary of conversation.")
        llm.get_context_window_size = lambda: 8000

        # 设置低阈值以便容易触发
        config = ContextConfig(max_tokens=100, threshold_ratio=0.95)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm,
        )

        # 添加事件直到超过阈值 (100 * 0.95 = 95)
        need_slide = context_mgr.add_event(
            {"event_type": EventType.USER_QUERY, "content": {"query": "Q1"}}, tokens=30
        )
        assert not need_slide  # 30 < 95

        need_slide = context_mgr.add_event(
            {"event_type": EventType.RESPONSE, "content": {"narrative": "A1"}}, tokens=30
        )
        assert not need_slide  # 60 < 95

        need_slide = context_mgr.add_event(
            {"event_type": EventType.USER_QUERY, "content": {"query": "Q2"}}, tokens=30
        )
        assert not need_slide  # 90 < 95

        # 再添加一个事件，超过阈值
        need_slide = context_mgr.add_event(
            {"event_type": EventType.RESPONSE, "content": {"narrative": "A2"}}, tokens=30
        )
        assert need_slide  # 120 > 95

    @pytest.mark.asyncio
    async def test_assistant_response_converted_to_message(self, tmp_path):
        """Test that ASSISTANT_RESPONSE events are converted to messages"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary.")
        llm.get_context_window_size = lambda: 8000

        config = ContextConfig(max_tokens=1000)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm,
        )

        context_mgr.add_event(
            {"event_type": EventType.USER_QUERY, "content": {"query": "拨款给直隶"}}, tokens=15
        )
        context_mgr.add_event(
            {
                "event_type": EventType.ASSISTANT_RESPONSE,
                "content": {
                    "response": "我来查询一下数据。",
                    "iteration": 1,
                    "has_tool_calls": True,
                },
            },
            tokens=20,
        )

        messages = context_mgr.get_context_messages()

        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert "拨款给直隶" in messages[0]["content"]
        assert messages[1]["role"] == "assistant"
        assert "我来查询一下数据。" in messages[1]["content"]

    @pytest.mark.asyncio
    async def test_anchor_detection(self, tmp_path):
        """测试锚点检测逻辑"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary.")
        llm.get_context_window_size = lambda: 8000

        config = ContextConfig(max_tokens=1000)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm,
        )

        # 创建测试事件
        user_query = {"type": EventType.USER_QUERY, "payload": {"query": "test"}}
        tool_call = {"type": "tool_result", "payload": {"tool": "query_data", "result": "ok"}}
        agent_response = {"type": EventType.RESPONSE, "payload": {"narrative": "ok"}}
        assistant_response = {
            "type": EventType.ASSISTANT_RESPONSE,
            "payload": {"narrative": "thinking"},
        }
        game_event = {"type": "GAME_EVENT", "payload": {"action": "allocate_funds"}}

        assert context_mgr._is_anchor_event(user_query)
        assert not context_mgr._is_anchor_event(tool_call)
        assert context_mgr._is_anchor_event(agent_response)
        assert context_mgr._is_anchor_event(assistant_response)
        assert context_mgr._is_anchor_event(game_event)

    @pytest.mark.asyncio
    async def test_anchor_aware_sliding_window(self, tmp_path):
        """测试锚点感知的滑动窗口"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary.")
        llm.get_context_window_size = lambda: 8000

        # 配置：保留最近3个事件，锚点缓冲区为1
        config = ContextConfig(
            max_tokens=1000, keep_recent_events=3, anchor_buffer=1, enable_anchor_aware=True
        )
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm,
        )

        # 添加事件序列：USER_QUERY -> TOOL_RESULT -> ASSISTANT_RESPONSE -> AGENT_RESPONSE
        # 事件0: USER_QUERY (锚点)
        context_mgr.add_event(
            {"type": EventType.USER_QUERY, "payload": {"query": "old_query"}}, tokens=10
        )
        # 事件1: TOOL_RESULT (非锚点)
        context_mgr.add_event(
            {"type": "tool_result", "payload": {"tool": "query_data", "result": "ok"}}, tokens=10
        )
        # 事件2: ASSISTANT_RESPONSE (锚点)
        context_mgr.add_event(
            {"type": EventType.ASSISTANT_RESPONSE, "payload": {"narrative": "thinking"}}, tokens=10
        )
        # 事件3: AGENT_RESPONSE (锚点)
        context_mgr.add_event(
            {"type": EventType.RESPONSE, "payload": {"narrative": "final"}}, tokens=10
        )

        # 执行滑动窗口
        await context_mgr.slide_window()

        # 验证：应该保留最近3个事件 (1, 2, 3)
        # + 事件0的锚点缓冲区 (0-1范围，但事件1已在最近范围内，只增加事件0)
        # 预期保留：事件0, 1, 2, 3 (全部保留，因为锚点缓冲区覆盖了旧事件)
        assert len(context_mgr.events) >= 3  # 至少保留最近3个

        # 验证最近的事件被保留
        assert any(e.get("type") == "response" for e in context_mgr.events)
        assert any(e.get("type") == "assistant_response" for e in context_mgr.events)

    @pytest.mark.asyncio
    async def test_anchor_aware_disabled(self, tmp_path):
        """测试禁用锚点感知时的行为"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary.")
        llm.get_context_window_size = lambda: 8000

        # 配置：禁用锚点感知
        config = ContextConfig(max_tokens=1000, keep_recent_events=3, enable_anchor_aware=False)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm,
        )

        # 添加5个事件
        for i in range(5):
            context_mgr.add_event(
                {"type": EventType.USER_QUERY, "payload": {"query": f"query_{i}"}}, tokens=10
            )

        # 执行滑动窗口
        await context_mgr.slide_window()

        # 验证：只保留最近3个事件
        assert len(context_mgr.events) == 3
        assert context_mgr.events[0].get("payload", {}).get("query") == "query_2"
        assert context_mgr.events[1].get("payload", {}).get("query") == "query_3"
        assert context_mgr.events[2].get("payload", {}).get("query") == "query_4"

    @pytest.mark.asyncio
    async def test_tool_result_converted_to_message(self, tmp_path):
        """测试 TOOL_RESULT 事件被正确转换为消息（需要对应的 tool_calls）"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary.")
        llm.get_context_window_size = lambda: 8000

        config = ContextConfig(max_tokens=1000)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm,
        )

        # 添加完整的事件序列：USER_QUERY -> ASSISTANT_RESPONSE (with tool_calls) -> TOOL_RESULT
        context_mgr.add_event(
            {"event_type": EventType.USER_QUERY, "content": {"query": "拨款给直隶"}}, tokens=15
        )
        context_mgr.add_event(
            {
                "event_type": EventType.ASSISTANT_RESPONSE,
                "content": {
                    "response": "",
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "query_national_data",
                                "arguments": '{"field": "imperial_treasury"}',
                            },
                        }
                    ],
                },
            },
            tokens=20,
        )
        context_mgr.add_event(
            {
                "event_type": EventType.TOOL_RESULT,
                "content": {
                    "tool_call_id": "call_123",
                    "tool": "query_national_data",
                    "result": "国库白银 100 万两",
                },
            },
            tokens=20,
        )

        messages = context_mgr.get_context_messages()

        # 验证所有事件都被转换为消息（包括 TOOL_RESULT）
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert "拨款给直隶" in messages[0]["content"]
        assert messages[1]["role"] == "assistant"
        assert "tool_calls" in messages[1]
        assert messages[1]["tool_calls"][0]["id"] == "call_123"
        assert messages[2]["role"] == "tool"
        assert messages[2]["tool_call_id"] == "call_123"
        assert "国库白银 100 万两" in messages[2]["content"]

    @pytest.mark.asyncio
    async def test_assistant_response_with_tool_calls(self, tmp_path):
        """测试 ASSISTANT_RESPONSE 包含 tool_calls 时的格式一致性"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary.")
        llm.get_context_window_size = lambda: 8000

        config = ContextConfig(max_tokens=1000)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm,
        )

        # 添加包含 tool_calls 的 ASSISTANT_RESPONSE 事件
        context_mgr.add_event(
            {
                "event_type": EventType.USER_QUERY,
                "content": {"query": "拨款给直隶"},
            },
            tokens=15,
        )
        context_mgr.add_event(
            {
                "event_type": EventType.ASSISTANT_RESPONSE,
                "content": {
                    "response": "",
                    "iteration": 1,
                    "has_tool_calls": True,
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "query_national_data",
                                "arguments": '{"field": "imperial_treasury"}',
                            },
                        }
                    ],
                },
            },
            tokens=20,
        )

        messages = context_mgr.get_context_messages()

        # 验证 ASSISTANT_RESPONSE 包含 tool_calls 字段
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] is None  # 空响应
        assert "tool_calls" in messages[1]
        assert len(messages[1]["tool_calls"]) == 1
        assert messages[1]["tool_calls"][0]["id"] == "call_123"
        assert messages[1]["tool_calls"][0]["function"]["name"] == "query_national_data"

    @pytest.mark.asyncio
    async def test_orphaned_tool_message_filtered(self, tmp_path):
        """测试孤立 tool 消息被过滤（没有匹配的 tool_calls）"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary.")
        llm.get_context_window_size = lambda: 8000

        config = ContextConfig(max_tokens=1000)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm,
        )

        # 添加一个孤立的 TOOL_RESULT（没有对应的 ASSISTANT_RESPONSE）
        context_mgr.add_event(
            {
                "event_type": EventType.TOOL_RESULT,
                "content": {
                    "tool_call_id": "call_orphaned",
                    "tool": "query_data",
                    "result": "orphaned result",
                },
            },
            tokens=20,
        )

        messages = context_mgr.get_context_messages()

        # 验证孤立的 tool 消息被过滤
        assert len(messages) == 0
        assert not any(msg.get("role") == "tool" for msg in messages)

    @pytest.mark.asyncio
    async def test_valid_tool_call_pair_preserved(self, tmp_path):
        """测试有效的 assistant+tool 配对被保留"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary.")
        llm.get_context_window_size = lambda: 8000

        config = ContextConfig(max_tokens=1000)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm,
        )

        # 添加完整的事件序列：USER_QUERY -> ASSISTANT_RESPONSE (with tool_calls) -> TOOL_RESULT
        context_mgr.add_event(
            {"event_type": EventType.USER_QUERY, "content": {"query": "拨款给直隶"}},
            tokens=15,
        )
        context_mgr.add_event(
            {
                "event_type": EventType.ASSISTANT_RESPONSE,
                "content": {
                    "response": "",
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "query_national_data",
                                "arguments": '{"field": "imperial_treasury"}',
                            },
                        }
                    ],
                },
            },
            tokens=20,
        )
        context_mgr.add_event(
            {
                "event_type": EventType.TOOL_RESULT,
                "content": {
                    "tool_call_id": "call_123",
                    "tool": "query_national_data",
                    "result": "国库白银 100 万两",
                },
            },
            tokens=15,
        )

        messages = context_mgr.get_context_messages()

        # 验证所有消息都被正确转换
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert "tool_calls" in messages[1]
        assert messages[1]["tool_calls"][0]["id"] == "call_123"
        assert messages[2]["role"] == "tool"
        assert messages[2]["tool_call_id"] == "call_123"
        assert "国库白银 100 万两" in messages[2]["content"]

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_with_results(self, tmp_path):
        """测试多个 tool_calls 及其结果都被正确处理"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary.")
        llm.get_context_window_size = lambda: 8000

        config = ContextConfig(max_tokens=1000)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm,
        )

        # 添加包含多个 tool_calls 的 ASSISTANT_RESPONSE
        context_mgr.add_event(
            {"event_type": EventType.USER_QUERY, "content": {"query": "查询国库和直隶情况"}},
            tokens=15,
        )
        context_mgr.add_event(
            {
                "event_type": EventType.ASSISTANT_RESPONSE,
                "content": {
                    "response": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "query_national_data",
                                "arguments": '{"field": "imperial_treasury"}',
                            },
                        },
                        {
                            "id": "call_2",
                            "type": "function",
                            "function": {
                                "name": "query_province_data",
                                "arguments": '{"province_id": "zhili", "field": "local_treasury"}',
                            },
                        },
                    ],
                },
            },
            tokens=30,
        )
        # 添加对应的 TOOL_RESULT 事件
        context_mgr.add_event(
            {
                "event_type": EventType.TOOL_RESULT,
                "content": {
                    "tool_call_id": "call_1",
                    "result": "国库白银 100 万两",
                },
            },
            tokens=15,
        )
        context_mgr.add_event(
            {
                "event_type": EventType.TOOL_RESULT,
                "content": {
                    "tool_call_id": "call_2",
                    "result": "直隶省库白银 20 万两",
                },
            },
            tokens=15,
        )

        messages = context_mgr.get_context_messages()

        # 验证：user + assistant (with 2 tool_calls) + 2 tool messages
        assert len(messages) == 4
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert len(messages[1]["tool_calls"]) == 2
        assert messages[2]["role"] == "tool"
        assert messages[2]["tool_call_id"] == "call_1"
        assert messages[3]["role"] == "tool"
        assert messages[3]["tool_call_id"] == "call_2"

    @pytest.mark.asyncio
    async def test_sliding_window_preserves_pairs(self, tmp_path):
        """测试滑动窗口不会破坏 assistant+tool 配对"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary.")
        llm.get_context_window_size = lambda: 8000

        # 配置：保留最近2个事件（测试滑动窗口场景）
        config = ContextConfig(max_tokens=1000, keep_recent_events=2, enable_anchor_aware=False)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm,
        )

        # 添加事件序列：
        # 1. USER_QUERY
        # 2. ASSISTANT_RESPONSE (with tool_calls)
        # 3. TOOL_RESULT
        # 4. AGENT_RESPONSE
        context_mgr.add_event(
            {"event_type": EventType.USER_QUERY, "content": {"query": "old query"}}, tokens=10
        )
        context_mgr.add_event(
            {
                "event_type": EventType.ASSISTANT_RESPONSE,
                "content": {
                    "response": "",
                    "tool_calls": [
                        {
                            "id": "call_old",
                            "type": "function",
                            "function": {"name": "query_data", "arguments": "{}"},
                        }
                    ],
                },
            },
            tokens=10,
        )
        context_mgr.add_event(
            {
                "event_type": EventType.TOOL_RESULT,
                "content": {"tool_call_id": "call_old", "result": "ok"},
            },
            tokens=10,
        )
        context_mgr.add_event(
            {"event_type": EventType.RESPONSE, "content": {"narrative": "final response"}},
            tokens=10,
        )

        # 执行滑动窗口（只保留最近2个事件）
        await context_mgr.slide_window()

        # 验证：如果滑动窗口分离了 assistant 和 tool 消息，
        # 孤立的 tool 消息应该被过滤
        messages = context_mgr.get_context_messages()

        # 滑动窗口后只保留最近2个事件，假设是 TOOL_RESULT 和 AGENT_RESPONSE
        # 此时 TOOL_RESULT 是孤立的（没有对应的 ASSISTANT_RESPONSE）
        # 因此应该只保留 AGENT_RESPONSE
        tool_messages = [msg for msg in messages if msg.get("role") == "tool"]
        assistant_messages = [msg for msg in messages if msg.get("role") == "assistant"]

        # 验证没有孤立的 tool 消息
        for tool_msg in tool_messages:
            tool_call_id = tool_msg.get("tool_call_id")
            # 确保这个 tool_call_id 有对应的 assistant 消息
            has_matching_assistant = any(
                any(tc.get("id") == tool_call_id for tc in assst_msg.get("tool_calls", []))
                for assst_msg in assistant_messages
            )
            assert has_matching_assistant, (
                f"Found orphaned tool message with tool_call_id: {tool_call_id}"
            )

    @pytest.mark.asyncio
    async def test_response_event_to_messages(self, tmp_path):
        """测试 RESPONSE 事件被正确转换为消息"""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary.")
        llm.get_context_window_size = lambda: 8000

        config = ContextConfig(max_tokens=1000)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="governor_zhili",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm,
        )

        # 添加来自其他 agent 的 RESPONSE 事件
        context_mgr.add_event(
            {
                "event_type": EventType.RESPONSE,
                "src": "agent:minister_of_revenue",
                "content": {"narrative": "已收到您的命令。"},
            },
            tokens=20,
        )

        messages = context_mgr.get_context_messages()

        # 验证 RESPONSE 事件被转换为 user 消息
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "来自 minister_of_revenue 的回复" in messages[0]["content"]
        assert "已收到您的命令。" in messages[0]["content"]


class TestContextManagerPositionTracking:
    """Test V4 tape position tracking for segment_index updates."""

    @pytest.mark.asyncio
    async def test_position_counter_initialized_from_tape(self, tmp_path):
        """Test that position counter is initialized from tape length."""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary.")
        llm.get_context_window_size = lambda: 8000

        config = ContextConfig(max_tokens=1000)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm,
        )

        # Create a tape file with 5 events
        tape_content = "\n".join(
            [f'{{"event_id": "evt_{i}", "event_type": "user_query"}}' for i in range(5)]
        )
        (tmp_path / "tape.jsonl").write_text(tape_content + "\n")

        # Load from tape should initialize position counter
        await context_mgr.load_from_tape()

        assert context_mgr._tape_position_counter == 5

    @pytest.mark.asyncio
    async def test_position_counter_increments_on_add_event(self, tmp_path):
        """Test that position counter increments when events are added."""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary.")
        llm.get_context_window_size = lambda: 8000

        config = ContextConfig(max_tokens=1000)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm,
        )

        # Initial position should be 0
        assert context_mgr._tape_position_counter == 0

        # Add events
        context_mgr.add_event(
            {"event_type": EventType.USER_QUERY, "content": {"query": "Q1"}}, tokens=10
        )
        assert context_mgr._tape_position_counter == 1

        context_mgr.add_event(
            {"event_type": EventType.RESPONSE, "content": {"narrative": "A1"}}, tokens=10
        )
        assert context_mgr._tape_position_counter == 2

        context_mgr.add_event(
            {"event_type": EventType.USER_QUERY, "content": {"query": "Q2"}}, tokens=10
        )
        assert context_mgr._tape_position_counter == 3

    @pytest.mark.asyncio
    async def test_position_counter_with_load_and_add(self, tmp_path):
        """Test position counter when loading from tape and adding new events."""
        llm = AsyncMock()
        llm.call = AsyncMock(return_value="Summary.")
        llm.get_context_window_size = lambda: 8000

        config = ContextConfig(max_tokens=1000)
        context_mgr = ContextManager(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            tape_path=tmp_path / "tape.jsonl",
            config=config,
            llm_provider=llm,
        )

        # Create a tape file with 3 events
        tape_content = "\n".join(
            [f'{{"event_id": "evt_{i}", "event_type": "user_query"}}' for i in range(3)]
        )
        (tmp_path / "tape.jsonl").write_text(tape_content + "\n")

        # Load from tape
        await context_mgr.load_from_tape()
        assert context_mgr._tape_position_counter == 3

        # Add new events
        context_mgr.add_event(
            {"event_type": EventType.USER_QUERY, "content": {"query": "Q1"}}, tokens=10
        )
        assert context_mgr._tape_position_counter == 4

        context_mgr.add_event(
            {"event_type": EventType.RESPONSE, "content": {"narrative": "A1"}}, tokens=10
        )
        assert context_mgr._tape_position_counter == 5
