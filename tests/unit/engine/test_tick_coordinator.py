"""Tests for TickCoordinator class (V4)."""

import pytest
import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from simu_emperor.engine.models.base_data import ProvinceData, NationData
from simu_emperor.engine.engine import Engine
from simu_emperor.engine.tick_coordinator import TickCoordinator


@pytest.fixture
def sample_nation():
    """Create a sample NationData for testing."""
    provinces = {
        "zhili": ProvinceData(
            province_id="zhili",
            name="直隶",
            production_value=Decimal("100000"),
            population=Decimal("50000"),
            fixed_expenditure=Decimal("5000"),
            stockpile=Decimal("20000"),
        )
    }
    return NationData(
        turn=0,
        base_tax_rate=Decimal("0.10"),
        tribute_rate=Decimal("0.8"),
        imperial_treasury=Decimal("100000"),
        provinces=provinces,
    )


@pytest.fixture
def engine(sample_nation):
    """Create an Engine instance for testing."""
    return Engine(initial_state=sample_nation)


@pytest.fixture
def mock_event_bus():
    """Create a mock EventBus for testing."""
    event_bus = MagicMock()
    event_bus.send_event = AsyncMock()
    return event_bus


class TestTickCoordinatorInit:
    """Test TickCoordinator initialization."""

    def test_init(self, mock_event_bus, engine):
        """Test TickCoordinator initialization."""
        coordinator = TickCoordinator(
            event_bus=mock_event_bus,
            engine=engine,
            tick_interval_seconds=5,
        )
        assert coordinator.event_bus is mock_event_bus
        assert coordinator.engine is engine
        assert coordinator.session_id.startswith("tick:")
        assert coordinator.tick_interval == 5
        assert coordinator._running is False
        assert coordinator._task is None

    def test_init_default_interval(self, mock_event_bus, engine):
        """Test TickCoordinator default interval is 5 seconds."""
        coordinator = TickCoordinator(
            event_bus=mock_event_bus,
            engine=engine,
        )
        assert coordinator.tick_interval == 5

    def test_session_id_is_unique(self, mock_event_bus, engine):
        """Test each TickCoordinator gets a unique session_id."""
        coord1 = TickCoordinator(event_bus=mock_event_bus, engine=engine)
        coord2 = TickCoordinator(event_bus=mock_event_bus, engine=engine)
        assert coord1.session_id != coord2.session_id
        assert coord1.get_session_id() == coord1.session_id


class TestTickCoordinatorStartStop:
    """Test TickCoordinator start and stop."""

    @pytest.mark.asyncio
    async def test_start_sets_running_true(self, mock_event_bus, engine):
        """Test start sets _running to True."""
        coordinator = TickCoordinator(
            event_bus=mock_event_bus,
            engine=engine,
            tick_interval_seconds=1,
        )
        await coordinator.start()
        assert coordinator._running is True
        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(self, mock_event_bus, engine):
        """Test calling start multiple times doesn't create multiple tasks."""
        coordinator = TickCoordinator(
            event_bus=mock_event_bus,
            engine=engine,
            tick_interval_seconds=1,
        )
        await coordinator.start()
        first_task = coordinator._task
        await coordinator.start()
        second_task = coordinator._task
        assert first_task is second_task
        await coordinator.stop()

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self, mock_event_bus, engine):
        """Test stop sets _running to False."""
        coordinator = TickCoordinator(
            event_bus=mock_event_bus,
            engine=engine,
            tick_interval_seconds=1,
        )
        await coordinator.start()
        await coordinator.stop()
        assert coordinator._running is False

    @pytest.mark.asyncio
    async def test_stop_without_start(self, mock_event_bus, engine):
        """Test stop without start doesn't raise."""
        coordinator = TickCoordinator(
            event_bus=mock_event_bus,
            engine=engine,
        )
        await coordinator.stop()
        assert coordinator._running is False


class TestTickLoop:
    """Test tick loop execution."""

    @pytest.mark.asyncio
    async def test_tick_loop_publishes_event(self, mock_event_bus, engine):
        """Test tick loop publishes tick_completed event."""
        coordinator = TickCoordinator(
            event_bus=mock_event_bus,
            engine=engine,
            tick_interval_seconds=0.1,
        )
        await coordinator.start()

        # Wait for at least one tick
        await asyncio.sleep(0.15)

        await coordinator.stop()

        # Verify send_event was called
        assert mock_event_bus.send_event.called
        call_args = mock_event_bus.send_event.call_args
        event = call_args[0][0]  # Event object is first positional arg
        assert event.type == "tick_completed"
        assert event.src == "system:tick_coordinator"
        assert event.dst == ["*"]
        assert "tick" in event.payload
        assert "timestamp" in event.payload
        assert event.session_id == coordinator.session_id

    @pytest.mark.asyncio
    async def test_tick_loop_increments_turn(self, mock_event_bus, engine):
        """Test tick loop increments engine turn counter."""
        coordinator = TickCoordinator(
            event_bus=mock_event_bus,
            engine=engine,
            tick_interval_seconds=0.1,
        )
        initial_turn = engine.state.turn
        await coordinator.start()

        # Wait for at least one tick
        await asyncio.sleep(0.15)

        await coordinator.stop()

        assert engine.state.turn > initial_turn

    @pytest.mark.asyncio
    async def test_tick_loop_handles_errors(self, mock_event_bus, engine):
        """Test tick loop handles errors and continues."""
        # Make apply_tick raise an error once
        original_apply_tick = engine.apply_tick
        call_count = [0]

        def failing_apply_tick():
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Test error")
            return original_apply_tick()

        engine.apply_tick = failing_apply_tick

        coordinator = TickCoordinator(
            event_bus=mock_event_bus,
            engine=engine,
            tick_interval_seconds=0.1,
        )
        await coordinator.start()

        # Wait for at least two ticks
        await asyncio.sleep(0.25)

        await coordinator.stop()

        # Should have recovered and continued
        assert call_count[0] >= 2


class TestTickTiming:
    """Test tick timing behavior."""

    @pytest.mark.asyncio
    async def test_tick_respects_interval(self, mock_event_bus, engine):
        """Test tick loop respects the configured interval."""
        import time

        coordinator = TickCoordinator(
            event_bus=mock_event_bus,
            engine=engine,
            tick_interval_seconds=0.2,
        )

        publish_times = []

        async def track_publish(event):
            publish_times.append(time.monotonic())

        mock_event_bus.send_event = AsyncMock(side_effect=track_publish)

        await coordinator.start()

        # Wait for at least 3 ticks
        await asyncio.sleep(0.7)

        await coordinator.stop()

        # Should have at least 3 ticks
        assert len(publish_times) >= 3

        # Check intervals are approximately correct
        for i in range(1, len(publish_times)):
            interval = publish_times[i] - publish_times[i - 1]
            # Allow some tolerance
            assert 0.15 < interval < 0.3
