"""Tests for ActionTools class"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from simu_emperor.agents.tools.action_tools import ActionTools
from simu_emperor.event_bus.event import Event
from simu_emperor.session import SessionManager


@pytest.fixture
def mock_event_bus():
    """Mock EventBus"""
    event_bus = MagicMock()
    event_bus.send_event = AsyncMock()
    return event_bus


@pytest.fixture
def action_tools(mock_event_bus, tmp_path):
    """Create ActionTools instance"""
    return ActionTools(
        agent_id="test_agent",
        event_bus=mock_event_bus,
        data_dir=tmp_path,
        session_manager=None,  # No session_manager needed for basic tests
    )


@pytest.fixture
def sample_event():
    """Create sample Event"""
    return Event(
        src="player",
        dst=["agent:test_agent"],
        type="command",
        payload={"command": "test"},
        session_id="test_session",
    )


class TestActionTools:
    """Test ActionTools class"""

    @pytest.mark.asyncio
    async def test_send_message_to_agent_rejects_self_message(
        self, action_tools, sample_event, mock_event_bus
    ):
        """Test that send_message_to_agent rejects messages to oneself"""
        # Try to send message to oneself
        result = await action_tools.send_message_to_agent(
            {"target_agent": "test_agent", "message": "这是一条消息"},
            sample_event,
        )

        # Should return error message
        assert "❌" in result
        assert "不能向自己发送消息" in result

        # Verify no event was sent
        assert not mock_event_bus.send_event.called

    @pytest.mark.asyncio
    async def test_send_message_to_agent_rejects_self_message_with_prefix(
        self, action_tools, sample_event, mock_event_bus
    ):
        """Test that send_message_to_agent rejects messages to oneself with agent: prefix"""
        # Try to send message to oneself with agent: prefix
        result = await action_tools.send_message_to_agent(
            {"target_agent": "agent:test_agent", "message": "这是一条消息"},
            sample_event,
        )

        # Should return error message
        assert "❌" in result
        assert "不能向自己发送消息" in result

        # Verify no event was sent
        assert not mock_event_bus.send_event.called

    @pytest.mark.asyncio
    async def test_send_message_to_agent_accepts_message_to_other_agent(
        self, action_tools, sample_event, mock_event_bus
    ):
        """Test that send_message_to_agent accepts messages to other agents"""
        # Send message to different agent
        result = await action_tools.send_message_to_agent(
            {"target_agent": "other_agent", "message": "这是给其他官员的消息"},
            sample_event,
        )

        # Should return success message
        assert "✅" in result
        assert "消息已发送" in result

        # Verify event was sent
        assert mock_event_bus.send_event.called
        sent_event = mock_event_bus.send_event.call_args[0][0]
        assert sent_event.dst == ["agent:other_agent"]

    @pytest.mark.asyncio
    async def test_send_message_to_agent_rejects_empty_target(
        self, action_tools, sample_event, mock_event_bus
    ):
        """Test that send_message_to_agent rejects empty target"""
        result = await action_tools.send_message_to_agent(
            {"target_agent": "", "message": "这是一条消息"},
            sample_event,
        )

        # Should return error message
        assert "❌" in result
        assert "目标官员不能为空" in result

        # Verify no event was sent
        assert not mock_event_bus.send_event.called

    @pytest.mark.asyncio
    async def test_send_message_to_agent_rejects_empty_message(
        self, action_tools, sample_event, mock_event_bus
    ):
        """Test that send_message_to_agent rejects empty message"""
        result = await action_tools.send_message_to_agent(
            {"target_agent": "other_agent", "message": ""},
            sample_event,
        )

        # Should return error message
        assert "❌" in result
        assert "消息内容不能为空" in result

        # Verify no event was sent
        assert not mock_event_bus.send_event.called


class TestRespondToPlayer:
    """Test respond_to_player method"""

    @pytest.fixture
    def mock_event_bus(self):
        """Mock EventBus"""
        event_bus = MagicMock()
        event_bus.send_event = AsyncMock()
        return event_bus

    @pytest.fixture
    async def session_manager(self, tmp_path):
        """Create SessionManager for testing"""
        mock_llm = MagicMock()
        mock_tape_metadata_mgr = AsyncMock()
        mock_tape = MagicMock()
        mock_tape._get_tape_path = MagicMock(return_value=tmp_path / "tape.jsonl")

        manager = SessionManager(
            memory_dir=tmp_path,
            llm_provider=mock_llm,
            tape_metadata_mgr=mock_tape_metadata_mgr,
            tape_writer=mock_tape,
        )
        return manager

    @pytest.mark.asyncio
    async def test_respond_to_player_without_session_manager(self, mock_event_bus, tmp_path):
        """Test respond_to_player without session_manager uses default 'player'"""
        action_tools = ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
            session_manager=None,
        )

        event = Event(
            src="agent:other_agent",  # Source is another agent
            dst=["agent:test_agent"],
            type="command",
            payload={},
            session_id="test_session",
        )

        result = await action_tools.respond_to_player(
            {"content": "Test response"},
            event,
        )

        # V4: respond_to_player 返回元组 (message, event)
        assert isinstance(result, tuple)
        assert result[0] == "✅ 响应已发送"
        assert mock_event_bus.send_event.called
        sent_event = mock_event_bus.send_event.call_args[0][0]
        # Should send to default "player" since no session_manager
        assert sent_event.dst == ["player"]
        assert sent_event.payload["narrative"] == "Test response"

    @pytest.mark.asyncio
    async def test_respond_to_player_in_main_session(
        self, mock_event_bus, session_manager, tmp_path
    ):
        """Test respond_to_player in main session sends to session's creator"""
        action_tools = ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
            session_manager=session_manager,
        )

        # Create main session created by player
        await session_manager.create_session(
            session_id="main_session",
            created_by="player",
        )

        event = Event(
            src="agent:other_agent",
            dst=["agent:test_agent"],
            type="command",
            payload={},
            session_id="main_session",
        )

        result = await action_tools.respond_to_player(
            {"content": "Response in main session"},
            event,
        )

        # V4: respond_to_player 返回元组 (message, event)
        assert isinstance(result, tuple)
        assert result[0] == "✅ 响应已发送"
        assert mock_event_bus.send_event.called
        sent_event = mock_event_bus.send_event.call_args[0][0]
        # Should send to main session's creator ("player")
        assert sent_event.dst == ["player"]
        assert sent_event.payload["narrative"] == "Response in main session"

    @pytest.mark.asyncio
    async def test_respond_to_player_in_task_session_traverses_to_main(
        self, mock_event_bus, session_manager, tmp_path
    ):
        """Test respond_to_player in task session traverses to main session"""
        action_tools = ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
            session_manager=session_manager,
        )

        # Create main session created by player
        await session_manager.create_session(
            session_id="main_session",
            created_by="player",
        )

        # Create task session created by agent_a
        task_session = await session_manager.create_session(
            parent_id="main_session",
            created_by="agent:agent_a",
            timeout_seconds=300,
        )

        # Event is from agent:agent_a (in task session context)
        event = Event(
            src="agent:agent_a",  # Source is the agent who created the task
            dst=["agent:test_agent"],
            type="agent_message",  # Simulating agent-to-agent message
            payload={},
            session_id=task_session.session_id,
        )

        result = await action_tools.respond_to_player(
            {"content": "Response from task session"},
            event,
        )

        # V4: respond_to_player 返回元组 (message, event)
        assert isinstance(result, tuple)
        assert result[0] == "✅ 响应已发送"
        assert mock_event_bus.send_event.called
        sent_event = mock_event_bus.send_event.call_args[0][0]
        # Should send to main session's creator ("player"), NOT to agent:agent_a
        assert sent_event.dst == ["player"]
        assert sent_event.payload["narrative"] == "Response from task session"

    @pytest.mark.asyncio
    async def test_respond_to_player_in_nested_task_sessions(
        self, mock_event_bus, session_manager, tmp_path
    ):
        """Test respond_to_player in deeply nested task sessions"""
        action_tools = ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
            session_manager=session_manager,
        )

        # Create main session
        await session_manager.create_session(
            session_id="main_session",
            created_by="player",
        )

        # Create first level task session
        task1 = await session_manager.create_session(
            parent_id="main_session",
            created_by="agent:agent_a",
            timeout_seconds=300,
        )

        # Create second level task session
        task2 = await session_manager.create_session(
            parent_id=task1.session_id,
            created_by="agent:agent_b",
            timeout_seconds=300,
        )

        event = Event(
            src="agent:agent_b",
            dst=["agent:test_agent"],
            type="agent_message",
            payload={},
            session_id=task2.session_id,
        )

        result = await action_tools.respond_to_player(
            {"content": "Response from nested task session"},
            event,
        )

        # V4: respond_to_player 返回元组 (message, event)
        assert isinstance(result, tuple)
        assert result[0] == "✅ 响应已发送"
        assert mock_event_bus.send_event.called
        sent_event = mock_event_bus.send_event.call_args[0][0]
        # Should traverse all the way up to main session's creator
        assert sent_event.dst == ["player"]


