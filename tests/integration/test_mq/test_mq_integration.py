"""
MQ集成测试 - 测试Publisher和Subscriber交互
"""

import asyncio
import pytest

from simu_emperor.mq.event import Event
from simu_emperor.mq.publisher import MQPublisher
from simu_emperor.mq.subscriber import MQSubscriber


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_pub_sub_integration():
    addr = "ipc://@test_integration_pubsub"

    publisher = MQPublisher(addr)
    await publisher.bind()

    subscriber = MQSubscriber(addr)
    await subscriber.connect()
    subscriber.subscribe("")

    await asyncio.sleep(0.5)

    event = Event(
        event_id="",
        event_type="TEST_EVENT",
        src="test:source",
        dst=["test:dest"],
        session_id="test:session",
        payload={"message": "hello"},
        timestamp="",
    )

    await publisher.publish_event(event)

    topic, received = await asyncio.wait_for(subscriber.receive_event(), timeout=1.0)

    assert topic == "TEST_EVENT"
    assert received.event_type == "TEST_EVENT"
    assert received.payload["message"] == "hello"

    await publisher.close()
    await subscriber.close()


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_multiple_subscribers():
    addr = "ipc://@test_integration_multi"

    publisher = MQPublisher(addr)
    await publisher.bind()

    subscribers = []
    for _ in range(3):
        sub = MQSubscriber(addr)
        await sub.connect()
        sub.subscribe("")
        subscribers.append(sub)

    await asyncio.sleep(0.1)

    event = Event(
        event_id="",
        event_type="BROADCAST",
        src="test:source",
        dst=["broadcast:*"],
        session_id="test:session",
        payload={"data": "broadcast message"},
        timestamp="",
    )

    await publisher.publish_event(event)

    for sub in subscribers:
        topic, received = await asyncio.wait_for(sub.receive_event(), timeout=1.0)
        assert received.event_type == "BROADCAST"

    await publisher.close()
    for sub in subscribers:
        await sub.close()


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_topic_filtering():
    addr = "ipc://@test_integration_topic"

    publisher = MQPublisher(addr)
    await publisher.bind()

    sub_tick = MQSubscriber(addr)
    await sub_tick.connect()
    sub_tick.subscribe("TICK_")

    sub_chat = MQSubscriber(addr)
    await sub_chat.connect()
    sub_chat.subscribe("CHAT")

    await asyncio.sleep(0.1)

    tick_event = Event(
        event_id="",
        event_type="TICK_COMPLETED",
        src="engine:*",
        dst=["broadcast:*"],
        session_id="system",
        payload={"tick": 1},
        timestamp="",
    )

    chat_event = Event(
        event_id="",
        event_type="CHAT",
        src="player:web",
        dst=["agent:governor"],
        session_id="session:001",
        payload={"message": "hello"},
        timestamp="",
    )

    await publisher.publish_event(tick_event)
    await publisher.publish_event(chat_event)

    topic1, received1 = await asyncio.wait_for(sub_tick.receive_event(), timeout=1.0)
    assert topic1 == "TICK_COMPLETED"

    topic2, received2 = await asyncio.wait_for(sub_chat.receive_event(), timeout=1.0)
    assert topic2 == "CHAT"

    await publisher.close()
    await sub_tick.close()
    await sub_chat.close()
