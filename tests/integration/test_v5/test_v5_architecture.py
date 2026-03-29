import asyncio
import json
import pytest
import socket

from simu_emperor.mq.event import Event
from simu_emperor.mq.dealer import MQDealer
from simu_emperor.mq.publisher import MQPublisher
from simu_emperor.mq.subscriber import MQSubscriber
from simu_emperor.router.routing_table import RoutingTable


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_event_serialization_roundtrip():
    event = Event(
        event_id="evt_test_001",
        event_type="CHAT",
        src="player:web:client_001",
        dst=["agent:governor_zhili"],
        session_id="session:test:001",
        payload={"message": "Hello, governor!"},
        timestamp="2026-03-29T10:00:00",
    )

    json_str = event.to_json()

    restored = Event.from_json(json_str)

    assert restored.event_id == event.event_id
    assert restored.event_type == event.event_type
    assert restored.src == event.src
    assert restored.dst == event.dst
    assert restored.payload == event.payload


@pytest.mark.asyncio
async def test_routing_table():
    table = RoutingTable()

    table.register("agent:governor_zhili", b"identity_001")
    table.register("agent:minister_revenue", b"identity_002")

    assert table.has("agent:governor_zhili")
    assert table.has("agent:minister_revenue")
    assert not table.has("agent:unknown")

    identity = table.get("agent:governor_zhili")
    assert identity == b"identity_001"

    all_agents = table.list_all()
    assert len(all_agents) == 2
    assert "agent:governor_zhili" in all_agents

    table.unregister("agent:governor_zhili")
    assert not table.has("agent:governor_zhili")
    assert len(table.list_all()) == 1
