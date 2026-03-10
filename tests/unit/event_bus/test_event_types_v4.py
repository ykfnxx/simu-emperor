"""Tests for EventTypes V4 extension."""

import pytest

from simu_emperor.event_bus.event_types import EventType


class TestEventTypeV4:
    """Test cases for V4 event types."""

    def test_task_created_exists(self):
        assert hasattr(EventType, "TASK_CREATED")
        assert EventType.TASK_CREATED == "task_created"

    def test_task_finished_exists(self):
        assert hasattr(EventType, "TASK_FINISHED")
        assert EventType.TASK_FINISHED == "task_finished"

    def test_task_failed_exists(self):
        assert hasattr(EventType, "TASK_FAILED")
        assert EventType.TASK_FAILED == "task_failed"

    def test_task_timeout_exists(self):
        assert hasattr(EventType, "TASK_TIMEOUT")
        assert EventType.TASK_TIMEOUT == "task_timeout"

    def test_all_includes_task_events(self):
        all_events = EventType.all()
        assert EventType.TASK_CREATED in all_events
        assert EventType.TASK_FINISHED in all_events
        assert EventType.TASK_FAILED in all_events
        assert EventType.TASK_TIMEOUT in all_events

    def test_is_valid_for_task_events(self):
        assert EventType.is_valid("task_created") is True
        assert EventType.is_valid("task_finished") is True
        assert EventType.is_valid("task_failed") is True
        assert EventType.is_valid("task_timeout") is True
        assert EventType.is_valid("invalid_event") is False

    def test_agent_events_includes_task_lifecycle(self):
        agent_events = EventType.agent_events()
        assert EventType.TASK_CREATED in agent_events
        assert EventType.TASK_FINISHED in agent_events
        assert EventType.TASK_FAILED in agent_events
        assert EventType.TASK_TIMEOUT not in agent_events

    def test_system_events_includes_timeout(self):
        system_events = EventType.system_events()
        assert EventType.TASK_TIMEOUT in system_events
        assert EventType.TICK_COMPLETED in system_events
        assert EventType.SESSION_STATE in system_events