class TestRespondToPlayerTapeWriting:
    """Test that respond_to_player writes RESPONSE events to tape"""

    @pytest.mark.asyncio
    async def test_respond_to_player_writes_to_tape(self, mock_event_bus, tmp_path):
        """V4: respond_to_player 返回事件，由 Agent 统一通过 ContextManager 管理"""
        # V4: ActionTools 不再需要 tape_writer 参数
        action_tools = ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
            session_manager=None,
        )

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type="chat",
            payload={"message": "test"},
            session_id="test_session",
        )

        result = await action_tools.respond_to_player(
            {"content": "Test response to player"},
            event,
        )

        # V4: 返回元组 (message, event)
        assert isinstance(result, tuple)
        assert len(result) == 2
        message, response_event = result
        assert message == "✅ 响应已发送"
        assert response_event.type == "response"
        assert response_event.payload["narrative"] == "Test response to player"
        assert response_event.src == "agent:test_agent"

        # Verify event was sent to event_bus
        assert mock_event_bus.send_event.called

    @pytest.mark.asyncio
    async def test_respond_to_player_without_tape_writer_still_works(
        self, mock_event_bus, tmp_path
    ):
        """V4: tape_writer 不再作为参数传递"""
        # V4: ActionTools 不再需要 tape_writer 参数
        action_tools = ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
            session_manager=None,
        )

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type="chat",
            payload={"message": "test"},
            session_id="test_session",
        )

        result = await action_tools.respond_to_player(
            {"content": "Test response"},
            event,
        )

        # V4: 返回元组 (message, event)
        assert isinstance(result, tuple)
        assert len(result) == 2
        message, response_event = result
        assert message == "✅ 响应已发送"
        assert mock_event_bus.send_event.called


