"""Memory module data models."""

from dataclasses import dataclass, field, asdict
from enum import Enum
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
        window_offset: Position anchor for incremental tape loading (default 0)
        summary: Cumulative summary of compacted events (default "")
        anchor_index: List of anchors with state summaries
    """

    session_id: str
    title: str
    created_tick: int | None
    created_time: str
    last_updated_tick: int | None
    last_updated_time: str
    event_count: int = 0
    window_offset: int = 0
    summary: str = ""
    anchor_index: list[dict] = field(default_factory=list)

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
            "window_offset": self.window_offset,
            "summary": self.summary,
            "anchor_index": self.anchor_index,
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
            window_offset=data.get("window_offset", 0),
            summary=data.get("summary", ""),
            anchor_index=data.get("anchor_index", []),
        )


@dataclass
class TapeAnchor:
    """tape.systems Anchor: state-bearing checkpoint."""

    anchor_id: str
    name: str
    tape_position: int
    state: dict
    created_at: str
    created_tick: int | None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TapeAnchor":
        return cls(**data)


@dataclass(frozen=True)
class TapeView:
    """tape.systems View: anchor-bounded immutable context window."""

    view_id: str
    session_id: str
    agent_id: str
    anchor_start_id: str | None
    anchor_end_id: str | None
    tape_position_start: int
    tape_position_end: int
    events: list[dict]
    anchor_state: dict | None
    tick_start: int | None
    tick_end: int | None
    event_count: int
    relevance_score: float = 0.0

    @property
    def frozen(self) -> bool:
        return True

    def to_text(self) -> str:
        parts = []
        if self.anchor_state and "summary" in self.anchor_state:
            parts.append(self.anchor_state["summary"])
        for evt in self.events:
            if isinstance(evt.get("payload"), dict):
                msg = evt["payload"].get("message", "")
                if msg:
                    parts.append(msg)
        return "\n".join(parts)


class AnchorStrategy(Enum):
    LAST_ANCHOR = "last_anchor"
    NAMED = "named"
    FULL = "full"
