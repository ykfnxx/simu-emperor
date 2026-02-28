"""
Unit tests for Telegram message router
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from simu_emperor.adapters.telegram.router import MessageRouter
from simu_emperor.event_bus.event_types import EventType


@pytest.fixture
def mock_session():
    """Mock GameSession"""
    session = MagicMock()
    session.player_id = "player:telegram:123"
    session.chat_id = 123
    session.session_id = "session:telegram:123"
    session.event_bus = MagicMock()
    session.event_bus.send_event = AsyncMock()
    # Mock the async get_session_id_for_event method
    session.get_session_id_for_event = AsyncMock(return_value="session:telegram:123")
    return session


@pytest.mark.asyncio
async def test_router_parse_mentions_agent(mock_session):
    """Test parsing @agent mentions"""
    router = MessageRouter(mock_session)

    mentions, message = router._parse_mentions("@governor_zhili 你好")

    assert mentions == ["governor_zhili"]
    assert message == "你好"


@pytest.mark.asyncio
async def test_router_parse_mentions_all(mock_session):
    """Test parsing @all mentions"""
    router = MessageRouter(mock_session)

    mentions, message = router._parse_mentions("@all 大家好")

    assert mentions == ["all"]
    assert message == "大家好"


@pytest.mark.asyncio
async def test_router_parse_mentions_multiple(mock_session):
    """Test parsing multiple @mentions"""
    router = MessageRouter(mock_session)

    mentions, message = router._parse_mentions("@governor_zhili @minister_of_revenue 报告情况")

    assert set(mentions) == {"governor_zhili", "minister_of_revenue"}
    assert message == "报告情况"


@pytest.mark.asyncio
async def test_router_parse_command(mock_session):
    """Test parsing /cmd format"""
    router = MessageRouter(mock_session)

    intent, payload = router._parse_command("/cmd @governor_zhili 提高税收")

    assert intent == "command"
    assert payload["intent"] == "execute_command"
    assert payload["command"] == "提高税收"
    assert payload["agents"] == ["governor_zhili"]


@pytest.mark.asyncio
async def test_router_parse_chat(mock_session):
    """Test parsing chat format"""
    router = MessageRouter(mock_session)

    intent, payload = router._parse_chat("@governor_zhili 最近如何？")

    assert intent == "chat"
    assert payload["intent"] == "chat"
    assert payload["message"] == "最近如何？"
    assert payload["agents"] == ["governor_zhili"]


@pytest.mark.asyncio
async def test_router_route_and_send_chat(mock_session):
    """Test routing chat message"""
    router = MessageRouter(mock_session)

    reply_mock = AsyncMock()
    await router.route_and_send("@governor_zhili 你好", 123, reply_mock)

    # Verify event was sent
    mock_session.event_bus.send_event.assert_called_once()
    event = mock_session.event_bus.send_event.call_args[0][0]

    assert event.src == "player:telegram:123"
    assert event.dst == ["agent:governor_zhili"]
    assert event.type == EventType.CHAT
    assert event.payload["message"] == "你好"
    assert event.payload["chat_id"] == 123

    # Verify reply was sent
    reply_mock.assert_called_once()
    assert "✅" in reply_mock.call_args[0][0]


@pytest.mark.asyncio
async def test_router_route_and_send_command(mock_session):
    """Test routing command message"""
    router = MessageRouter(mock_session)

    reply_mock = AsyncMock()
    await router.route_and_send("/cmd @minister_of_revenue 调整税率", 123, reply_mock)

    # Verify event was sent
    mock_session.event_bus.send_event.assert_called_once()
    event = mock_session.event_bus.send_event.call_args[0][0]

    assert event.src == "player:telegram:123"
    assert event.dst == ["agent:minister_of_revenue"]
    assert event.type == EventType.COMMAND
    assert event.payload["command"] == "调整税率"
    assert event.payload["chat_id"] == 123


@pytest.mark.asyncio
async def test_router_route_and_send_broadcast(mock_session):
    """Test routing @all broadcast"""
    router = MessageRouter(mock_session)

    reply_mock = AsyncMock()
    await router.route_and_send("@all 各位卿家，局势如何？", 123, reply_mock)

    # Verify event was sent
    mock_session.event_bus.send_event.assert_called_once()
    event = mock_session.event_bus.send_event.call_args[0][0]

    assert event.src == "player:telegram:123"
    assert event.dst == ["*"]  # Broadcast to all
    assert event.type == EventType.CHAT
    assert event.payload["message"] == "各位卿家，局势如何？"


@pytest.mark.asyncio
async def test_router_route_and_send_no_mentions(mock_session):
    """Test routing without mentions returns error"""
    router = MessageRouter(mock_session)

    reply_mock = AsyncMock()
    await router.route_and_send("你好", 123, reply_mock)

    # Should not send event
    mock_session.event_bus.send_event.assert_not_called()

    # Should send error reply
    reply_mock.assert_called_once()
    assert "❌" in reply_mock.call_args[0][0] or "请使用" in reply_mock.call_args[0][0]


@pytest.mark.asyncio
async def test_router_route_and_send_no_event_bus(mock_session):
    """Test routing with uninitialized session"""
    mock_session.event_bus = None
    router = MessageRouter(mock_session)

    reply_mock = AsyncMock()
    await router.route_and_send("@governor_zhili 你好", 123, reply_mock)

    # Should send error reply
    reply_mock.assert_called_once()
    assert "❌" in reply_mock.call_args[0][0] or "未初始化" in reply_mock.call_args[0][0]