class TestCreateIncident:
    """Test create_incident method (V4)."""

    @pytest.fixture
    def mock_event_bus(self):
        """Mock EventBus"""
        event_bus = MagicMock()
        event_bus.send_event = AsyncMock()
        return event_bus

    @pytest.mark.asyncio
    async def test_create_incident_with_add_effect(self, mock_event_bus, tmp_path):
        """Test create_incident with add effect on stockpile."""
        action_tools = ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
            session_manager=None,
        )

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type="chat",
            payload={},
            session_id="test_session",
        )

        result = await action_tools.create_incident(
            {
                "title": "拨款",
                "description": "国库拨款给直隶",
                "effects": [
                    {
                        "target_path": "provinces.zhili.stockpile",
                        "add": 5000,
                        "factor": None,
                    }
                ],
                "duration_ticks": 3,
            },
            event,
        )

        # Should return success message
        assert "✅" in result
        assert "事件已创建" in result
        assert "拨款" in result
        assert "3 ticks" in result

        # Verify event was sent
        assert mock_event_bus.send_event.called
        sent_event = mock_event_bus.send_event.call_args[0][0]
        assert sent_event.type == "incident_created"
        assert sent_event.dst == ["system:engine"]
        assert sent_event.payload["title"] == "拨款"
        assert sent_event.payload["description"] == "国库拨款给直隶"
        assert sent_event.payload["remaining_ticks"] == 3
        assert sent_event.payload["source"] == "test_agent"

    @pytest.mark.asyncio
    async def test_create_incident_with_factor_effect(self, mock_event_bus, tmp_path):
        """Test create_incident with factor effect on production_value."""
        action_tools = ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
            session_manager=None,
        )

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type="chat",
            payload={},
            session_id="test_session",
        )

        result = await action_tools.create_incident(
            {
                "title": "丰收",
                "description": "今年大丰收",
                "effects": [
                    {
                        "target_path": "provinces.zhili.production_value",
                        "add": None,
                        "factor": 0.1,
                    }
                ],
                "duration_ticks": 2,
            },
            event,
        )

        assert "✅" in result
        assert "丰收" in result

        sent_event = mock_event_bus.send_event.call_args[0][0]
        assert sent_event.type == "incident_created"
        assert sent_event.payload["effects"][0]["factor"] == "0.1"
        assert sent_event.payload["effects"][0]["add"] is None

    @pytest.mark.asyncio
    async def test_create_incident_with_imperial_treasury_add(self, mock_event_bus, tmp_path):
        """Test create_incident with add effect on imperial_treasury."""
        action_tools = ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
            session_manager=None,
        )

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type="chat",
            payload={},
            session_id="test_session",
        )

        result = await action_tools.create_incident(
            {
                "title": "税收",
                "description": "增加国库",
                "effects": [
                    {
                        "target_path": "nation.imperial_treasury",
                        "add": 10000,
                        "factor": None,
                    }
                ],
                "duration_ticks": 1,
            },
            event,
        )

        assert "✅" in result
        sent_event = mock_event_bus.send_event.call_args[0][0]
        assert sent_event.payload["effects"][0]["target_path"] == "nation.imperial_treasury"

    @pytest.mark.asyncio
    async def test_create_incident_with_multiple_effects(self, mock_event_bus, tmp_path):
        """Test create_incident with multiple effects."""
        action_tools = ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
            session_manager=None,
        )

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type="chat",
            payload={},
            session_id="test_session",
        )

        result = await action_tools.create_incident(
            {
                "title": "复合事件",
                "description": "多效果事件",
                "effects": [
                    {
                        "target_path": "provinces.zhili.stockpile",
                        "add": 1000,
                        "factor": None,
                    },
                    {
                        "target_path": "provinces.zhili.production_value",
                        "add": None,
                        "factor": 0.05,
                    },
                ],
                "duration_ticks": 3,
            },
            event,
        )

        assert "✅" in result
        sent_event = mock_event_bus.send_event.call_args[0][0]
        assert len(sent_event.payload["effects"]) == 2

    @pytest.mark.asyncio
    async def test_create_incident_generates_unique_id(self, mock_event_bus, tmp_path):
        """Test that create_incident generates unique incident IDs."""
        action_tools = ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
            session_manager=None,
        )

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type="chat",
            payload={},
            session_id="test_session",
        )

        args = {
            "title": "测试",
            "description": "测试事件",
            "effects": [{"target_path": "provinces.zhili.stockpile", "add": 100, "factor": None}],
            "duration_ticks": 1,
        }

        await action_tools.create_incident(args, event)
        first_event = mock_event_bus.send_event.call_args[0][0]
        first_id = first_event.payload["incident_id"]

        mock_event_bus.send_event.reset_mock()

        await action_tools.create_incident(args, event)
        second_event = mock_event_bus.send_event.call_args[0][0]
        second_id = second_event.payload["incident_id"]

        # IDs should be different (different timestamp/uuid)
        assert first_id != second_id
        assert first_id.startswith("inc_")
        assert second_id.startswith("inc_")


