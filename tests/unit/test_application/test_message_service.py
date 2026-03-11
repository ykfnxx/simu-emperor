"""Message Service unit tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from simu_emperor.application.message_service import MessageService


@pytest.fixture
def mock_event_bus():
    """Create mock event bus."""
    bus = MagicMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def mock_session_manager():
    """Create mock session manager."""
    return MagicMock()


@pytest.mark.asyncio
class TestMessageService:
    """Test MessageService."""

    def test_init(self, mock_event_bus, mock_session_manager):
        """Test message service initialization."""
        service = MessageService(
            event_bus=mock_event_bus,
            session_manager=mock_session_manager,
        )

        assert service.event_bus == mock_event_bus
        assert service.session_manager == mock_session_manager

    async def test_send_command(self, mock_event_bus, mock_session_manager):
        """Test sending command to agent."""
        service = MessageService(
            event_bus=mock_event_bus,
            session_manager=mock_session_manager,
        )

        await service.send_command(
            agent_id="governor_zhili",
            command="查看直隶情况",
            session_id="session:web:main",
        )

        mock_event_bus.publish.assert_called_once()
        call_args = mock_event_bus.publish.call_args
        event = call_args[0][0]
        assert "agent:governor_zhili" in event.dst
        assert event.payload["query"] == "查看直隶情况"

    async def test_send_command_with_agent_prefix(self, mock_event_bus, mock_session_manager):
        """Test sending command with agent: prefix."""
        service = MessageService(
            event_bus=mock_event_bus,
            session_manager=mock_session_manager,
        )

        await service.send_command(
            agent_id="agent:governor_zhili",
            command="查看情况",
            session_id="session:web:main",
        )

        call_args = mock_event_bus.publish.call_args
        event = call_args[0][0]
        assert event.dst == ["agent:governor_zhili"]

    async def test_send_chat(self, mock_event_bus, mock_session_manager):
        """Test sending chat to agent."""
        service = MessageService(
            event_bus=mock_event_bus,
            session_manager=mock_session_manager,
        )

        await service.send_chat(
            agent_id="governor_zhili",
            message="你好",
            session_id="session:web:main",
        )

        mock_event_bus.publish.assert_called_once()
        call_args = mock_event_bus.publish.call_args
        event = call_args[0][0]
        assert "agent:governor_zhili" in event.dst
        assert event.payload["message"] == "你好"

    async def test_broadcast(self, mock_event_bus, mock_session_manager):
        """Test broadcasting message to all agents."""
        service = MessageService(
            event_bus=mock_event_bus,
            session_manager=mock_session_manager,
        )

        await service.broadcast(
            message="大家注意",
            session_id="session:web:main",
        )

        call_args = mock_event_bus.publish.call_args
        event = call_args[0][0]
        assert event.dst == ["*"]

    async def test_broadcast_to_specific_agents(self, mock_event_bus, mock_session_manager):
        """Test broadcasting to specific agents."""
        service = MessageService(
            event_bus=mock_event_bus,
            session_manager=mock_session_manager,
        )

        await service.broadcast(
            message="请注意",
            session_id="session:web:main",
            agent_ids=["governor_zhili", "minister_of_revenue"],
        )

        call_args = mock_event_bus.publish.call_args
        event = call_args[0][0]
        assert "agent:governor_zhili" in event.dst
        assert "agent:minister_of_revenue" in event.dst

    async def test_send_to_group(self, mock_event_bus, mock_session_manager):
        """Test sending to group chat."""
        service = MessageService(
            event_bus=mock_event_bus,
            session_manager=mock_session_manager,
        )

        # Currently returns empty list - would need GroupChatService integration
        result = await service.send_to_group(
            group_id="group:web:001",
            message="群消息",
            session_id="session:web:main",
        )

        assert result == []

    def test_normalize_agent_id(self, mock_event_bus, mock_session_manager):
        """Test agent ID normalization."""
        service = MessageService(
            event_bus=mock_event_bus,
            session_manager=mock_session_manager,
        )

        assert service._normalize_agent_id("agent:governor_zhili") == "governor_zhili"
        assert service._normalize_agent_id("governor_zhili") == "governor_zhili"

    async def test_parse_message_command(self, mock_event_bus, mock_session_manager):
        """Test parsing command message."""
        service = MessageService(
            event_bus=mock_event_bus,
            session_manager=mock_session_manager,
        )

        result = await service.parse_message("/help")

        assert result["type"] == "command"
        assert result["command"] == "help"
        assert result["args"] == ""

    async def test_parse_message_command_with_args(self, mock_event_bus, mock_session_manager):
        """Test parsing command with arguments."""
        service = MessageService(
            event_bus=mock_event_bus,
            session_manager=mock_session_manager,
        )

        result = await service.parse_message("/create_session Test Session")

        assert result["type"] == "command"
        assert result["command"] == "create_session"
        assert result["args"] == "Test Session"

    async def test_parse_message_chat(self, mock_event_bus, mock_session_manager):
        """Test parsing chat message."""
        service = MessageService(
            event_bus=mock_event_bus,
            session_manager=mock_session_manager,
        )

        result = await service.parse_message("你好，你好吗？")

        assert result["type"] == "chat"
        assert result["text"] == "你好，你好吗？"

    async def test_parse_message_whitespace(self, mock_event_bus, mock_session_manager):
        """Test parsing message with whitespace."""
        service = MessageService(
            event_bus=mock_event_bus,
            session_manager=mock_session_manager,
        )

        result = await service.parse_message("  查看情况  ")

        assert result["type"] == "chat"
        assert result["text"] == "查看情况"
