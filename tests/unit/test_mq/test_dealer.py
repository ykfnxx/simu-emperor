"""
MQDealer测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from simu_emperor.mq.dealer import MQDealer
from simu_emperor.mq.event import Event


@pytest.mark.asyncio
async def test_dealer_connect():
    dealer = MQDealer("ipc://@test_router", identity="test_worker")

    with patch("zmq.asyncio.Context") as mock_ctx:
        mock_socket = MagicMock()
        mock_ctx.return_value.socket.return_value = mock_socket

        await dealer.connect()

        assert dealer._connected
        mock_socket.connect.assert_called_once_with("ipc://@test_router")


@pytest.mark.asyncio
async def test_dealer_send_event():
    dealer = MQDealer("ipc://@test_router")
    dealer._connected = True
    dealer._socket = AsyncMock()

    event = Event(
        event_id="evt_test",
        event_type="CHAT",
        src="player:web:001",
        dst=["agent:governor"],
        session_id="session:001",
        payload={"message": "test"},
        timestamp="2026-03-29T10:00:00",
    )

    await dealer.send_event(event)

    dealer._socket.send.assert_called_once()
    sent_data = dealer._socket.send.call_args[0][0]
    assert b"evt_test" in sent_data


@pytest.mark.asyncio
async def test_dealer_receive_event():
    dealer = MQDealer("ipc://@test_router")
    dealer._connected = True
    dealer._socket = AsyncMock()

    event_json = '{"event_id":"evt_test","event_type":"CHAT","src":"player:web:001","dst":["agent:governor"],"session_id":"session:001","payload":{"message":"test"},"timestamp":"2026-03-29T10:00:00"}'
    dealer._socket.recv.return_value = event_json.encode("utf-8")

    event = await dealer.receive_event()

    assert event.event_id == "evt_test"
    assert event.event_type == "CHAT"


@pytest.mark.asyncio
async def test_dealer_context_manager():
    with patch("zmq.asyncio.Context") as mock_ctx:
        mock_socket = MagicMock()
        mock_ctx.return_value.socket.return_value = mock_socket

        async with MQDealer("ipc://@test_router") as dealer:
            assert dealer._connected

        assert not dealer._connected


@pytest.mark.asyncio
async def test_dealer_not_connected_error():
    dealer = MQDealer("ipc://@test_router")

    with pytest.raises(RuntimeError, match="not connected"):
        await dealer.send("test")

    with pytest.raises(RuntimeError, match="not connected"):
        await dealer.receive()


@pytest.mark.asyncio
async def test_dealer_send_raw_string():
    dealer = MQDealer("ipc://@test_router")
    dealer._connected = True
    dealer._socket = AsyncMock()

    await dealer.send("raw string data")

    dealer._socket.send.assert_called_once()
    sent_data = dealer._socket.send.call_args[0][0]
    assert sent_data == b"raw string data"


@pytest.mark.asyncio
async def test_dealer_send_bytes():
    dealer = MQDealer("ipc://@test_router")
    dealer._connected = True
    dealer._socket = AsyncMock()

    await dealer.send(b"bytes data")

    dealer._socket.send.assert_called_once_with(b"bytes data")


@pytest.mark.asyncio
async def test_dealer_receive_raw():
    dealer = MQDealer("ipc://@test_router")
    dealer._connected = True
    dealer._socket = AsyncMock()
    dealer._socket.recv.return_value = b"raw response"

    data = await dealer.receive()

    assert data == "raw response"


@pytest.mark.asyncio
async def test_dealer_receive_with_timeout():
    dealer = MQDealer("ipc://@test_router")
    dealer._connected = True
    dealer._socket = AsyncMock()
    dealer._socket.recv.return_value = b"response"

    data = await dealer.receive(timeout=5.0)

    assert data == "response"


@pytest.mark.asyncio
async def test_dealer_receive_timeout_expired():
    import asyncio

    dealer = MQDealer("ipc://@test_router")
    dealer._connected = True
    dealer._socket = AsyncMock()

    async def slow_recv():
        await asyncio.sleep(10)
        return b"too late"

    dealer._socket.recv.side_effect = slow_recv

    with pytest.raises(asyncio.TimeoutError):
        await dealer.receive(timeout=0.1)


@pytest.mark.asyncio
async def test_dealer_close():
    with patch("zmq.asyncio.Context") as mock_ctx:
        mock_socket = MagicMock()
        mock_ctx.return_value.socket.return_value = mock_socket

        dealer = MQDealer("ipc://@test_router")
        await dealer.connect()
        assert dealer._connected

        await dealer.close()

        assert not dealer._connected
        assert dealer._socket is None
        assert dealer._ctx is None
        mock_socket.close.assert_called_once()


@pytest.mark.asyncio
async def test_dealer_identity():
    with patch("zmq.asyncio.Context") as mock_ctx:
        mock_socket = MagicMock()
        mock_ctx.return_value.socket.return_value = mock_socket

        dealer = MQDealer("ipc://@test_router", identity="worker_001")
        await dealer.connect()

        mock_socket.setsockopt.assert_called_once()
        args = mock_socket.setsockopt.call_args[0]
        assert args[1] == b"worker_001"


@pytest.mark.asyncio
async def test_dealer_reconnect_warning():
    dealer = MQDealer("ipc://@test_router")
    dealer._connected = True
    dealer._socket = MagicMock()

    await dealer.connect()

    assert dealer._connected
