"""
测试 Agent 核心逻辑（Function Calling 架构）
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock

from simu_emperor.agents.agent import Agent
from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.llm.mock import MockProvider


@pytest.fixture
def mock_event_bus():
    """Mock EventBus"""
    event_bus = MagicMock(spec=EventBus)
    event_bus.subscribe = MagicMock()
    event_bus.unsubscribe = MagicMock()
    event_bus.send_event = AsyncMock()
    return event_bus


@pytest.fixture
def mock_repository():
    """Mock Repository"""
    repo = Mock()
    repo.load_state = AsyncMock(
        return_value={
            "turn": 5,
            "imperial_treasury": 100000,
            "provinces": [
                {
                    "province_id": "zhili",
                    "name": "直隶",
                    "population": {"total": 2600000, "happiness": 0.7},
                },
                {
                    "province_id": "jiangsu",
                    "name": "江苏",
                    "population": {"total": 1800000, "happiness": 0.65},
                },
            ],
        }
    )
    return repo


@pytest.fixture
def mock_llm():
    """Mock LLM Provider"""
    return MockProvider(
        response="",
        tool_calls=[
            {
                "id": "call_1",
                "function": {"name": "respond_to_player", "arguments": '{"content": "臣遵旨！"}'},
            }
        ],
    )


@pytest.fixture
def temp_data_dir(tmp_path):
    """创建临时数据目录"""
    # 创建目录结构：tmp_path/data/agent/test_agent/
    agent_dir = tmp_path / "data" / "agent" / "test_agent"
    agent_dir.mkdir(parents=True)

    # 创建 soul.md
    soul_path = agent_dir / "soul.md"
    soul_path.write_text("# Test Soul\nYou are a test agent.", encoding="utf-8")

    # 创建 data_scope.yaml
    import yaml

    scope_path = agent_dir / "data_scope.yaml"
    scope_path.write_text(yaml.dump({"query": ["province.population"]}), encoding="utf-8")

    return agent_dir


@pytest.fixture
def agent(mock_event_bus, mock_llm, temp_data_dir, mock_repository, tmp_path, monkeypatch):
    """创建 Agent 实例，使用临时 memory 目录"""
    # 创建临时 memory 目录
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()

    # 使用 monkeypatch.setattr 直接修改 settings.memory.memory_dir
    # 注意：必须在 Agent 实例化之前 patch，因为 Agent.__init__ 会读取 settings
    from simu_emperor.config import settings

    monkeypatch.setattr(settings.memory, "memory_dir", memory_dir)

    # 创建 mock SessionManager with proper mock session
    mock_session = MagicMock()
    mock_session.is_task = False
    mock_session.status = "ACTIVE"
    mock_session.pending_async_replies = 0
    mock_session.parent_id = None
    mock_session.pending_message_ids = []
    mock_session.created_by = "player"  # V4: 避免 MagicMock 序列化问题
    mock_session_manager = MagicMock()
    mock_session_manager.get_session = AsyncMock(return_value=mock_session)
    mock_session_manager.get_agent_state = AsyncMock(return_value=None)
    mock_session_manager.increment_async_replies = AsyncMock()
    mock_session_manager.save_manifest = AsyncMock()
    mock_session_manager.get_context_manager = AsyncMock()

    # V4.1: 创建 mock tape_writer 和 tape_metadata_mgr
    # 注意：write_event 需要是 AsyncMock，因为被 await 调用
    mock_tape_writer = MagicMock()
    mock_tape_writer._get_tape_path = MagicMock(return_value=memory_dir / "tape.jsonl")
    mock_tape_writer.write_event = AsyncMock(return_value="event_id")
    mock_tape_metadata_mgr = AsyncMock()

    agent = Agent(
        agent_id="test_agent",
        event_bus=mock_event_bus,
        llm_provider=mock_llm,
        data_dir=temp_data_dir,
        repository=mock_repository,
        session_manager=mock_session_manager,
        tape_writer=mock_tape_writer,
        tape_metadata_mgr=mock_tape_metadata_mgr,
    )

    yield agent


class TestAgent:
    """测试 Agent 类"""

    def test_init(self, agent, mock_event_bus, mock_llm, temp_data_dir):
        """测试初始化"""
        assert agent.agent_id == "test_agent"
        assert agent.event_bus == mock_event_bus
        assert agent.llm_provider == mock_llm
        assert agent.data_dir == temp_data_dir
        assert agent._soul is not None
        assert agent._data_scope is not None

    def test_start(self, agent, mock_event_bus):
        """测试启动"""
        agent.start()

        # 订阅2次：agent:xxx, * (broadcast only)
        assert mock_event_bus.subscribe.call_count == 2

    def test_stop(self, agent, mock_event_bus):
        """测试停止"""
        agent.start()
        agent.stop()

        # 只取消订阅1次：agent:xxx
        # conditional_handler 无法取消（局部变量）
        assert mock_event_bus.unsubscribe.call_count == 1

    @pytest.mark.asyncio
    async def test_on_event_command(self, agent, mock_llm):
        """测试处理命令事件"""
        # 创建新的 MockProvider 实例以避免测试之间的状态污染
        fresh_mock = MockProvider(response="", tool_calls=None)
        agent.llm_provider = fresh_mock

        agent.start()

        # 设置 tool calls（只回复，不执行游戏动作）
        fresh_mock.set_tool_calls(
            [
                {
                    "id": "call_1",
                    "function": {
                        "name": "respond_to_player",
                        "arguments": '{"content": "臣遵旨！已记录陛下的命令。"}',
                    },
                },
            ]
        )

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.CHAT,
            payload={"message": "调整直隶税率为 5%"},
            session_id="test_session_command",
        )

        await agent._on_event(event)

        # 应该调用 LLM
        assert fresh_mock.call_count == 1

        # 应该发送事件
        assert agent.event_bus.send_event.called

    @pytest.mark.asyncio
    async def test_on_event_query(self, agent, mock_llm):
        """测试处理查询事件"""
        # 创建新的 MockProvider 实例以避免测试之间的状态污染
        fresh_mock = MockProvider(response="", tool_calls=None)
        agent.llm_provider = fresh_mock

        agent.start()

        # 设置 tool calls（第一轮：查询）
        fresh_mock.set_tool_calls(
            [
                {
                    "id": "call_1",
                    "function": {
                        "name": "query_national_data",
                        "arguments": '{"field_name": "imperial_treasury"}',
                    },
                }
            ]
        )

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.CHAT,
            payload={"message": "国库还有多少银两？"},
            session_id="test_session_query",
        )

        await agent._on_event(event)

        # 应该调用 LLM 两次（第一轮查询，第二轮回复）
        # 因为包含查询函数，需要多轮对话
        assert fresh_mock.call_count == 2
        assert agent.event_bus.send_event.called

    @pytest.mark.asyncio
    async def test_on_event_chat(self, agent, mock_llm):
        """测试处理对话事件"""
        agent.start()

        # 设置 tool calls
        mock_llm.set_tool_calls(
            [
                {
                    "id": "call_1",
                    "function": {
                        "name": "respond_to_player",
                        "arguments": '{"content": "臣惶恐！陛下垂询，臣不胜感激。"}',
                    },
                }
            ]
        )

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.CHAT,
            payload={"message": "你好"},
            session_id="test_session_chat",
        )

        await agent._on_event(event)

        # V4: 由于 ContextManager 需要加载历史事件，可能会有 2 次 LLM 调用
        # 第一次：获取 tool_calls
        # 第二次：处理 tool 结果后，返回空 tool_calls（循环结束）
        assert mock_llm.call_count >= 1
        assert agent.event_bus.send_event.called

    @pytest.mark.asyncio
    async def test_send_message_to_agent(self, agent, mock_llm):
        """测试发送消息给其他 Agent"""
        # 创建新的 MockProvider 实例以避免测试之间的状态污染
        fresh_mock = MockProvider(response="", tool_calls=None)
        agent.llm_provider = fresh_mock

        agent.start()

        # 设置 tool calls
        fresh_mock.set_tool_calls(
            [
                {
                    "id": "call_1",
                    "function": {
                        "name": "send_message_to_agent",
                        "arguments": '{"target_agent": "governor_zhili", "message": "请执行陛下的命令"}',
                    },
                },
                {
                    "id": "call_2",
                    "function": {
                        "name": "respond_to_player",
                        "arguments": '{"content": "臣已通知李卫执行命令。"}',
                    },
                },
            ]
        )

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.CHAT,
            payload={"command": "命令直隶总督李卫执行任务"},
            session_id="test_session_send_message",
        )

        await agent._on_event(event)

        # 应该发送消息给其他 agent
        assert agent.event_bus.send_event.called
        calls = agent.event_bus.send_event.call_args_list
        assert len(calls) == 2  # send_message_to_agent + respond_to_player

    @pytest.mark.asyncio
    async def test_get_system_prompt_for_event(self, agent):
        """测试不同事件类型的 system prompt"""
        agent.start()

        # CHAT 事件
        prompt_chat = agent._get_system_prompt_for_event(EventType.CHAT)
        assert "皇帝想和你聊天" in prompt_chat
        assert "respond_to_player" in prompt_chat

    @pytest.mark.asyncio
    async def test_query_province_data(self, agent, mock_repository):
        """测试查询省份数据（使用 QueryTools）"""
        agent.start()

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.CHAT,
            payload={"query": "查询直隶人口"},
            session_id="test_session_query_province",
        )

        # 调用 QueryTools 的方法
        result = await agent._query_tools.query_province_data(
            {"province_id": "zhili", "field_path": "population.total"}, event
        )

        # 应该调用 load_state
        assert mock_repository.load_state.called
        # 应该返回结果字符串
        assert isinstance(result, str)
        assert "2600000" in result

    @pytest.mark.asyncio
    async def test_query_national_data(self, agent, mock_repository):
        """测试查询国家级数据（使用 QueryTools）"""
        agent.start()

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.CHAT,
            payload={"query": "查询国库"},
            session_id="test_session_query_national",
        )

        # 调用 QueryTools 的方法
        result = await agent._query_tools.query_national_data(
            {"field_name": "imperial_treasury"}, event
        )

        # 应该调用 load_state
        assert mock_repository.load_state.called
        # 应该返回结果字符串
        assert isinstance(result, str)
        assert "100000" in result

    @pytest.mark.asyncio
    async def test_list_provinces(self, agent, mock_repository):
        """测试列出所有省份（使用 QueryTools）"""
        agent.start()

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.CHAT,
            payload={"query": "列出所有省份"},
            session_id="test_session_list_provinces",
        )

        # 调用 QueryTools 的方法
        result = await agent._query_tools.list_provinces({}, event)

        # 应该调用 load_state
        assert mock_repository.load_state.called
        # 应该返回结果字符串
        assert isinstance(result, str)
        assert "zhili" in result
        assert "jiangsu" in result

    @pytest.mark.asyncio
    async def test_query_without_repository(self, agent, mock_repository):
        """测试没有 repository 时的查询（使用 QueryTools）"""
        agent.start()

        # 移除 repository (需要同时更新 agent.repository 和 _query_tools.repository)
        agent.repository = None
        agent._query_tools.repository = None

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.CHAT,
            payload={"query": "查询直隶人口"},
            session_id="test_session_query_province",
        )

        # 调用 QueryTools 的方法（应该返回错误消息）
        result = await agent._query_tools.query_province_data(
            {"province_id": "zhili", "field_path": "population.total"}, event
        )

        # 不应该调用 load_state
        assert not mock_repository.load_state.called
        # 应该返回错误消息
        assert "repository not available" in result.lower() or "无法查询" in result

    def test_agent_with_skill_loader(
        self, mock_event_bus, mock_llm, temp_data_dir, mock_repository
    ):
        """测试注入 SkillLoader"""
        # 创建 mock SkillLoader
        mock_skill_loader = Mock()

        # 创建 mock SessionManager with proper mock session
        mock_session = MagicMock()
        mock_session.is_task = False
        mock_session.status = "ACTIVE"
        mock_session.pending_async_replies = 0
        mock_session.parent_id = None
        mock_session.pending_message_ids = []
        mock_session_manager = MagicMock()
        mock_session_manager.get_session = AsyncMock(return_value=mock_session)
        mock_session_manager.get_agent_state = AsyncMock(return_value=None)
        mock_session_manager.increment_async_replies = AsyncMock()
        mock_session_manager.save_manifest = AsyncMock()

        # 创建 Agent 时传入 skill_loader
        agent = Agent(
            agent_id="test_agent_with_loader",
            event_bus=mock_event_bus,
            llm_provider=mock_llm,
            data_dir=temp_data_dir,
            repository=mock_repository,
            skill_loader=mock_skill_loader,
            session_manager=mock_session_manager,
        )

        # 验证 skill_loader 被正确保存
        assert agent._skill_loader is mock_skill_loader
        assert agent._skill_loader is not None

    def test_agent_backward_compatible(
        self, mock_event_bus, mock_llm, temp_data_dir, mock_repository
    ):
        """测试不传 skill_loader 时向后兼容"""
        # 创建 mock SessionManager with proper mock session
        mock_session = MagicMock()
        mock_session.is_task = False
        mock_session.status = "ACTIVE"
        mock_session.pending_async_replies = 0
        mock_session.parent_id = None
        mock_session.pending_message_ids = []
        mock_session_manager = MagicMock()
        mock_session_manager.get_session = AsyncMock(return_value=mock_session)
        mock_session_manager.get_agent_state = AsyncMock(return_value=None)
        mock_session_manager.increment_async_replies = AsyncMock()
        mock_session_manager.save_manifest = AsyncMock()

        # 创建 Agent 时不传入 skill_loader
        agent = Agent(
            agent_id="test_agent_no_loader",
            event_bus=mock_event_bus,
            llm_provider=mock_llm,
            data_dir=temp_data_dir,
            repository=mock_repository,
            session_manager=mock_session_manager,
            # 不传 skill_loader 参数
        )

        # 验证 _skill_loader 为 None（向后兼容）
        assert agent._skill_loader is None
        # 其他属性应该正常初始化
        assert agent.agent_id == "test_agent_no_loader"
        assert agent.event_bus == mock_event_bus
        assert agent.llm_provider == mock_llm

    @pytest.mark.asyncio
    async def test_system_prompt_uses_hardcoded_content(
        self, mock_event_bus, mock_llm, temp_data_dir, mock_repository
    ):
        """测试使用硬编码的 System Prompt 内容"""
        # 创建 Agent（不传入 SkillLoader，因为已不再使用）
        # 创建 mock SessionManager with proper mock session
        mock_session = MagicMock()
        mock_session.is_task = False
        mock_session.status = "ACTIVE"
        mock_session.pending_async_replies = 0
        mock_session.parent_id = None
        mock_session.pending_message_ids = []
        mock_session_manager = MagicMock()
        mock_session_manager.get_session = AsyncMock(return_value=mock_session)
        mock_session_manager.get_agent_state = AsyncMock(return_value=None)
        mock_session_manager.increment_async_replies = AsyncMock()
        mock_session_manager.save_manifest = AsyncMock()

        agent = Agent(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            llm_provider=mock_llm,
            data_dir=temp_data_dir,
            repository=mock_repository,
            session_manager=mock_session_manager,
        )

        # 获取 system prompt
        prompt = agent._get_system_prompt_for_event(EventType.CHAT)

        # 验证使用了硬编码指令
        assert "皇帝想和你聊天" in prompt

    @pytest.mark.asyncio
    async def test_system_prompt_fallback_to_hardcoded(
        self, mock_event_bus, mock_llm, temp_data_dir, mock_repository
    ):
        """测试回退到硬编码指令"""
        # 创建 mock SessionManager
        mock_session = MagicMock()
        mock_session.is_task = False
        mock_session.status = "ACTIVE"
        mock_session_manager = MagicMock()
        mock_session_manager.get_session = AsyncMock(return_value=mock_session)
        mock_session_manager.increment_async_replies = AsyncMock()
        mock_session_manager.save_manifest = AsyncMock()

        # 创建 Agent 时不传入 SkillLoader
        agent = Agent(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            llm_provider=mock_llm,
            data_dir=temp_data_dir,
            repository=mock_repository,
            session_manager=mock_session_manager,
        )

        # 获取 system prompt
        prompt = agent._get_system_prompt_for_event(EventType.CHAT)

        # 验证使用了硬编码指令
        assert "皇帝想和你聊天" in prompt

    @pytest.mark.asyncio
    async def test_system_prompt_fallback_when_skill_not_found(
        self, mock_event_bus, mock_llm, temp_data_dir, mock_repository
    ):
        """测试 Skill 加载失败时回退到硬编码"""
        # 创建 mock SkillLoader，但返回 None（模拟加载失败）
        mock_skill_loader = Mock()
        mock_skill_loader.load.return_value = None
        mock_skill_loader.registry.get_skill_for_event.return_value = "nonexistent_skill"

        # 创建 mock SessionManager with proper mock session
        mock_session = MagicMock()
        mock_session.is_task = False
        mock_session.status = "ACTIVE"
        mock_session.pending_async_replies = 0
        mock_session.parent_id = None
        mock_session.pending_message_ids = []
        mock_session_manager = MagicMock()
        mock_session_manager.get_session = AsyncMock(return_value=mock_session)
        mock_session_manager.get_agent_state = AsyncMock(return_value=None)
        mock_session_manager.increment_async_replies = AsyncMock()
        mock_session_manager.save_manifest = AsyncMock()

        # 创建 Agent 并注入 SkillLoader
        agent = Agent(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            llm_provider=mock_llm,
            data_dir=temp_data_dir,
            repository=mock_repository,
            skill_loader=mock_skill_loader,
            session_manager=mock_session_manager,
        )

        # 获取 system prompt
        prompt = agent._get_system_prompt_for_event(EventType.CHAT)

        # 验证回退到硬编码指令
        assert "皇帝想和你聊天" in prompt

    @pytest.mark.asyncio
    async def test_send_message_to_agent_with_await_reply_true(self, agent, tmp_path, monkeypatch):
        """测试 send_message_to_agent 返回正确的等待消息（await_reply=true）"""
        # 创建临时 memory 目录
        memory_dir = tmp_path / "memory_for_await_test"
        memory_dir.mkdir(exist_ok=True)

        # Patch settings to use temporary memory directory
        from simu_emperor.config import settings

        monkeypatch.setattr(settings.memory, "memory_dir", memory_dir)

        # 创建 mock SessionManager with task session
        mock_session = MagicMock()
        mock_session.parent_id = "parent_session"
        mock_session.is_task = True  # Task session
        mock_session.status = "ACTIVE"
        mock_session.pending_async_replies = 0
        mock_session.pending_message_ids = []
        mock_session_manager = MagicMock()
        mock_session_manager.get_session = AsyncMock(return_value=mock_session)
        mock_session_manager.get_agent_state = AsyncMock(return_value=None)
        mock_session_manager.increment_async_replies = AsyncMock()
        mock_session_manager.save_manifest = AsyncMock()

        # 创建 Agent with task session manager
        agent_with_task = Agent(
            agent_id="test_agent_task",
            event_bus=agent.event_bus,
            llm_provider=agent.llm_provider,
            data_dir=agent.data_dir,
            repository=agent.repository,
            session_manager=mock_session_manager,
        )

        task_session_id = "task:test_agent:parent_session:123"
        event = Event(
            src="player",
            dst=["agent:test_agent_task"],
            type=EventType.CHAT,
            payload={"command": "test"},
            session_id=task_session_id,
        )

        # 调用 send_message_to_agent with await_reply=true
        result = await agent_with_task._action_tools.send_message_to_agent(
            {"target_agent": "governor_zhili", "message": "请查收", "await_reply": True},
            event,
        )

        # 应该返回等待消息
        assert "等待回复" in result

        # 验证发送的事件使用的是 task session
        assert agent_with_task.event_bus.send_event.called
        sent_event = agent_with_task.event_bus.send_event.call_args[0][0]
        assert sent_event.session_id == task_session_id

    @pytest.mark.asyncio
    async def test_send_message_to_agent_with_await_reply_false(self, agent):
        """测试 send_message_to_agent 返回成功消息（await_reply=false）"""
        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.CHAT,
            payload={"command": "test"},
            session_id="test_session",
        )

        # 调用 send_message_to_agent with await_reply=false (default)
        result = await agent._action_tools.send_message_to_agent(
            {"target_agent": "governor_zhili", "message": "请查收", "await_reply": False},
            event,
        )

        # 应该返回成功消息（包含 ✅）
        assert "✅" in result
        assert "⏳" not in result

    @pytest.mark.asyncio
    async def test_send_message_to_agent_shares_task_session(self, agent, tmp_path, monkeypatch):
        """测试两个 agent 共享 task session"""
        # 创建临时 memory 目录
        memory_dir = tmp_path / "memory_for_task_test"
        memory_dir.mkdir(exist_ok=True)

        # Patch settings to use temporary memory directory
        from simu_emperor.config import settings

        monkeypatch.setattr(settings.memory, "memory_dir", memory_dir)

        # 创建 mock SessionManager with proper mocks
        mock_session_manager = MagicMock()
        mock_session = MagicMock()
        mock_session.parent_id = "parent_session"
        mock_session.is_task = True
        mock_session.status = "ACTIVE"
        mock_session_manager.get_session = AsyncMock(return_value=mock_session)
        mock_session_manager.get_agent_state = AsyncMock(return_value=None)
        mock_session_manager.increment_async_replies = AsyncMock()
        mock_session_manager.save_manifest = AsyncMock()

        # 创建 Agent with session_manager
        agent_with_sm = Agent(
            agent_id="test_agent_with_session",
            event_bus=agent.event_bus,
            llm_provider=agent.llm_provider,
            data_dir=agent.data_dir,
            repository=agent.repository,
            session_manager=mock_session_manager,
        )

        task_session_id = "task:test_agent:parent_session:123"
        event = Event(
            src="player",
            dst=["agent:test_agent_with_session"],
            type=EventType.AGENT_MESSAGE,
            payload={"message": "test"},
            session_id=task_session_id,
        )

        # 调用 send_message_to_agent
        result = await agent_with_sm._action_tools.send_message_to_agent(
            {"target_agent": "governor_zhili", "message": "请查收", "await_reply": True},
            event,
        )

        # 验证发送的事件使用的是 task session（共享原则）
        assert agent_with_sm.event_bus.send_event.called
        sent_event = agent_with_sm.event_bus.send_event.call_args[0][0]

        # 关键验证：应该使用 task session，而不是 parent session
        assert sent_event.session_id == task_session_id
        assert sent_event.session_id != "parent_session"

    @pytest.mark.asyncio
    async def test_send_message_to_agent_rejects_self_message(self, agent):
        """测试 send_message_to_agent 拒绝向自己发送消息"""
        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.CHAT,
            payload={"command": "test"},
            session_id="test_session",
        )

        # 调用 send_message_to_agent 尝试向自己发送消息
        result = await agent._action_tools.send_message_to_agent(
            {"target_agent": "test_agent", "message": "这是一条消息"},
            event,
        )

        # 应该返回错误消息
        assert "❌" in result
        assert "不能向自己发送消息" in result

        # 验证没有发送任何事件
        assert not agent.event_bus.send_event.called


class TestTickCompletedEvent:
    """Test TICK_COMPLETED event handling (V4)."""

    @pytest.fixture
    def mock_event_bus(self):
        """Mock EventBus"""
        event_bus = MagicMock(spec=EventBus)
        event_bus.subscribe = MagicMock()
        event_bus.unsubscribe = MagicMock()
        event_bus.send_event = AsyncMock()
        return event_bus

    @pytest.fixture
    def mock_repository(self):
        """Mock Repository"""
        repo = Mock()
        repo.load_state = AsyncMock(
            return_value={
                "turn": 5,
                "imperial_treasury": 100000,
                "provinces": [],
            }
        )
        return repo

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM Provider"""
        return MockProvider(
            response="",
            tool_calls=[
                {
                    "id": "call_1",
                    "function": {
                        "name": "finish_loop",
                        "arguments": '{"reason": "no action needed"}',
                    },
                }
            ],
        )

    @pytest.fixture
    def temp_data_dir(self, tmp_path):
        """创建临时数据目录"""
        agent_dir = tmp_path / "data" / "agent" / "test_agent"
        agent_dir.mkdir(parents=True)

        soul_path = agent_dir / "soul.md"
        soul_path.write_text("# Test Soul\nYou are a test agent.", encoding="utf-8")

        import yaml

        scope_path = agent_dir / "data_scope.yaml"
        scope_path.write_text(yaml.dump({"query": ["province.population"]}), encoding="utf-8")

        return agent_dir

    def test_system_prompt_for_tick_completed(
        self, mock_event_bus, mock_llm, temp_data_dir, mock_repository
    ):
        """Test TICK_COMPLETED system prompt is available."""
        mock_session = MagicMock()
        mock_session.is_task = False
        mock_session.status = "ACTIVE"
        mock_session_manager = MagicMock()
        mock_session_manager.get_session = AsyncMock(return_value=mock_session)

        agent = Agent(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            llm_provider=mock_llm,
            data_dir=temp_data_dir,
            repository=mock_repository,
            session_manager=mock_session_manager,
        )

        prompt = agent._get_system_prompt_for_event(EventType.TICK_COMPLETED)

        assert "Tick 完成通知" in prompt
        assert "query_province_data" in prompt
        assert "write_memory" in prompt
        assert "finish_loop" in prompt

    @pytest.mark.asyncio
    async def test_on_event_tick_completed(
        self, mock_event_bus, mock_llm, temp_data_dir, mock_repository, tmp_path, monkeypatch
    ):
        """Test handling TICK_COMPLETED event - V4: only refresh metadata, no LLM call."""
        from simu_emperor.config import settings

        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        monkeypatch.setattr(settings.memory, "memory_dir", memory_dir)

        mock_session = MagicMock()
        mock_session.is_task = False
        mock_session.status = "ACTIVE"
        mock_session.pending_async_replies = 0
        mock_session.parent_id = None
        mock_session.pending_message_ids = []
        mock_session_manager = MagicMock()
        mock_session_manager.get_session = AsyncMock(return_value=mock_session)
        mock_session_manager.get_agent_state = AsyncMock(return_value=None)

        fresh_mock = MockProvider(response="", tool_calls=None)
        fresh_mock.set_tool_calls(
            [
                {
                    "id": "call_1",
                    "function": {"name": "finish_loop", "arguments": '{"reason": "no action"}'},
                }
            ]
        )

        agent = Agent(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            llm_provider=fresh_mock,
            data_dir=temp_data_dir,
            repository=mock_repository,
            session_manager=mock_session_manager,
        )

        agent.start()

        event = Event(
            src="system:tick_coordinator",
            dst=["agent:test_agent"],
            type=EventType.TICK_COMPLETED,
            payload={"tick": 42},
            session_id="test_session_tick",
        )

        await agent._on_event(event)

        # V4: TICK_COMPLETED only refreshes metadata, no LLM call
        assert fresh_mock.call_count == 0


class TestIncidentCreatedEvent:
    """Test INCIDENT_CREATED event type in EventType (V4)."""

    def test_incident_created_in_all_types(self):
        """Test INCIDENT_CREATED is in all event types."""
        all_types = EventType.all()
        assert EventType.INCIDENT_CREATED in all_types

    def test_incident_created_is_system_event(self):
        """Test INCIDENT_CREATED is not in system events (it's agent-initiated)."""
        system_events = EventType.system_events()
        assert EventType.INCIDENT_CREATED not in system_events
