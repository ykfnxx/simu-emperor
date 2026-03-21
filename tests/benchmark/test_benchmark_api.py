"""
TDD tests for Benchmark API.

These tests define the expected API contract for the Benchmark API endpoints.

Expected API:
- POST /api/benchmark/agent/chat - Agent chat benchmark
- GET /api/benchmark/health - Health check for benchmark mode
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport
import pytest_asyncio


async def _trigger_response(event, handlers):
    """Trigger response event for benchmark tests."""
    await asyncio.sleep(0.01)

    for handler in handlers:
        response_event = MagicMock()
        response_event.session_id = event.session_id
        response_event.type = "agent_message"
        response_event.payload = {"content": "测试响应"}
        await handler(response_event)


@pytest_asyncio.fixture
async def async_client():
    """Create async test client with mocked game instance."""
    from simu_emperor.adapters.web.server import app

    mock_instance = MagicMock()
    mock_instance.is_running = True

    mock_agent_manager = MagicMock()
    mock_agent = MagicMock()
    mock_agent.agent_id = "governor_zhili"

    def get_agent_side_effect(agent_id):
        if agent_id == "nonexistent_agent_xyz":
            return None
        return mock_agent

    mock_agent_manager.get_agent.side_effect = get_agent_side_effect
    mock_instance.agent_manager = mock_agent_manager

    handlers = []

    def mock_subscribe(dst, handler):
        handlers.append(handler)

    def mock_unsubscribe(dst, handler):
        if handler in handlers:
            handlers.remove(handler)

    async def mock_send_event(event):
        asyncio.get_event_loop().call_soon(
            lambda: asyncio.create_task(_trigger_response(event, handlers))
        )

    mock_event_bus = MagicMock()
    mock_event_bus.subscribe = mock_subscribe
    mock_event_bus.unsubscribe = mock_unsubscribe
    mock_event_bus.send_event = AsyncMock(side_effect=mock_send_event)
    mock_instance.event_bus = mock_event_bus

    with patch(
        "simu_emperor.adapters.web.benchmark_api._get_game_instance", return_value=mock_instance
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client


# ============================================================================
# POST /api/benchmark/agent/chat - Success Case
# ============================================================================


@pytest.mark.asyncio
async def test_benchmark_agent_chat_success(async_client):
    """Test successful agent chat returns response, tool_calls, latency_ms, success."""
    request_body = {"agent_id": "governor_zhili", "message": "查询直隶省的产值"}

    response = await async_client.post("/api/benchmark/agent/chat", json=request_body)

    assert response.status_code == 200
    data = response.json()

    assert "response" in data
    assert "tool_calls" in data
    assert "latency_ms" in data
    assert "success" in data

    assert isinstance(data["response"], str)
    assert isinstance(data["tool_calls"], list)
    assert isinstance(data["latency_ms"], (int, float))
    assert isinstance(data["success"], bool)
    assert data["success"] is True

    for tool_call in data["tool_calls"]:
        assert "name" in tool_call
        assert "args" in tool_call
        assert "result" in tool_call
        assert isinstance(tool_call["name"], str)
        assert isinstance(tool_call["args"], dict)
        assert isinstance(tool_call["result"], str)


# ============================================================================
# POST /api/benchmark/agent/chat - Error Cases
# ============================================================================


@pytest.mark.asyncio
async def test_benchmark_agent_chat_missing_agent_id(async_client):
    """Test error handling when agent_id is missing in request body."""
    request_body = {"message": "查询直隶省的产值"}

    response = await async_client.post("/api/benchmark/agent/chat", json=request_body)

    assert response.status_code in [400, 422]

    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_benchmark_agent_chat_missing_message(async_client):
    """Test error handling when message is missing in request body."""
    request_body = {"agent_id": "governor_zhili"}

    response = await async_client.post("/api/benchmark/agent/chat", json=request_body)

    assert response.status_code in [400, 422]

    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_benchmark_agent_chat_empty_request_body(async_client):
    """Test error handling when request body is empty."""
    response = await async_client.post("/api/benchmark/agent/chat", json={})

    assert response.status_code == 422

    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_benchmark_agent_chat_invalid_agent(async_client):
    """Test error handling when agent_id doesn't exist."""
    request_body = {"agent_id": "nonexistent_agent_xyz", "message": "查询数据"}

    response = await async_client.post("/api/benchmark/agent/chat", json=request_body)

    assert response.status_code in [200, 404]

    data = response.json()

    if response.status_code == 200:
        assert data.get("success") is False
        assert "error" in data or "response" in data
    else:
        assert "detail" in data


