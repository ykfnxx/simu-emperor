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
