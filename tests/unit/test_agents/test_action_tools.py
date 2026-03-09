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
        mock_manifest = AsyncMock()
        mock_tape = MagicMock()
        mock_tape._get_tape_path = MagicMock(return_value=tmp_path / "tape.jsonl")

        manager = SessionManager(
            memory_dir=tmp_path,
            llm_provider=mock_llm,
            manifest_index=mock_manifest,
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

        assert result == "✅ 响应已发送"
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

        assert result == "✅ 响应已发送"
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

        assert result == "✅ 响应已发送"
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

        assert result == "✅ 响应已发送"
        assert mock_event_bus.send_event.called
        sent_event = mock_event_bus.send_event.call_args[0][0]
        # Should traverse all the way up to main session's creator
        assert sent_event.dst == ["player"]


class TestRespondToPlayerTapeWriting:
    """Test that respond_to_player writes RESPONSE events to tape"""

    @pytest.mark.asyncio
    async def test_respond_to_player_writes_to_tape(
        self, mock_event_bus, tmp_path
    ):
        """Test that respond_to_player writes RESPONSE event to tape"""
        # Create mock tape_writer
        mock_tape_writer = AsyncMock()
        mock_tape_writer.write_event = AsyncMock()

        # Create ActionTools with tape_writer
        action_tools = ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
            session_manager=None,
            tape_writer=mock_tape_writer,
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

        # Verify response was sent
        assert result == "✅ 响应已发送"
        assert mock_event_bus.send_event.called

        # Verify tape_writer.write_event was called with the RESPONSE event
        assert mock_tape_writer.write_event.called
        sent_event = mock_tape_writer.write_event.call_args[0][0]
        assert sent_event.type == "response"
        assert sent_event.payload["narrative"] == "Test response to player"
        assert sent_event.src == "agent:test_agent"

    @pytest.mark.asyncio
    async def test_respond_to_player_without_tape_writer_still_works(
        self, mock_event_bus, tmp_path
    ):
        """Test that respond_to_player works without tape_writer (backward compatibility)"""
        # Create ActionTools without tape_writer
        action_tools = ActionTools(
            agent_id="test_agent",
            event_bus=mock_event_bus,
            data_dir=tmp_path,
            session_manager=None,
            tape_writer=None,  # No tape_writer
        )

        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type="chat",
            payload={"message": "test"},
            session_id="test_session",
        )

        # Should not raise an error
        result = await action_tools.respond_to_player(
            {"content": "Test response"},
            event,
        )

        assert result == "✅ 响应已发送"
        assert mock_event_bus.send_event.called
