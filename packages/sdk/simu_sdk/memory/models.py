"""Data models for the memory system."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ViewSegment(BaseModel):
    """A compressed segment of tape events."""

    view_id: str  # "view_{session_id}_{start}_{end}"
    session_id: str
    start_index: int  # tape event offset (inclusive)
    end_index: int  # tape event offset (exclusive)
    summary: str  # LLM-generated summary
    event_count: int
    created_at: datetime = Field(default_factory=_utcnow)


class TapeMetadata(BaseModel):
    """Per-session metadata for memory indexing."""

    session_id: str
    title: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    event_count: int = 0
    window_offset: int = 0  # sliding window start position
    summary: str = ""  # fixed-length replacement summary (≤300 tokens)
    views: list[ViewSegment] = Field(default_factory=list)


class MemoryResult(BaseModel):
    """A single result from memory retrieval."""

    session_id: str
    session_title: str = ""
    view_summary: str = ""
    relevance_score: float = 0.0