class TestValidateAndBuildEffects:
    """Test _validate_and_build_effects method (V4)."""

    @pytest.fixture
    def action_tools(self, tmp_path):
        """Create ActionTools instance."""
        mock_event_bus = MagicMock()
        return ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
            session_manager=None,
        )

    def test_validate_add_on_stockpile(self, action_tools):
        """Test add effect on province stockpile is valid."""
        effects = action_tools._validate_and_build_effects(
            [{"target_path": "provinces.zhili.stockpile", "add": 1000, "factor": None}]
        )

        assert len(effects) == 1
        assert effects[0]["target_path"] == "provinces.zhili.stockpile"
        assert effects[0]["add"] == "1000"
        assert effects[0]["factor"] is None

    def test_validate_add_on_imperial_treasury(self, action_tools):
        """Test add effect on imperial_treasury is valid."""
        effects = action_tools._validate_and_build_effects(
            [{"target_path": "nation.imperial_treasury", "add": 5000, "factor": None}]
        )

        assert len(effects) == 1
        assert effects[0]["target_path"] == "nation.imperial_treasury"
        assert effects[0]["add"] == "5000"

    def test_validate_factor_on_production_value(self, action_tools):
        """Test factor effect on production_value is valid."""
        effects = action_tools._validate_and_build_effects(
            [{"target_path": "provinces.zhili.production_value", "add": None, "factor": 0.1}]
        )

        assert len(effects) == 1
        assert effects[0]["factor"] == "0.1"
        assert effects[0]["add"] is None

    def test_validate_factor_on_population(self, action_tools):
        """Test factor effect on population is valid."""
        effects = action_tools._validate_and_build_effects(
            [{"target_path": "provinces.jiangsu.population", "add": None, "factor": -0.05}]
        )

        assert len(effects) == 1
        assert effects[0]["factor"] == "-0.05"

    def test_validate_add_on_invalid_path_raises(self, action_tools):
        """Test add effect on invalid path raises ValueError."""
        with pytest.raises(ValueError, match="add 类型效果只能作用于"):
            action_tools._validate_and_build_effects(
                [{"target_path": "provinces.zhili.production_value", "add": 100, "factor": None}]
            )

    def test_validate_factor_on_invalid_path_raises(self, action_tools):
        """Test factor effect on invalid path raises ValueError."""
        with pytest.raises(ValueError, match="factor 类型效果只能作用于"):
            action_tools._validate_and_build_effects(
                [{"target_path": "provinces.zhili.stockpile", "add": None, "factor": 0.1}]
            )

    def test_validate_effect_without_add_or_factor_raises(self, action_tools):
        """Test effect without add or factor raises ValueError."""
        with pytest.raises(ValueError, match="Effect 必须指定 add 或 factor"):
            action_tools._validate_and_build_effects(
                [{"target_path": "provinces.zhili.stockpile", "add": None, "factor": None}]
            )

    def test_validate_decimal_precision(self, action_tools):
        """Test that effect values are converted to Decimal strings."""
        effects = action_tools._validate_and_build_effects(
            [{"target_path": "provinces.zhili.stockpile", "add": 1234.56, "factor": None}]
        )

        # Should be converted to string representation of Decimal
        assert effects[0]["add"] == "1234.56"

    def test_validate_multiple_effects(self, action_tools):
        """Test validation of multiple effects in one incident."""
        effects = action_tools._validate_and_build_effects(
            [
                {"target_path": "provinces.zhili.stockpile", "add": 1000, "factor": None},
                {"target_path": "provinces.zhili.production_value", "add": None, "factor": 0.1},
            ]
        )

        assert len(effects) == 2
