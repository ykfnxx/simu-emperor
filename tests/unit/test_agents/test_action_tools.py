"""Tests for ActionTools class"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from simu_emperor.agents.tools.action_tools import ActionTools
from simu_emperor.event_bus.event import Event


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


class TestSendMessage:
    """Test unified send_message method"""

    @pytest.mark.asyncio
    async def test_send_message_rejects_self_message(
        self, action_tools, sample_event, mock_event_bus
    ):
        """Test that send_message rejects messages to oneself"""
        # Try to send message to oneself
        result = await action_tools.send_message(
            {"recipients": ["test_agent"], "content": "这是一条消息"},
            sample_event,
        )

        # Should return error message
        assert "❌" in result
        assert "不能向自己发送消息" in result

        # Verify no event was sent
        assert not mock_event_bus.send_event.called

    @pytest.mark.asyncio
    async def test_send_message_rejects_self_message_with_prefix(
        self, action_tools, sample_event, mock_event_bus
    ):
        """Test that send_message rejects messages to oneself with agent: prefix"""
        # Try to send message to oneself with agent: prefix
        result = await action_tools.send_message(
            {"recipients": ["agent:test_agent"], "content": "这是一条消息"},
            sample_event,
        )

        # Should return error message
        assert "❌" in result
        assert "不能向自己发送消息" in result

        # Verify no event was sent
        assert not mock_event_bus.send_event.called

    @pytest.mark.asyncio
    async def test_send_message_accepts_message_to_other_agent(
        self, action_tools, sample_event, mock_event_bus
    ):
        """Test that send_message accepts messages to other agents"""
        # Send message to different agent
        result = await action_tools.send_message(
            {"recipients": ["other_agent"], "content": "这是给其他官员的消息"},
            sample_event,
        )

        # Should return success message
        assert isinstance(result, tuple)
        status_msg, message_event = result
        assert "✅" in status_msg
        assert "消息已发送" in status_msg

        # Verify event was sent
        assert mock_event_bus.send_event.called
        assert message_event.dst == ["agent:other_agent"]
        assert message_event.type == "agent_message"
        assert message_event.payload["content"] == "这是给其他官员的消息"

    @pytest.mark.asyncio
    async def test_send_message_rejects_empty_recipients(
        self, action_tools, sample_event, mock_event_bus
    ):
        """Test that send_message rejects empty recipients"""
        result = await action_tools.send_message(
            {"recipients": [], "content": "这是一条消息"},
            sample_event,
        )

        # Should return error message
        assert "❌" in result
        assert "接收者列表不能为空" in result

        # Verify no event was sent
        assert not mock_event_bus.send_event.called

    @pytest.mark.asyncio
    async def test_send_message_rejects_empty_content(
        self, action_tools, sample_event, mock_event_bus
    ):
        """Test that send_message rejects empty content"""
        result = await action_tools.send_message(
            {"recipients": ["other_agent"], "content": ""},
            sample_event,
        )

        # Should return error message
        assert "❌" in result
        assert "消息内容不能为空" in result

        # Verify no event was sent
        assert not mock_event_bus.send_event.called

    @pytest.mark.asyncio
    async def test_send_message_to_player(
        self, action_tools, sample_event, mock_event_bus
    ):
        """Test that send_message can send to player"""
        result = await action_tools.send_message(
            {"recipients": ["player"], "content": "回复给玩家"},
            sample_event,
        )

        # Should return success message
        assert isinstance(result, tuple)
        status_msg, message_event = result
        assert "✅" in status_msg
        assert message_event.dst == ["player"]
        assert message_event.payload["content"] == "回复给玩家"

    @pytest.mark.asyncio
    async def test_send_message_to_multiple_recipients(
        self, action_tools, sample_event, mock_event_bus
    ):
        """Test that send_message can send to multiple recipients"""
        result = await action_tools.send_message(
            {"recipients": ["player", "other_agent"], "content": "群发消息"},
            sample_event,
        )

        # Should return success message
        assert isinstance(result, tuple)
        status_msg, message_event = result
        assert "✅" in status_msg
        assert set(message_event.dst) == {"player", "agent:other_agent"}

    @pytest.mark.asyncio
    async def test_send_message_normalizes_agent_ids(
        self, action_tools, sample_event, mock_event_bus
    ):
        """Test that send_message normalizes agent IDs (adds agent: prefix)"""
        result = await action_tools.send_message(
            {"recipients": ["other_agent", "agent:another_agent"], "content": "测试"},
            sample_event,
        )

        # Should return success message
        assert isinstance(result, tuple)
        status_msg, message_event = result
        assert "✅" in status_msg
        assert set(message_event.dst) == {"agent:other_agent", "agent:another_agent"}

    @pytest.mark.asyncio
    async def test_send_message_rejects_await_reply_to_player(
        self, action_tools, sample_event, mock_event_bus
    ):
        """Test that send_message rejects await_reply=true when sending to player"""
        result = await action_tools.send_message(
            {"recipients": ["player"], "content": "测试", "await_reply": True},
            sample_event,
        )

        # Should return error message
        assert "❌" in result
        assert "await_reply=true 只能用于 agent 间消息" in result

    @pytest.mark.asyncio
    async def test_send_message_rejects_player_in_task_session(
        self, mock_event_bus, sample_event, tmp_path
    ):
        """Test that task sessions cannot send messages directly to player."""
        mock_session = MagicMock()
        mock_session.is_task = True

        mock_session_manager = MagicMock()
        mock_session_manager.get_session = AsyncMock(return_value=mock_session)

        action_tools = ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
            session_manager=mock_session_manager,
        )

        result = await action_tools.send_message(
            {"recipients": ["player"], "content": "任务内回复给玩家"},
            sample_event,
        )

        assert "❌" in result
        assert "任务会话中禁止向 player 发送消息" in result
        assert not mock_event_bus.send_event.called



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
