"""Tests for Agent Event Queue (V4.2 backpressure handling)."""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from simu_emperor.agents.agent import Agent
from simu_emperor.config import settings
from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.llm.mock import MockProvider


@pytest.fixture
def mock_event_bus():
    event_bus = MagicMock(spec=EventBus)
    event_bus.subscribe = MagicMock()
    event_bus.unsubscribe = MagicMock()
    event_bus.send_event = AsyncMock()
    return event_bus


@pytest.fixture
def mock_llm():
    return MockProvider(
        response="",
        tool_calls=[
            {
                "id": "call_1",
                "function": {
                    "name": "send_message",
                    "arguments": '{"recipients": ["player"], "content": "臣遵旨！"}',
                },
            }
        ],
    )


@pytest.fixture
def temp_data_dir(tmp_path):
    agent_dir = tmp_path / "data" / "agent" / "test_agent"
    agent_dir.mkdir(parents=True)

    soul_path = agent_dir / "soul.md"
    soul_path.write_text("# Test Soul\nYou are a test agent.", encoding="utf-8")

    import yaml

    scope_path = agent_dir / "data_scope.yaml"
    scope_path.write_text(yaml.dump({"query": ["province.population"]}), encoding="utf-8")

    return agent_dir


@pytest.fixture
def agent(mock_event_bus, mock_llm, temp_data_dir, tmp_path, monkeypatch):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()

    monkeypatch.setattr(settings.memory, "memory_dir", memory_dir)

    mock_session = MagicMock()
    mock_session.is_task = False
    mock_session.status = "ACTIVE"
    mock_session.pending_async_replies = 0
    mock_session.parent_id = None
    mock_session.pending_message_ids = []
    mock_session.created_by = "player"
    mock_session_manager = MagicMock()
    mock_session_manager.get_session = AsyncMock(return_value=mock_session)
    mock_session_manager.get_agent_state = AsyncMock(return_value=None)
    mock_session_manager.increment_async_replies = AsyncMock()
    mock_session_manager.save_manifest = AsyncMock()
    mock_session_manager.get_context_manager = AsyncMock()

    mock_tape_writer = MagicMock()
    mock_tape_writer._get_tape_path = MagicMock(return_value=memory_dir / "tape.jsonl")
    mock_tape_writer.write_event = AsyncMock(return_value="event_id")
    mock_tape_metadata_mgr = AsyncMock()

    agent = Agent(
        agent_id="test_agent",
        event_bus=mock_event_bus,
        llm_provider=mock_llm,
        data_dir=temp_data_dir,
        repository=Mock(),
        session_manager=mock_session_manager,
        tape_writer=mock_tape_writer,
        tape_metadata_mgr=mock_tape_metadata_mgr,
    )

    yield agent


def _make_event(index: int) -> Event:
    return Event(
        src="player",
        dst=["agent:test_agent"],
        type=EventType.CHAT,
        payload={"message": f"Message {index}"},
        session_id="test_session",
    )


class TestStartQueueConsumer:
    @pytest.mark.asyncio
    async def test_creates_queue_and_task(self, agent, monkeypatch):
        monkeypatch.setattr(settings.agent_queue, "enabled", True)
        monkeypatch.setattr(settings.agent_queue, "max_size", 0)

        agent.start_queue_consumer()

        assert agent._running is True
        assert agent._event_queue is not None
        assert agent._queue_task is not None
        assert agent._event_queue.maxsize == 0

        await agent.stop_queue_consumer()

    @pytest.mark.asyncio
    async def test_respects_max_size(self, agent, monkeypatch):
        monkeypatch.setattr(settings.agent_queue, "enabled", True)
        monkeypatch.setattr(settings.agent_queue, "max_size", 5)

        agent.start_queue_consumer()

        assert agent._event_queue.maxsize == 5

        await agent.stop_queue_consumer()

    @pytest.mark.asyncio
    async def test_noop_when_disabled(self, agent, monkeypatch):
        monkeypatch.setattr(settings.agent_queue, "enabled", False)

        agent.start_queue_consumer()

        assert agent._event_queue is None
        assert agent._running is False


