"""Memory module data models."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class StructuredQuery:
    """
    Structured query representation.

    Attributes:
        raw_query: Original natural language query
        intent: Query type (query_history/query_status/query_data)
        entities: Extracted entities {action: [], target: [], time: ""}
        scope: current_session or cross_session
        depth: overview or tape
    """

    raw_query: str
    intent: str
    entities: dict
    scope: str
    depth: str


@dataclass(frozen=True)
class ParseResult:
    """
    Result of query parsing.

    Attributes:
        structured: Parsed structured query
        parsed_by: Parser identifier ("llm")
        latency_ms: Parsing latency in milliseconds
    """

    structured: StructuredQuery
    parsed_by: str
    latency_ms: float


@dataclass(frozen=True)
class RetrievalResult:
    """
    Result of memory retrieval.

    Attributes:
        query: Original query string
        scope: Retrieval scope used
        depth: Retrieval depth used
        results: List of retrieved event records
        sessions_searched: Optional list of session IDs searched
    """

    query: str
    scope: str
    depth: str
    results: list[dict]
    sessions_searched: list[str] | None = None


@dataclass
class TapeMetadataEntry:
    """
    Metadata entry for a tape in tape_meta.jsonl (V4).

    Represents one tape's metadata in the agent-level index.

    Attributes:
        session_id: Session identifier
        title: LLM-generated session title (≤50 chars)
        created_tick: Game tick when session was created (optional)
        created_time: ISO format timestamp when session was created
        last_updated_tick: Game tick when session was last updated (optional)
        last_updated_time: ISO format timestamp when session was last updated
        event_count: Number of events in the tape
        segment_index: List of compacted segments with summaries

    Note on naming convention:
        - created_tick/last_updated_tick: Timestamp semantics (point in time)
        - Contrast with TapeSegment.tick_start/tick_end which use range semantics
    """

    session_id: str
    title: str
    created_tick: int | None
    created_time: str
    last_updated_tick: int | None
    last_updated_time: str
    event_count: int = 0
    segment_index: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "title": self.title,
            "created_tick": self.created_tick,
            "created_time": self.created_time,
            "last_updated_tick": self.last_updated_tick,
            "last_updated_time": self.last_updated_time,
            "event_count": self.event_count,
            "segment_index": self.segment_index,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TapeMetadataEntry":
        """Create from dictionary for JSON deserialization."""
        return cls(
            session_id=data["session_id"],
            title=data["title"],
            created_tick=data.get("created_tick"),
            created_time=data["created_time"],
            last_updated_tick=data.get("last_updated_tick"),
            last_updated_time=data["last_updated_time"],
            event_count=data.get("event_count", 0),
            segment_index=data.get("segment_index", []),
        )


@dataclass(frozen=True)
class TapeSegment:
    """
    Continuous event segment from a tape.jsonl file (V4).

    Represents a contiguous range of events for context-rich retrieval.

    Attributes:
        session_id: Session identifier
        agent_id: Agent identifier
        start_position: Starting line number in tape.jsonl (0-indexed)
        end_position: Ending line number in tape.jsonl (inclusive)
        event_count: Number of events in this segment
        events: List of event dicts in this segment
        tick_start: First tick number in segment (optional)
        tick_end: Last tick number in segment (optional)
        timestamp_start: First ISO timestamp in segment (optional)
        timestamp_end: Last ISO timestamp in segment (optional)
        relevance_score: Calculated relevance score (0.0-1.0)

    Note on naming convention:
        - tick_start/tick_end: Range semantics (start and end of a range)
        - Contrast with TapeMetadataEntry.created_tick/last_updated_tick which use timestamp semantics
    """

    session_id: str
    agent_id: str
    start_position: int
    end_position: int
    event_count: int
    events: list[dict]
    tick_start: int | None = None
    tick_end: int | None = None
    timestamp_start: str | None = None
    timestamp_end: str | None = None
    relevance_score: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "start_position": self.start_position,
            "end_position": self.end_position,
            "event_count": self.event_count,
            "events": self.events,
            "tick_start": self.tick_start,
            "tick_end": self.tick_end,
            "timestamp_start": self.timestamp_start,
            "timestamp_end": self.timestamp_end,
            "relevance_score": self.relevance_score,
        }
