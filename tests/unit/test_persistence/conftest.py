"""Shared fixtures for V5 persistence tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any

from simu_emperor.persistence.client import SeekDBClient
from simu_emperor.mq.event import Event


@pytest.fixture
def mock_client():
    """Create a mock SeekDBClient for testing."""
    client = MagicMock(spec=SeekDBClient)
    client.execute = AsyncMock(return_value=1)
    client.fetch_one = AsyncMock(return_value=None)
    client.fetch_all = AsyncMock(return_value=[])
    client.fetch_value = AsyncMock(return_value=None)
    return client


@pytest.fixture
def sample_event():
    """Create a sample Event for testing."""
    return Event(
        event_id="evt_test_001",
        event_type="COMMAND",
        src="agent:governor_zhili",
        dst=["player:web:client_001"],
        session_id="sess_test_001",
        payload={"action": "report", "target": "zhili"},
        timestamp="2025-01-15T10:30:00",
    )


@pytest.fixture
def sample_event_2():
    """Create another sample Event for testing."""
    return Event(
        event_id="evt_test_002",
        event_type="RESPONSE",
        src="agent:governor_shanxi",
        dst=["player:web:client_001"],
        session_id="sess_test_001",
        payload={"action": "report", "target": "shanxi"},
        timestamp="2025-01-15T10:31:00",
    )


@pytest.fixture
def sample_agent_config():
    """Sample agent configuration data."""
    return {
        "agent_id": "governor_zhili",
        "role_name": "直隶总督",
        "soul_text": "# 直隶总督\n\n你是一位忠诚的官员...",
        "skills": ["query_province", "report_status"],
        "permissions": {
            "provinces": ["zhili", "*"],
            "tools": ["query_province", "set_tax"],
        },
    }
