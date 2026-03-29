import asyncio
import json
import socket
import uuid

import pytest
import pytest_asyncio

from simu_emperor.orchestrator import Orchestrator, OrchestratorConfig, ServiceStatus
from simu_emperor.mq.event import Event
from simu_emperor.mq.dealer import MQDealer
from simu_emperor.mq.subscriber import MQSubscriber


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def get_unique_ipc_addr():
    return f"ipc://@simu_test_{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def orchestrator():
    router_addr = get_unique_ipc_addr()
    broadcast_addr = get_unique_ipc_addr()
    gateway_port = get_free_port()

    config = OrchestratorConfig(
        router_addr=router_addr,
        broadcast_addr=broadcast_addr,
        gateway_port=gateway_port,
        tick_interval=1.0,
        agent_ids=["test_agent_1", "test_agent_2"],
    )

    orch = Orchestrator(config)
    yield orch

    await orch.stop_all()


@pytest_asyncio.fixture
async def running_orchestrator(orchestrator):
    await orchestrator.start_all()
    await asyncio.sleep(0.5)
    yield orchestrator


class TestOrchestratorLifecycle:
    @pytest.mark.asyncio
    async def test_orchestrator_starts_all_services(self, orchestrator):
        await orchestrator.start_all()
        await asyncio.sleep(0.5)

        status = orchestrator.get_status()

        assert status["router"]["status"] == ServiceStatus.RUNNING.value
        assert status["broadcast"]["status"] == ServiceStatus.RUNNING.value
        assert status["engine"]["status"] == ServiceStatus.RUNNING.value
        assert status["gateway"]["status"] == ServiceStatus.RUNNING.value
        assert status["worker:test_agent_1"]["status"] == ServiceStatus.RUNNING.value
        assert status["worker:test_agent_2"]["status"] == ServiceStatus.RUNNING.value

    @pytest.mark.asyncio
    async def test_orchestrator_stops_all_services(self, orchestrator):
        await orchestrator.start_all()
        await asyncio.sleep(0.5)

        await orchestrator.stop_all()

        status = orchestrator.get_status()
        for service_status in status.values():
            assert service_status["status"] in [
                ServiceStatus.STOPPED.value,
                ServiceStatus.STOPPING.value,
            ]

    @pytest.mark.asyncio
    async def test_orchestrator_status_no_errors(self, running_orchestrator):
        status = running_orchestrator.get_status()

        for name, service_status in status.items():
            assert service_status["error"] is None, (
                f"Service {name} has error: {service_status['error']}"
            )


class TestEventFlow:
    @pytest.mark.asyncio
    async def test_router_accepts_connections(self, running_orchestrator):
        config = running_orchestrator.config

        dealer = MQDealer(config.router_addr, identity="test_client:*")
        await dealer.connect()

        await dealer.send(json.dumps({"type": "REGISTER", "agent_id": "test_client:*"}))

        try:
            response = await asyncio.wait_for(dealer.receive(), timeout=2.0)
            msg = json.loads(response)
            assert msg["type"] == "REGISTER_ACK"
        finally:
            await dealer.close()

    @pytest.mark.asyncio
    async def test_event_routing_to_engine(self, running_orchestrator):
        config = running_orchestrator.config

        dealer = MQDealer(config.router_addr, identity="test_sender:*")
        await dealer.connect()
        await dealer.send(json.dumps({"type": "REGISTER", "agent_id": "test_sender:*"}))
        await asyncio.wait_for(dealer.receive(), timeout=2.0)

        event = Event(
            event_id=f"evt_{uuid.uuid4().hex[:8]}",
            event_type="CREATE_INCIDENT",
            src="test_sender:*",
            dst=["engine:*"],
            session_id="test_session",
            payload={"incident_type": "flood", "province": "zhili"},
            timestamp="2026-03-29T10:00:00",
        )

        await dealer.send(event.to_json())

        await asyncio.sleep(0.5)

        await dealer.close()

    @pytest.mark.asyncio
    async def test_broadcast_subscription(self, running_orchestrator):
        config = running_orchestrator.config

        subscriber = MQSubscriber(config.broadcast_addr)
        await subscriber.connect()
        subscriber.subscribe("")

        await asyncio.sleep(0.2)

        received_events = []

        async def collect_events():
            try:
                for _ in range(3):
                    topic, data = await asyncio.wait_for(subscriber.receive(), timeout=3.0)
                    event = Event.from_json(data)
                    received_events.append((topic, event))
            except asyncio.TimeoutError:
                pass

        collect_task = asyncio.create_task(collect_events())

        await asyncio.sleep(2.5)

        collect_task.cancel()
        try:
            await collect_task
        except asyncio.CancelledError:
            pass

        await subscriber.close()

        assert len(received_events) >= 1, "Should have received at least one tick event"


class TestGatewayHealth:
    @pytest.mark.asyncio
    async def test_gateway_health_endpoint(self, running_orchestrator):
        import httpx

        gateway_port = running_orchestrator.config.gateway_port

        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:{gateway_port}/health", timeout=5.0)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["connected"] is True

    @pytest.mark.asyncio
    async def test_gateway_agents_endpoint(self, running_orchestrator):
        import httpx

        gateway_port = running_orchestrator.config.gateway_port

        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:{gateway_port}/agents", timeout=5.0)

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data


class TestWorkerRegistration:
    @pytest.mark.asyncio
    async def test_workers_register_with_router(self, running_orchestrator):
        await asyncio.sleep(1.0)

        router_handle = running_orchestrator.services.get("router")
        assert router_handle is not None
        assert router_handle.instance is not None

        routing_table = router_handle.instance.routing_table

        for agent_id in running_orchestrator.config.agent_ids:
            full_id = f"worker:{agent_id}"
            assert routing_table.has(full_id), f"Worker {full_id} not registered"
