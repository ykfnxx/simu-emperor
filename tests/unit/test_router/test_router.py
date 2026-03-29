"""Router tests - V5 Router Process."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from simu_emperor.mq.event import Event
from simu_emperor.router.router import Router


class TestRouterInit:
    def test_init_default_address(self):
        router = Router()

        assert router.router_addr == "ipc://@simu_router"
        assert router._ctx is None
        assert router._socket is None
        assert router._running is False

    def test_init_custom_address(self):
        router = Router(router_addr="tcp://localhost:5555")

        assert router.router_addr == "tcp://localhost:5555"

    def test_init_has_routing_table(self):
        router = Router()

        assert router.routing_table is not None
        assert hasattr(router.routing_table, "register")
        assert hasattr(router.routing_table, "get")


class TestRouterStart:
    @pytest.mark.asyncio
    async def test_start_creates_context_and_socket(self):
        router = Router()

        with patch("simu_emperor.router.router.zmq.asyncio.Context") as mock_ctx_class:
            mock_ctx = MagicMock()
            mock_socket = AsyncMock()
            mock_ctx.socket.return_value = mock_socket
            mock_ctx_class.return_value = mock_ctx

            call_count = 0

            async def mock_recv():
                nonlocal call_count
                call_count += 1
                if call_count >= 2:
                    router._running = False
                await asyncio.sleep(0.01)
                raise asyncio.TimeoutError()

            mock_socket.recv_multipart = mock_recv

            await router.start()

            mock_ctx_class.assert_called_once()
            mock_ctx.socket.assert_called_once()
            mock_socket.bind.assert_called_once_with("ipc://@simu_router")

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self):
        router = Router()

        with patch("simu_emperor.router.router.zmq.asyncio.Context") as mock_ctx_class:
            mock_ctx = MagicMock()
            mock_socket = AsyncMock()
            mock_ctx.socket.return_value = mock_socket
            mock_ctx_class.return_value = mock_ctx

            call_count = 0

            async def mock_recv():
                nonlocal call_count
                call_count += 1
                if call_count >= 1:
                    router._running = False
                await asyncio.sleep(0.01)
                raise asyncio.TimeoutError()

            mock_socket.recv_multipart = mock_recv

            await router.start()

            assert router._running is False


class TestRouterStop:
    @pytest.mark.asyncio
    async def test_stop_clears_running_flag(self):
        router = Router()
        router._running = True
        router._socket = MagicMock()
        router._ctx = MagicMock()

        await router.stop()

        assert router._running is False

    @pytest.mark.asyncio
    async def test_stop_closes_socket(self):
        router = Router()
        router._running = True
        mock_socket = MagicMock()
        router._socket = mock_socket
        router._ctx = MagicMock()

        await router.stop()

        mock_socket.close.assert_called_once()
        assert router._socket is None

    @pytest.mark.asyncio
    async def test_stop_terminates_context(self):
        router = Router()
        router._running = True
        router._socket = MagicMock()
        mock_ctx = MagicMock()
        router._ctx = mock_ctx

        await router.stop()

        mock_ctx.term.assert_called_once()
        assert router._ctx is None

    @pytest.mark.asyncio
    async def test_stop_handles_none_socket_and_context(self):
        router = Router()
        router._running = True
        router._socket = None
        router._ctx = None

        await router.stop()

        assert router._running is False


class TestRouterHandleRegister:
    @pytest.mark.asyncio
    async def test_handle_register_adds_to_routing_table(self):
        router = Router()
        mock_socket = AsyncMock()
        router._socket = mock_socket

        identity = b"worker_001"
        msg = {"type": "REGISTER", "agent_id": "agent:governor"}

        await router._handle_register(identity, msg)

        assert router.routing_table.has("agent:governor")
        assert router.routing_table.get("agent:governor") == identity

    @pytest.mark.asyncio
    async def test_handle_register_sends_ack(self):
        router = Router()
        mock_socket = AsyncMock()
        router._socket = mock_socket

        identity = b"worker_001"
        msg = {"type": "REGISTER", "agent_id": "agent:governor"}

        await router._handle_register(identity, msg)

        mock_socket.send_multipart.assert_called_once()
        call_args = mock_socket.send_multipart.call_args[0][0]
        assert call_args[0] == identity
        ack_msg = json.loads(call_args[1].decode("utf-8"))
        assert ack_msg["type"] == "REGISTER_ACK"
        assert ack_msg["agent_id"] == "agent:governor"

    @pytest.mark.asyncio
    async def test_handle_register_missing_agent_id(self):
        router = Router()
        mock_socket = AsyncMock()
        router._socket = mock_socket

        identity = b"worker_001"
        msg = {"type": "REGISTER"}

        await router._handle_register(identity, msg)

        assert not router.routing_table.has("agent:governor")
        mock_socket.send_multipart.assert_not_called()


class TestRouterHandleUnregister:
    @pytest.mark.asyncio
    async def test_handle_unregister_removes_from_routing_table(self):
        router = Router()
        router.routing_table.register("agent:governor", b"identity")

        identity = b"worker_001"
        msg = {"type": "UNREGISTER", "agent_id": "agent:governor"}

        await router._handle_unregister(identity, msg)

        assert not router.routing_table.has("agent:governor")

    @pytest.mark.asyncio
    async def test_handle_unregister_missing_agent_id(self):
        router = Router()
        router.routing_table.register("agent:governor", b"identity")

        identity = b"worker_001"
        msg = {"type": "UNREGISTER"}

        await router._handle_unregister(identity, msg)

        assert router.routing_table.has("agent:governor")


class TestRouterRouteToDestination:
    @pytest.mark.asyncio
    async def test_route_to_agent(self):
        router = Router()
        mock_socket = AsyncMock()
        router._socket = mock_socket
        router.routing_table.register("governor", b"worker_001")

        event = Event(
            event_id="evt_test",
            event_type="CHAT",
            src="player:web:001",
            dst=["agent:governor"],
            session_id="session:001",
            payload={"message": "test"},
            timestamp="2026-03-29T10:00:00",
        )

        await router._route_to_destination("agent:governor", event)

        mock_socket.send_multipart.assert_called_once()
        call_args = mock_socket.send_multipart.call_args[0][0]
        assert call_args[0] == b"worker_001"

    @pytest.mark.asyncio
    async def test_route_to_non_existent_agent(self):
        router = Router()
        mock_socket = AsyncMock()
        router._socket = mock_socket

        event = Event(
            event_id="evt_test",
            event_type="CHAT",
            src="player:web:001",
            dst=["agent:nonexistent"],
            session_id="session:001",
            payload={"message": "test"},
            timestamp="2026-03-29T10:00:00",
        )

        await router._route_to_destination("agent:nonexistent", event)

        mock_socket.send_multipart.assert_not_called()

    @pytest.mark.asyncio
    async def test_route_to_engine(self):
        router = Router()
        mock_socket = AsyncMock()
        router._socket = mock_socket
        router.routing_table.register("engine:*", b"engine_worker")

        event = Event(
            event_id="evt_test",
            event_type="COMMAND",
            src="player:cli",
            dst=["engine:*"],
            session_id="session:001",
            payload={"command": "tick"},
            timestamp="2026-03-29T10:00:00",
        )

        await router._route_to_destination("engine:main", event)

        mock_socket.send_multipart.assert_called_once()
        call_args = mock_socket.send_multipart.call_args[0][0]
        assert call_args[0] == b"engine_worker"

    @pytest.mark.asyncio
    async def test_route_to_player_via_gateway(self):
        router = Router()
        mock_socket = AsyncMock()
        router._socket = mock_socket
        router.routing_table.register("gateway:*", b"gateway_worker")

        event = Event(
            event_id="evt_test",
            event_type="AGENT_MESSAGE",
            src="agent:governor",
            dst=["player:web:client_001"],
            session_id="session:001",
            payload={"message": "response"},
            timestamp="2026-03-29T10:00:00",
        )

        await router._route_to_destination("player:web:client_001", event)

        mock_socket.send_multipart.assert_called_once()
        call_args = mock_socket.send_multipart.call_args[0][0]
        assert call_args[0] == b"gateway_worker"

    @pytest.mark.asyncio
    async def test_route_broadcast(self):
        router = Router()
        mock_socket = AsyncMock()
        router._socket = mock_socket
        router.routing_table.register("agent:governor", b"worker_001")
        router.routing_table.register("agent:minister", b"worker_002")
        router.routing_table.register("engine:*", b"engine_worker")

        event = Event(
            event_id="evt_test",
            event_type="SYSTEM",
            src="engine:*",
            dst=["broadcast:*"],
            session_id="session:001",
            payload={"type": "tick"},
            timestamp="2026-03-29T10:00:00",
        )

        await router._route_to_destination("broadcast:*", event)

        assert mock_socket.send_multipart.call_count == 2


class TestRouterRouteEvent:
    @pytest.mark.asyncio
    async def test_route_event_routes_to_all_destinations(self):
        router = Router()
        mock_socket = AsyncMock()
        router._socket = mock_socket
        router.routing_table.register("governor", b"worker_001")
        router.routing_table.register("minister", b"worker_002")

        event_dict = {
            "event_id": "evt_test",
            "event_type": "CHAT",
            "src": "player:web:001",
            "dst": ["agent:governor", "agent:minister"],
            "session_id": "session:001",
            "payload": {"message": "test"},
            "timestamp": "2026-03-29T10:00:00",
        }

        await router._route_event(b"sender", event_dict)

        assert mock_socket.send_multipart.call_count == 2

    @pytest.mark.asyncio
    async def test_route_event_invalid_format(self):
        router = Router()
        mock_socket = AsyncMock()
        router._socket = mock_socket

        invalid_event_dict = {"invalid": "data"}

        await router._route_event(b"sender", invalid_event_dict)

        mock_socket.send_multipart.assert_not_called()


class TestRouterEventLoop:
    @pytest.mark.asyncio
    async def test_event_loop_handles_register_message(self):
        router = Router()
        mock_socket = AsyncMock()
        router._socket = mock_socket
        router._running = True

        register_msg = json.dumps({"type": "REGISTER", "agent_id": "agent:test"}).encode("utf-8")

        call_count = 0

        async def mock_recv():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [b"identity_001", register_msg]
            router._running = False
            raise asyncio.TimeoutError()

        mock_socket.recv_multipart = mock_recv

        await router._event_loop()

        assert router.routing_table.has("agent:test")

    @pytest.mark.asyncio
    async def test_event_loop_handles_unregister_message(self):
        router = Router()
        mock_socket = AsyncMock()
        router._socket = mock_socket
        router.routing_table.register("agent:test", b"identity_001")
        router._running = True

        unregister_msg = json.dumps({"type": "UNREGISTER", "agent_id": "agent:test"}).encode(
            "utf-8"
        )

        call_count = 0

        async def mock_recv():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [b"identity_001", unregister_msg]
            router._running = False
            raise asyncio.TimeoutError()

        mock_socket.recv_multipart = mock_recv

        await router._event_loop()

        assert not router.routing_table.has("agent:test")

    @pytest.mark.asyncio
    async def test_event_loop_handles_invalid_message_format(self):
        router = Router()
        mock_socket = AsyncMock()
        router._socket = mock_socket
        router._running = True

        call_count = 0

        async def mock_recv():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [b"only_one_part"]
            router._running = False
            raise asyncio.TimeoutError()

        mock_socket.recv_multipart = mock_recv

        await router._event_loop()

    @pytest.mark.asyncio
    async def test_event_loop_handles_json_decode_error(self):
        router = Router()
        mock_socket = AsyncMock()
        router._socket = mock_socket
        router._running = True

        call_count = 0

        async def mock_recv():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [b"identity", b"invalid json"]
            router._running = False
            raise asyncio.TimeoutError()

        mock_socket.recv_multipart = mock_recv

        await router._event_loop()


class TestRouterContextManager:
    @pytest.mark.asyncio
    async def test_context_manager_aenter_returns_self(self):
        router = Router()

        result = await router.__aenter__()

        assert result is router

    @pytest.mark.asyncio
    async def test_context_manager_aexit_calls_stop(self):
        router = Router()
        router._running = True
        router._socket = MagicMock()
        router._ctx = MagicMock()

        await router.__aexit__(None, None, None)

        assert router._running is False


class TestRouterRoutingTableIntegration:
    @pytest.mark.asyncio
    async def test_register_then_route(self):
        router = Router()
        mock_socket = AsyncMock()
        router._socket = mock_socket

        identity = b"worker_001"
        msg = {"type": "REGISTER", "agent_id": "governor"}
        await router._handle_register(identity, msg)

        event = Event(
            event_id="evt_test",
            event_type="CHAT",
            src="player:web:001",
            dst=["agent:governor"],
            session_id="session:001",
            payload={"message": "test"},
            timestamp="2026-03-29T10:00:00",
        )

        await router._route_to_destination("agent:governor", event)

        mock_socket.send_multipart.assert_called()
        assert mock_socket.send_multipart.call_count == 2

    @pytest.mark.asyncio
    async def test_unregister_prevents_routing(self):
        router = Router()
        mock_socket = AsyncMock()
        router._socket = mock_socket

        router.routing_table.register("governor", b"worker_001")
        router.routing_table.unregister("governor")

        event = Event(
            event_id="evt_test",
            event_type="CHAT",
            src="player:web:001",
            dst=["agent:governor"],
            session_id="session:001",
            payload={"message": "test"},
            timestamp="2026-03-29T10:00:00",
        )

        await router._route_to_destination("agent:governor", event)

        mock_socket.send_multipart.assert_not_called()