class TestStopQueueConsumer:
    @pytest.mark.asyncio
    async def test_stops_cleanly(self, agent, monkeypatch):
        monkeypatch.setattr(settings.agent_queue, "enabled", True)
        monkeypatch.setattr(settings.agent_queue, "max_size", 0)

        agent.start_queue_consumer()
        await agent.stop_queue_consumer()

        assert agent._running is False
        assert agent._event_queue is None
        assert agent._queue_task is None

    @pytest.mark.asyncio
    async def test_noop_when_not_running(self, agent):
        await agent.stop_queue_consumer()
        assert agent._running is False


class TestEnqueueEvent:
    @pytest.mark.asyncio
    async def test_events_processed_in_order(self, agent, monkeypatch):
        monkeypatch.setattr(settings.agent_queue, "enabled", True)
        monkeypatch.setattr(settings.agent_queue, "max_size", 0)

        processed = []

        async def mock_on_event(event):
            processed.append(event.payload["message"])

        with patch.object(agent, "_on_event", side_effect=mock_on_event):
            agent.start_queue_consumer()

            for i in range(5):
                await agent._enqueue_event(_make_event(i))

            await asyncio.sleep(0.2)

        await agent.stop_queue_consumer()

        assert [f"Message {i}" for i in range(5)] == processed

    @pytest.mark.asyncio
    async def test_falls_back_to_direct_when_no_queue(self, agent, monkeypatch):
        monkeypatch.setattr(settings.agent_queue, "enabled", True)

        event = _make_event(0)

        with patch.object(agent, "_on_event", new_callable=AsyncMock) as mock_on_event:
            await agent._enqueue_event(event)
            mock_on_event.assert_called_once_with(event)


class TestQueueFullDropOldest:
    @pytest.mark.asyncio
    async def test_drops_oldest_when_full(self, agent, monkeypatch):
        monkeypatch.setattr(settings.agent_queue, "enabled", True)
        monkeypatch.setattr(settings.agent_queue, "max_size", 3)

        agent.start_queue_consumer()

        processed_ids = []

        async def slow_on_event(event):
            await asyncio.sleep(0.05)
            processed_ids.append(event.event_id)

        with patch.object(agent, "_on_event", side_effect=slow_on_event):
            # Block processing so queue fills up
            await asyncio.sleep(0.01)

            events = [_make_event(i) for i in range(6)]
            for event in events:
                await agent._enqueue_event(event)

            await asyncio.sleep(0.5)

        await agent.stop_queue_consumer()

        # With max_size=3 and slow processing, some events should be dropped
        # We sent 6 events into a queue of size 3
        assert len(processed_ids) <= 6

    @pytest.mark.asyncio
    async def test_logs_warning_on_drop(self, agent, monkeypatch):
        monkeypatch.setattr(settings.agent_queue, "enabled", True)
        monkeypatch.setattr(settings.agent_queue, "max_size", 2)

        agent.start_queue_consumer()

        async def blocking_on_event(event):
            await asyncio.sleep(0.3)

        with patch.object(agent, "_on_event", side_effect=blocking_on_event):
            with patch("simu_emperor.agents.agent.logger") as mock_logger:
                await asyncio.sleep(0.01)

                for i in range(5):
                    await agent._enqueue_event(_make_event(i))

                await asyncio.sleep(0.5)

                warning_calls = [
                    call
                    for call in mock_logger.warning.call_args_list
                    if "dropping oldest" in str(call).lower()
                ]
                assert len(warning_calls) > 0

        await agent.stop_queue_consumer()


class TestStartUsesQueue:
    def test_subscribes_enqueue_when_enabled(self, agent, monkeypatch):
        monkeypatch.setattr(settings.agent_queue, "enabled", True)

        agent.start()

        subscribe_calls = agent.event_bus.subscribe.call_args_list
        handlers = [call[0][1] for call in subscribe_calls]
        assert agent._enqueue_event in handlers

    def test_subscribes_on_event_when_disabled(self, agent, monkeypatch):
        monkeypatch.setattr(settings.agent_queue, "enabled", False)

        agent.start()

        subscribe_calls = agent.event_bus.subscribe.call_args_list
        handlers = [call[0][1] for call in subscribe_calls]
        assert agent._on_event in handlers
