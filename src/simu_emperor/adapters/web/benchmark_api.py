"""Benchmark API endpoints for performance testing.

Provides synchronous HTTP endpoints for benchmarking agent performance:
- POST /api/benchmark/agent/chat - Send message to agent and get response with metrics
- GET /api/benchmark/health - Health check for benchmark mode
"""

import asyncio
import logging
import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])


# ============================================================================
# Pydantic Models
# ============================================================================


class BenchmarkChatRequest(BaseModel):
    """Request model for benchmark agent chat."""

    agent_id: str = Field(..., description="Target agent ID")
    message: str = Field(..., description="Message to send to the agent")
    session_id: Optional[str] = Field(None, description="Optional session ID")


class ToolCall(BaseModel):
    """Model representing a tool call made by the agent."""

    name: str = Field(..., description="Tool name")
    args: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    result: str = Field(..., description="Tool execution result")


class BenchmarkChatResponse(BaseModel):
    """Response model for benchmark agent chat."""

    response: str = Field(..., description="Agent's response text")
    tool_calls: list[ToolCall] = Field(
        default_factory=list, description="Tool calls made during processing"
    )
    latency_ms: float = Field(..., description="Total processing latency in milliseconds")
    success: bool = Field(..., description="Whether the request was successful")
    error: Optional[str] = Field(None, description="Error message if not successful")


class BenchmarkHealthResponse(BaseModel):
    """Response model for benchmark health check."""

    status: str = Field(..., description="Health status")
    config: dict[str, Any] = Field(..., description="Benchmark configuration")


# ============================================================================
# Helper Functions
# ============================================================================


def _get_game_instance():
    from simu_emperor.adapters.web.server import game_instance

    return game_instance


# ============================================================================
# Benchmark Endpoint Handlers
# ============================================================================


@router.get("/health", response_model=BenchmarkHealthResponse)
async def benchmark_health():
    """Health check endpoint for benchmark mode.

    Returns:
        BenchmarkHealthResponse with status and config.
    """
    return BenchmarkHealthResponse(
        status="ok",
        config={
            "test_mode": True,
            "database": "test_benchmark.db",
        },
    )


@router.post("/agent/chat", response_model=BenchmarkChatResponse)
async def benchmark_agent_chat(request: BenchmarkChatRequest):
    """Send a message to an agent and get response with performance metrics.

    This endpoint provides synchronous HTTP access to agent chat functionality
    for benchmarking purposes. It collects:
    - Agent's response text
    - All tool calls made during processing
    - Total latency in milliseconds

    Args:
        request: BenchmarkChatRequest with agent_id, message, and optional session_id.

    Returns:
        BenchmarkChatResponse with response, tool_calls, latency_ms, and success.

    Raises:
        HTTPException: 400 if request validation fails, 503 if services unavailable.
    """
    if not request.agent_id or not request.agent_id.strip():
        raise HTTPException(status_code=400, detail="agent_id cannot be empty")

    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    game_instance = _get_game_instance()

    if not game_instance.is_running:
        raise HTTPException(status_code=503, detail="Game not initialized")

    agent_manager = game_instance.agent_manager
    if not agent_manager:
        raise HTTPException(status_code=503, detail="Agent manager not available")

    from simu_emperor.common import strip_agent_prefix

    normalized_agent_id = strip_agent_prefix(request.agent_id)

    agent = agent_manager.get_agent(normalized_agent_id)
    if not agent:
        return BenchmarkChatResponse(
            response="",
            tool_calls=[],
            latency_ms=0.0,
            success=False,
            error=f"Agent not found: {normalized_agent_id}",
        )

    import uuid

    benchmark_session_id = (
        request.session_id or f"benchmark:{normalized_agent_id}:{uuid.uuid4().hex[:8]}"
    )

    start_time = time.perf_counter()
    collected_tool_calls: list[ToolCall] = []
    response_text = ""
    response_received = asyncio.Event()

    event_bus = game_instance.event_bus
    if not event_bus:
        raise HTTPException(status_code=503, detail="Event bus not available")

    async def benchmark_event_handler(event: Event) -> None:
        nonlocal response_text

        if event.session_id != benchmark_session_id:
            return

        if event.type == EventType.OBSERVATION:
            actions = event.payload.get("actions", [])
            for action in actions:
                tool_name = action.get("tool", "")
                tool_result = action.get("result", "")
                if tool_name:
                    collected_tool_calls.append(
                        ToolCall(
                            name=tool_name,
                            args={},
                            result=str(tool_result),
                        )
                    )

        if event.type in (EventType.AGENT_MESSAGE, EventType.RESPONSE):
            payload = event.payload or {}
            response_text = (
                payload.get("content") or payload.get("message") or payload.get("response", "")
            )
            response_received.set()

    event_bus.subscribe("*", benchmark_event_handler)

    try:
        chat_event = Event(
            src="benchmark",
            dst=[f"agent:{normalized_agent_id}"],
            type=EventType.CHAT,
            payload={"message": request.message},
            session_id=benchmark_session_id,
        )

        await event_bus.send_event(chat_event)

        try:
            await asyncio.wait_for(response_received.wait(), timeout=60.0)
        except asyncio.TimeoutError:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return BenchmarkChatResponse(
                response="",
                tool_calls=collected_tool_calls,
                latency_ms=latency_ms,
                success=False,
                error="Timeout waiting for agent response",
            )

        latency_ms = (time.perf_counter() - start_time) * 1000

        return BenchmarkChatResponse(
            response=response_text,
            tool_calls=collected_tool_calls,
            latency_ms=latency_ms,
            success=True,
            error=None,
        )

    except Exception as e:
        logger.error(f"Benchmark chat error: {e}", exc_info=True)
        latency_ms = (time.perf_counter() - start_time) * 1000
        return BenchmarkChatResponse(
            response="",
            tool_calls=collected_tool_calls,
            latency_ms=latency_ms,
            success=False,
            error=str(e),
        )

    finally:
        event_bus.unsubscribe("*", benchmark_event_handler)