@pytest.mark.asyncio
async def test_benchmark_agent_chat_empty_agent_id(async_client):
    """Test error handling when agent_id is empty string."""
    request_body = {"agent_id": "", "message": "查询数据"}

    response = await async_client.post("/api/benchmark/agent/chat", json=request_body)

    assert response.status_code in [400, 422]


@pytest.mark.asyncio
async def test_benchmark_agent_chat_empty_message(async_client):
    """Test error handling when message is empty string."""
    request_body = {"agent_id": "governor_zhili", "message": ""}

    response = await async_client.post("/api/benchmark/agent/chat", json=request_body)

    assert response.status_code in [400, 422]


# ============================================================================
# GET /api/benchmark/health - Health Check
# ============================================================================


@pytest.mark.asyncio
async def test_benchmark_health(async_client):
    """Test health check endpoint returns ok status and config."""
    response = await async_client.get("/api/benchmark/health")

    assert response.status_code == 200

    data = response.json()

    assert "status" in data
    assert data["status"] == "ok"

    assert "config" in data
    config = data["config"]
    assert isinstance(config, dict)

    assert "test_mode" in config
    assert isinstance(config["test_mode"], bool)

    assert "database" in config
    assert isinstance(config["database"], str)


@pytest.mark.asyncio
async def test_benchmark_health_config_values(async_client):
    """Test health check returns expected config values for benchmark mode."""
    response = await async_client.get("/api/benchmark/health")

    assert response.status_code == 200

    data = response.json()
    config = data.get("config", {})

    assert config.get("test_mode") is True

    database = config.get("database", "")
    assert "test" in database.lower() or database.endswith(".db")


# ============================================================================
# POST /api/benchmark/agent/chat - Response Format Validation
# ============================================================================


@pytest.mark.asyncio
async def test_benchmark_agent_chat_response_has_latency(async_client):
    """Test that successful response includes latency_ms measurement."""
    request_body = {"agent_id": "governor_zhili", "message": "查询直隶省的产值"}

    response = await async_client.post("/api/benchmark/agent/chat", json=request_body)

    assert response.status_code == 200

    data = response.json()

    assert "latency_ms" in data
    latency = data["latency_ms"]
    assert isinstance(latency, (int, float))
    assert latency >= 0


@pytest.mark.asyncio
async def test_benchmark_agent_chat_response_has_tool_calls(async_client):
    """Test that response includes tool_calls array (can be empty)."""
    request_body = {"agent_id": "governor_zhili", "message": "查询直隶省的产值"}

    response = await async_client.post("/api/benchmark/agent/chat", json=request_body)

    assert response.status_code == 200

    data = response.json()

    assert "tool_calls" in data
    assert isinstance(data["tool_calls"], list)


# ============================================================================
# POST /api/benchmark/agent/chat - Tool Call Format
# ============================================================================


@pytest.mark.asyncio
async def test_benchmark_agent_chat_tool_call_format(async_client):
    """Test that tool_calls have the expected format when present."""
    request_body = {"agent_id": "governor_zhili", "message": "查询直隶省的生产值"}

    response = await async_client.post("/api/benchmark/agent/chat", json=request_body)

    assert response.status_code == 200

    data = response.json()
    tool_calls = data.get("tool_calls", [])

    for tool_call in tool_calls:
        assert "name" in tool_call
        assert "args" in tool_call
        assert "result" in tool_call

        assert isinstance(tool_call["name"], str)
        assert isinstance(tool_call["args"], dict)
        assert isinstance(tool_call["result"], str)

        assert len(tool_call["name"]) > 0


# ============================================================================
# Endpoints Exist Check
# ============================================================================


@pytest.mark.asyncio
async def test_benchmark_endpoints_exist(async_client):
    """Verify benchmark endpoints exist and return valid responses."""
    post_response = await async_client.post(
        "/api/benchmark/agent/chat", json={"agent_id": "governor_zhili", "message": "test"}
    )
    assert post_response.status_code in [200, 400, 422, 503], (
        f"Expected valid response for POST /api/benchmark/agent/chat, got {post_response.status_code}"
    )

    get_response = await async_client.get("/api/benchmark/health")
    assert get_response.status_code == 200, (
        f"Expected 200 for GET /api/benchmark/health, got {get_response.status_code}"
    )
