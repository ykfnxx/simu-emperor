"""
TDD RED tests for Benchmark API.

These tests define the expected API contract for the Benchmark API endpoints.
All tests should FAIL (RED) because the API doesn't exist yet.

Expected API:
- POST /api/benchmark/agent/chat - Agent chat benchmark
- GET /api/benchmark/health - Health check for benchmark mode
"""

import pytest
from httpx import AsyncClient, ASGITransport
import pytest_asyncio

from simu_emperor.adapters.web.server import app


@pytest_asyncio.fixture
async def async_client():
    """Create async test client for Benchmark API tests."""
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

    # Should return 200 with expected response format
    assert response.status_code == 200
    data = response.json()

    # Validate response structure
    assert "response" in data
    assert "tool_calls" in data
    assert "latency_ms" in data
    assert "success" in data

    # Validate types
    assert isinstance(data["response"], str)
    assert isinstance(data["tool_calls"], list)
    assert isinstance(data["latency_ms"], (int, float))
    assert isinstance(data["success"], bool)
    assert data["success"] is True

    # Validate tool_calls structure if present
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
    request_body = {
        "message": "查询直隶省的产值"
        # Missing agent_id
    }

    response = await async_client.post("/api/benchmark/agent/chat", json=request_body)

    # Should return 422 (Validation Error) or 400 (Bad Request)
    assert response.status_code in [400, 422]

    # Error response should have detail
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_benchmark_agent_chat_missing_message(async_client):
    """Test error handling when message is missing in request body."""
    request_body = {
        "agent_id": "governor_zhili"
        # Missing message
    }

    response = await async_client.post("/api/benchmark/agent/chat", json=request_body)

    # Should return 422 (Validation Error) or 400 (Bad Request)
    assert response.status_code in [400, 422]

    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_benchmark_agent_chat_empty_request_body(async_client):
    """Test error handling when request body is empty."""
    response = await async_client.post("/api/benchmark/agent/chat", json={})

    # Should return 422 (Validation Error)
    assert response.status_code == 422

    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_benchmark_agent_chat_invalid_agent(async_client):
    """Test error handling when agent_id doesn't exist."""
    request_body = {"agent_id": "nonexistent_agent_xyz", "message": "查询数据"}

    response = await async_client.post("/api/benchmark/agent/chat", json=request_body)

    # Should return 404 (Not Found) or error response with success=False
    # API could return 404 directly, or 200 with success=False
    assert response.status_code in [200, 404]

    data = response.json()

    if response.status_code == 200:
        # If 200, success should be False
        assert data.get("success") is False
        assert "error" in data or "response" in data
    else:
        # If 404, should have detail
        assert "detail" in data


@pytest.mark.asyncio
async def test_benchmark_agent_chat_empty_agent_id(async_client):
    """Test error handling when agent_id is empty string."""
    request_body = {"agent_id": "", "message": "查询数据"}

    response = await async_client.post("/api/benchmark/agent/chat", json=request_body)

    # Should return 422 or 400
    assert response.status_code in [400, 422]


@pytest.mark.asyncio
async def test_benchmark_agent_chat_empty_message(async_client):
    """Test error handling when message is empty string."""
    request_body = {"agent_id": "governor_zhili", "message": ""}

    response = await async_client.post("/api/benchmark/agent/chat", json=request_body)

    # Should return 422 or 400
    assert response.status_code in [400, 422]


# ============================================================================
# GET /api/benchmark/health - Health Check
# ============================================================================


@pytest.mark.asyncio
async def test_benchmark_health(async_client):
    """Test health check endpoint returns ok status and config."""
    response = await async_client.get("/api/benchmark/health")

    # Should return 200
    assert response.status_code == 200

    data = response.json()

    # Validate response structure
    assert "status" in data
    assert data["status"] == "ok"

    # Should include benchmark config
    assert "config" in data
    config = data["config"]
    assert isinstance(config, dict)

    # Config should contain test_mode flag
    assert "test_mode" in config
    assert isinstance(config["test_mode"], bool)

    # Config should contain database setting
    assert "database" in config
    assert isinstance(config["database"], str)


@pytest.mark.asyncio
async def test_benchmark_health_config_values(async_client):
    """Test health check returns expected config values for benchmark mode."""
    response = await async_client.get("/api/benchmark/health")

    assert response.status_code == 200

    data = response.json()
    config = data.get("config", {})

    # In benchmark mode, test_mode should be True
    assert config.get("test_mode") is True

    # Database should be a test database
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

    # This test will fail if endpoint doesn't exist
    assert response.status_code == 200

    data = response.json()

    # latency_ms should be a positive number
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

    # tool_calls should always be present (array, can be empty)
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

    # If there are tool calls, validate their format
    for tool_call in tool_calls:
        # Each tool call should have name, args, result
        assert "name" in tool_call
        assert "args" in tool_call
        assert "result" in tool_call

        # Types should be correct
        assert isinstance(tool_call["name"], str)
        assert isinstance(tool_call["args"], dict)
        assert isinstance(tool_call["result"], str)

        # Name should be a valid tool name (non-empty)
        assert len(tool_call["name"]) > 0


# ============================================================================
# Non-existent Endpoint Check
# ============================================================================


@pytest.mark.asyncio
async def test_benchmark_endpoints_not_yet_implemented(async_client):
    """
    META TEST: Verify benchmark endpoints don't exist yet (TDD RED phase).

    This test confirms we're in the RED phase - endpoints should return 404/405
    because they haven't been implemented yet.

    Remove or update this test once endpoints are implemented.
    """
    # POST endpoint should return 404 or 405 (not implemented yet)
    post_response = await async_client.post(
        "/api/benchmark/agent/chat", json={"agent_id": "test", "message": "test"}
    )
    assert post_response.status_code in [404, 405], (
        f"Expected 404/405 for unimplemented POST /api/benchmark/agent/chat, got {post_response.status_code}"
    )

    # GET endpoint should return 404 (not implemented yet)
    get_response = await async_client.get("/api/benchmark/health")
    assert get_response.status_code == 404, (
        f"Expected 404 for unimplemented GET /api/benchmark/health, got {get_response.status_code}"
    )
