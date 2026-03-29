"""
MQSubscriber测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from simu_emperor.mq.subscriber import MQSubscriber
from simu_emperor.mq.event import Event


@pytest.mark.asyncio
async def test_subscriber_connect():
    subscriber = MQSubscriber("ipc://@test_broadcast")

    with patch("zmq.asyncio.Context") as mock_ctx:
        mock_socket = MagicMock()
        mock_ctx.return_value.socket.return_value = mock_socket

        await subscriber.connect()

        assert subscriber._connected
        mock_socket.connect.assert_called_once_with("ipc://@test_broadcast")


@pytest.mark.asyncio
async def test_subscriber_subscribe():
    subscriber = MQSubscriber("ipc://@test_broadcast")
    subscriber._connected = True
    subscriber._socket = MagicMock()

    subscriber.subscribe("TICK_COMPLETED")

    subscriber._socket.setsockopt.assert_called_once()
    topic = subscriber._socket.setsockopt.call_args[0][1]
    assert topic == b"TICK_COMPLETED"


@pytest.mark.asyncio
async def test_subscriber_receive_event():
    subscriber = MQSubscriber("ipc://@test_broadcast")
    subscriber._connected = True
    subscriber._socket = AsyncMock()

    event_json = '{"event_id":"evt_test","event_type":"TICK_COMPLETED","src":"engine:*","dst":["broadcast:*"],"session_id":"system","payload":{"tick":42},"timestamp":"2026-03-29T10:00:00"}'
    subscriber._socket.recv_multipart.return_value = [b"TICK_COMPLETED", event_json.encode("utf-8")]

    topic, event = await subscriber.receive_event()

    assert topic == "TICK_COMPLETED"
    assert event.event_id == "evt_test"
    assert event.payload["tick"] == 42


@pytest.mark.asyncio
async def test_subscriber_not_connected_error():
    subscriber = MQSubscriber("ipc://@test_broadcast")

    with pytest.raises(RuntimeError, match="not connected"):
        subscriber.subscribe("topic")

    with pytest.raises(RuntimeError, match="not connected"):
        await subscriber.receive()


@pytest.mark.asyncio
async def test_subscriber_invalid_parts():
    subscriber = MQSubscriber("ipc://@test_broadcast")
    subscriber._connected = True
    subscriber._socket = AsyncMock()
    subscriber._socket.recv_multipart.return_value = [b"only_one_part"]

    with pytest.raises(ValueError, match="Expected 2 parts"):
        await subscriber.receive()


@pytest.mark.asyncio
async def test_subscriber_context_manager():
    with patch("zmq.asyncio.Context") as mock_ctx:
        mock_socket = MagicMock()
        mock_ctx.return_value.socket.return_value = mock_socket

        async with MQSubscriber("ipc://@test_broadcast") as subscriber:
            assert subscriber._connected

        assert not subscriber._connected


@pytest.mark.asyncio
async def test_subscriber_close():
    with patch("zmq.asyncio.Context") as mock_ctx:
        mock_socket = MagicMock()
        mock_ctx.return_value.socket.return_value = mock_socket

        subscriber = MQSubscriber("ipc://@test_broadcast")
        await subscriber.connect()
        assert subscriber._connected

        await subscriber.close()

        assert not subscriber._connected
        assert subscriber._socket is None
        assert subscriber._ctx is None
        mock_socket.close.assert_called_once()


@pytest.mark.asyncio
async def test_subscriber_reconnect_warning():
    subscriber = MQSubscriber("ipc://@test_broadcast")
    subscriber._connected = True
    subscriber._socket = MagicMock()

    await subscriber.connect()

    assert subscriber._connected


@pytest.mark.asyncio
async def test_subscriber_multiple_topics():
    subscriber = MQSubscriber("ipc://@test_broadcast")
    subscriber._connected = True
    subscriber._socket = MagicMock()

    subscriber.subscribe("TICK_COMPLETED")
    subscriber.subscribe("AGENT_MESSAGE")

    assert subscriber._socket.setsockopt.call_count == 2


@pytest.mark.asyncio
async def test_subscriber_receive_raw():
    subscriber = MQSubscriber("ipc://@test_broadcast")
    subscriber._connected = True
    subscriber._socket = AsyncMock()
    subscriber._socket.recv_multipart.return_value = [b"RAW_TOPIC", b"raw data"]

    topic, data = await subscriber.receive()

    assert topic == "RAW_TOPIC"
    assert data == "raw data"
