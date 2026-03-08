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
                    "province_id": "shanxi",
                    "name": "山西",
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

    agent = Agent(
        agent_id="test_agent",
        event_bus=mock_event_bus,
        llm_provider=mock_llm,
        data_dir=temp_data_dir,
        repository=mock_repository,
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

        # 订阅3次：agent:xxx, * (broadcast only), TASK_CREATED
        assert mock_event_bus.subscribe.call_count == 3

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

        # 设置 tool calls
        fresh_mock.set_tool_calls(
            [
                {
                    "id": "call_1",
                    "function": {
                        "name": "send_game_event",
                        "arguments": '{"event_type": "adjust_tax", "payload": {"province": "zhili", "rate": 0.05}}',
                    },
                },
                {
                    "id": "call_2",
                    "function": {
                        "name": "respond_to_player",
                        "arguments": '{"content": "臣遵旨！已调整直隶税率为 5%。"}',
                    },
                },
            ]
        )

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.COMMAND,
            payload={"command": "调整直隶税率为 5%"},
            session_id="test_session_command",
        )

        await agent._on_event(event)

        # 应该调用 LLM
        assert fresh_mock.call_count == 1

        # 应该发送事件
        assert agent.event_bus.send_event.called
        # 验证发送的事件
        calls = agent.event_bus.send_event.call_args_list
        assert len(calls) == 2  # send_game_event + respond_to_player

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
            type=EventType.COMMAND,
            payload={"query": "国库还有多少银两？"},
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

        # 应该调用 LLM
        assert mock_llm.call_count == 1
        assert agent.event_bus.send_event.called

    @pytest.mark.asyncio
    async def test_on_event_end_turn(self, agent, mock_llm):
        """测试处理回合结束"""
        agent.start()

        # 设置 tool calls
        mock_llm.set_tool_calls(
            [{"id": "call_1", "function": {"name": "send_ready", "arguments": "{}"}}]
        )

        event = Event(
            src="player", dst=["*"], type=EventType.END_TURN, session_id="test_session_end_turn"
        )

        await agent._on_event(event)

        # 应该调用 LLM 并发送 ready
        assert mock_llm.call_count >= 1
        assert agent.event_bus.send_event.called

    @pytest.mark.asyncio
    async def test_on_event_turn_resolved(self, agent, mock_llm):
        """测试处理回合结算完成"""
        agent.start()

        # 设置 tool calls
        mock_llm.set_tool_calls(
            [
                {
                    "id": "call_1",
                    "function": {
                        "name": "write_memory",
                        "arguments": '{"content": "本回合臣完成了陛下的命令，调整了直隶税率。"}',
                    },
                }
            ]
        )

        event = Event(
            src="system:calculator",
            dst=["*"],
            type=EventType.TURN_RESOLVED,
            payload={"turn": 1},
            session_id="test_session_turn_resolved",
        )

        await agent._on_event(event)

        # 应该调用 LLM 并写入记忆
        assert mock_llm.call_count >= 1

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
            type=EventType.COMMAND,
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

        # COMMAND 事件
        prompt_cmd = await agent._get_system_prompt_for_event(EventType.COMMAND)
        assert "执行皇帝的命令" in prompt_cmd
        assert "send_game_event" in prompt_cmd
        assert "执行动作" in prompt_cmd

        # CHAT 事件
        prompt_chat = await agent._get_system_prompt_for_event(EventType.CHAT)
        assert "皇帝想和你聊天" in prompt_chat
        assert "respond_to_player" in prompt_chat

        # END_TURN 事件
        prompt_end = await agent._get_system_prompt_for_event(EventType.END_TURN)
        assert "回合即将结束" in prompt_end
        assert "send_ready" in prompt_end

        # TURN_RESOLVED 事件
        prompt_resolved = await agent._get_system_prompt_for_event(EventType.TURN_RESOLVED)
        assert "回合结算完成" in prompt_resolved
        assert "write_memory" in prompt_resolved

    @pytest.mark.asyncio
    async def test_query_province_data(self, agent, mock_repository):
        """测试查询省份数据（使用 QueryTools）"""
        agent.start()

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.COMMAND,
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
            type=EventType.COMMAND,
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
            type=EventType.COMMAND,
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
        assert "shanxi" in result

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
            type=EventType.COMMAND,
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

        # 创建 Agent 时传入 skill_loader
        agent = Agent(
            agent_id="test_agent_with_loader",
            event_bus=mock_event_bus,
            llm_provider=mock_llm,
            data_dir=temp_data_dir,
            repository=mock_repository,
            skill_loader=mock_skill_loader,
        )

        # 验证 skill_loader 被正确保存
        assert agent._skill_loader is mock_skill_loader
        assert agent._skill_loader is not None

    def test_agent_backward_compatible(
        self, mock_event_bus, mock_llm, temp_data_dir, mock_repository
    ):
        """测试不传 skill_loader 时向后兼容"""
        # 创建 Agent 时不传入 skill_loader
        agent = Agent(
            agent_id="test_agent_no_loader",
            event_bus=mock_event_bus,
            llm_provider=mock_llm,
            data_dir=temp_data_dir,
            repository=mock_repository,
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
        agent = Agent(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            llm_provider=mock_llm,
            data_dir=temp_data_dir,
            repository=mock_repository,
        )

        # 获取 system prompt
        prompt = await agent._get_system_prompt_for_event("command")

        # 验证使用了硬编码指令
        assert "执行皇帝的命令" in prompt
        assert "send_game_event" in prompt
        assert "执行动作" in prompt

    @pytest.mark.asyncio
    async def test_system_prompt_fallback_to_hardcoded(
        self, mock_event_bus, mock_llm, temp_data_dir, mock_repository
    ):
        """测试回退到硬编码指令"""
        # 创建 Agent 时不传入 SkillLoader
        agent = Agent(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            llm_provider=mock_llm,
            data_dir=temp_data_dir,
            repository=mock_repository,
            # 不传 skill_loader
        )

        # 获取 system prompt
        prompt = await agent._get_system_prompt_for_event("command")

        # 验证使用了硬编码指令
        assert "执行皇帝的命令" in prompt
        assert "send_game_event" in prompt

    @pytest.mark.asyncio
    async def test_system_prompt_fallback_when_skill_not_found(
        self, mock_event_bus, mock_llm, temp_data_dir, mock_repository
    ):
        """测试 Skill 加载失败时回退到硬编码"""
        # 创建 mock SkillLoader，但返回 None（模拟加载失败）
        mock_skill_loader = Mock()
        mock_skill_loader.load.return_value = None
        mock_skill_loader.registry.get_skill_for_event.return_value = "nonexistent_skill"

        # 创建 Agent 并注入 SkillLoader
        agent = Agent(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            llm_provider=mock_llm,
            data_dir=temp_data_dir,
            repository=mock_repository,
            skill_loader=mock_skill_loader,
        )

        # 获取 system prompt
        prompt = await agent._get_system_prompt_for_event("command")

        # 验证回退到硬编码指令
        assert "执行皇帝的命令" in prompt
        assert "send_game_event" in prompt

    @pytest.mark.asyncio
    async def test_system_prompt_task_session_uses_task_created_prompt(
        self, mock_event_bus, mock_llm, temp_data_dir, mock_repository
    ):
        """测试 task session 使用 TASK_CREATED 的 system prompt"""
        # 创建 Agent（不传入 SkillLoader）
        agent = Agent(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            llm_provider=mock_llm,
            data_dir=temp_data_dir,
            repository=mock_repository,
        )

        # Task session 应该使用 TASK_CREATED 的 prompt
        task_session_id = "task:test_agent:parent_session:123"
        prompt = await agent._get_system_prompt_for_event("agent_message", task_session_id)

        # 验证 task session 使用了 TASK_CREATED 的提示
        assert "Task Session" in prompt
        assert "单一目标" in prompt
        assert "finish_task_session" in prompt
        assert "创建者职责" in prompt
        assert "参与者职责" in prompt

    @pytest.mark.asyncio
    async def test_send_message_to_agent_with_await_reply_true(self, agent):
        """测试 send_message_to_agent 返回正确的等待消息（await_reply=true）"""
        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.COMMAND,
            payload={"command": "test"},
            session_id="test_session",
        )

        # 调用 send_message_to_agent with await_reply=true
        result = await agent._action_tools.send_message_to_agent(
            {"target_agent": "governor_zhili", "message": "请查收", "await_reply": True},
            event,
        )

        # 应该返回等待消息（不包含 ⏳，改为基于函数名称和参数检测）
        assert "等待回复" in result

        # 验证发送的事件使用的是当前 session（没有切换）
        assert agent.event_bus.send_event.called
        sent_event = agent.event_bus.send_event.call_args[0][0]
        assert sent_event.session_id == "test_session"
        # 验证没有 reply_to_session 字段
        assert "reply_to_session" not in sent_event.payload

    @pytest.mark.asyncio
    async def test_send_message_to_agent_with_await_reply_false(self, agent):
        """测试 send_message_to_agent 返回成功消息（await_reply=false）"""
        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.COMMAND,
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

        # 创建 mock SessionManager
        mock_session_manager = Mock()
        mock_session = Mock()
        mock_session.parent_id = "parent_session"
        mock_session.is_task = True
        mock_session.status = "ACTIVE"
        mock_session_manager.get_session = AsyncMock(return_value=mock_session)

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
