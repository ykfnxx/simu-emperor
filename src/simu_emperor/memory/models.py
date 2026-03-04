"""Memory module data models."""

from dataclasses import dataclass


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
