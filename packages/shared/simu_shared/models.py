"""Shared data models used by both Server and Agent SDK.

All models use Pydantic for validation and serialization.
Financial values use Decimal for precision.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    return f"evt_{ts}_{short_uuid}"


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AgentStatus(StrEnum):
    REGISTERED = "registered"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class InvocationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    WAITING_TASK = "waiting_task"
    WAITING_REPLY = "waiting_reply"
    FINISHED = "finished"
    FAILED = "failed"
    COMPLETED = "completed"


# ---------------------------------------------------------------------------
# TapeEvent — the universal event envelope
# ---------------------------------------------------------------------------

class TapeEvent(BaseModel):
    """Append-only event that flows through the system.

    Used for both Server-side routing and Agent-side Tape storage.
    """

    event_id: str = Field(default_factory=_make_event_id)
    src: str  # "player" | "agent:{id}" | "system:engine"
    dst: list[str]  # routing targets
    event_type: str  # see EventType constants
    payload: dict[str, Any] = Field(default_factory=dict)
    session_id: str
    timestamp: datetime = Field(default_factory=_utcnow)
    parent_event_id: str | None = None
    root_event_id: str | None = None
    invocation_id: str | None = None

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# RoutedMessage — Server-side persisted message for frontend display
# ---------------------------------------------------------------------------

class RoutedMessage(BaseModel):
    """A message stored by Server for frontend history display."""

    message_id: str = Field(default_factory=lambda: _make_id("msg"))
    session_id: str
    src: str
    dst: list[str]
    content: str
    event_type: str
    timestamp: datetime = Field(default_factory=_utcnow)
    origin_event_id: str | None = None  # points to source TapeEvent


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class Session(BaseModel):
    """A collaboration session scoping Agent interactions."""

    session_id: str = Field(default_factory=lambda: f"session:web:{uuid.uuid4().hex[:12]}")
    parent_id: str | None = None
    child_ids: list[str] = Field(default_factory=list)
    status: SessionStatus = SessionStatus.ACTIVE
    created_by: str = ""  # "player" or "agent:{id}"
    agent_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_task(self) -> bool:
        return self.parent_id is not None


# ---------------------------------------------------------------------------
# Agent Registration
# ---------------------------------------------------------------------------

class AgentRegistration(BaseModel):
    """An Agent's registration record managed by Server."""

    agent_id: str
    display_name: str = ""
    status: AgentStatus = AgentStatus.REGISTERED
    process_pid: int | None = None
    config_path: str = ""  # path to soul.md + data_scope.yaml directory
    callback_url: str | None = None
    registered_at: datetime = Field(default_factory=_utcnow)
    last_heartbeat: datetime | None = None
    capabilities: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Invocation — tracks a single Agent call lifecycle
# ---------------------------------------------------------------------------

class Invocation(BaseModel):
    """Tracks one Agent invocation from queue to completion."""

    invocation_id: str = Field(default_factory=lambda: _make_id("inv"))
    agent_id: str
    session_id: str
    trigger_event_id: str
    status: InvocationStatus = InvocationStatus.QUEUED
    callback_token: str = Field(default_factory=lambda: uuid.uuid4().hex)
    created_at: datetime = Field(default_factory=_utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# LLM / Agent Configuration
# ---------------------------------------------------------------------------

class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = "anthropic"  # "anthropic" | "openai" | "mock"
    model: str = "claude-sonnet-4-20250514"
    api_key: str = ""
    base_url: str | None = None  # Custom base URL for OpenAI-compatible APIs
    temperature: float = 0.7
    max_tokens: int = 4096


class ContextConfig(BaseModel):
    """Context window management settings."""

    max_tokens: int = 8000
    threshold_ratio: float = 0.95
    keep_recent_events: int = 20


class ReActConfig(BaseModel):
    """ReAct loop iteration limits."""

    max_iterations: int = 10
    max_tool_calls: int = 20


# ---------------------------------------------------------------------------
# Game Engine Models
# ---------------------------------------------------------------------------

class ProvinceData(BaseModel):
    """Economic and demographic data for a single province."""

    province_id: str
    name: str
    production_value: Decimal = Decimal("0")
    population: Decimal = Decimal("0")
    fixed_expenditure: Decimal = Decimal("0")
    stockpile: Decimal = Decimal("0")
    base_production_growth: Decimal = Decimal("0.01")
    base_population_growth: Decimal = Decimal("0.005")
    tax_modifier: Decimal = Decimal("0.0")


class NationData(BaseModel):
    """Top-level nation state (one per game session)."""

    turn: int = 0
    base_tax_rate: Decimal = Decimal("0.10")
    tribute_rate: Decimal = Decimal("0.8")
    fixed_expenditure: Decimal = Decimal("0")
    imperial_treasury: Decimal = Decimal("0")
    provinces: dict[str, ProvinceData] = Field(default_factory=dict)


class Effect(BaseModel):
    """A single numeric effect applied by an Incident."""

    target_path: str  # e.g. "provinces.zhili.production_value"
    add: Decimal | None = None
    factor: Decimal | None = None

    def model_post_init(self, __context: Any) -> None:
        if (self.add is None) == (self.factor is None):
            msg = "Effect must have exactly one of 'add' or 'factor'"
            raise ValueError(msg)
        if self.factor is not None and self.factor <= Decimal("-1"):
            msg = "factor must be > -1.0"
            raise ValueError(msg)


class Incident(BaseModel):
    """A time-limited event with economic effects."""

    incident_id: str = Field(default_factory=lambda: _make_id("inc"))
    title: str
    description: str = ""
    effects: list[Effect] = Field(default_factory=list)
    source: str = "system"
    remaining_ticks: int
    applied: bool = False
