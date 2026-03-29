"""
MQPublisher测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from simu_emperor.mq.publisher import MQPublisher
from simu_emperor.mq.event import Event


@pytest.mark.asyncio
async def test_publisher_bind():
    publisher = MQPublisher("ipc://@test_broadcast")

    with patch("zmq.asyncio.Context") as mock_ctx:
        mock_socket = MagicMock()
        mock_ctx.return_value.socket.return_value = mock_socket

        await publisher.bind()

        assert publisher._bound
        mock_socket.bind.assert_called_once_with("ipc://@test_broadcast")


@pytest.mark.asyncio
async def test_publisher_publish_event():
    publisher = MQPublisher("ipc://@test_broadcast")
    publisher._bound = True
    publisher._socket = AsyncMock()

    event = Event(
        event_id="evt_test",
        event_type="TICK_COMPLETED",
        src="engine:*",
        dst=["broadcast:*"],
        session_id="system",
        payload={"tick": 42},
        timestamp="2026-03-29T10:00:00",
    )

    await publisher.publish_event(event)

    publisher._socket.send_multipart.assert_called_once()
    topic, data = publisher._socket.send_multipart.call_args[0][0]
    assert topic == b"TICK_COMPLETED"
    assert b"evt_test" in data


@pytest.mark.asyncio
async def test_publisher_publish_with_custom_topic():
    publisher = MQPublisher("ipc://@test_broadcast")
    publisher._bound = True
    publisher._socket = AsyncMock()

    await publisher.publish("custom_topic", "test data")

    topic, data = publisher._socket.send_multipart.call_args[0][0]
    assert topic == b"custom_topic"
    assert data == b"test data"


@pytest.mark.asyncio
async def test_publisher_not_bound_error():
    publisher = MQPublisher("ipc://@test_broadcast")

    with pytest.raises(RuntimeError, match="not bound"):
        await publisher.publish("topic", "data")


@pytest.mark.asyncio
async def test_publisher_context_manager():
    with patch("zmq.asyncio.Context") as mock_ctx:
        mock_socket = MagicMock()
        mock_ctx.return_value.socket.return_value = mock_socket

        async with MQPublisher("ipc://@test_broadcast") as publisher:
            assert publisher._bound

        assert not publisher._bound


@pytest.mark.asyncio
async def test_publisher_close():
    with patch("zmq.asyncio.Context") as mock_ctx:
        mock_socket = MagicMock()
        mock_ctx.return_value.socket.return_value = mock_socket

        publisher = MQPublisher("ipc://@test_broadcast")
        await publisher.bind()
        assert publisher._bound

        await publisher.close()

        assert not publisher._bound
        assert publisher._socket is None
        assert publisher._ctx is None
        mock_socket.close.assert_called_once()


@pytest.mark.asyncio
async def test_publisher_rebind_warning():
    publisher = MQPublisher("ipc://@test_broadcast")
    publisher._bound = True
    publisher._socket = MagicMock()

    await publisher.bind()

    assert publisher._bound


@pytest.mark.asyncio
async def test_publisher_publish_bytes():
    publisher = MQPublisher("ipc://@test_broadcast")
    publisher._bound = True
    publisher._socket = AsyncMock()

    await publisher.publish("topic", b"bytes data")

    topic, data = publisher._socket.send_multipart.call_args[0][0]
    assert topic == b"topic"
    assert data == b"bytes data"


@pytest.mark.asyncio
async def test_publisher_publish_event_custom_topic():
    publisher = MQPublisher("ipc://@test_broadcast")
    publisher._bound = True
    publisher._socket = AsyncMock()

    event = Event(
        event_id="evt_test",
        event_type="CHAT",
        src="player:web:001",
        dst=["agent:governor"],
        session_id="session:001",
        payload={"message": "test"},
        timestamp="2026-03-29T10:00:00",
    )

    await publisher.publish_event(event, topic="CUSTOM_TOPIC")

    topic, data = publisher._socket.send_multipart.call_args[0][0]
    assert topic == b"CUSTOM_TOPIC"
    assert b"evt_test" in data
