"""Memory module for V4 memory system."""

# V4 Components
from simu_emperor.memory.config import (
    SEGMENT_SIZE,
    DEFAULT_MAX_RESULTS,
    KEEP_RECENT_EVENTS,
    TITLE_MATCH_WEIGHT,
    SUMMARY_MATCH_WEIGHT,
    SEGMENT_MATCH_WEIGHT,
)
from simu_emperor.memory.models import TapeMetadataEntry, TapeAnchor, TapeView, AnchorStrategy
from simu_emperor.memory.tape_metadata import TapeMetadataManager
from simu_emperor.memory.tape_metadata_index import TapeMetadataIndex

from simu_emperor.memory.segment_searcher import SegmentSearcher
from simu_emperor.memory.two_level_searcher import TwoLevelSearcher
from simu_emperor.memory.vector_searcher import VectorSearcher

# V3 Components (still used)
from simu_emperor.memory.context_manager import ContextManager, ContextConfig, count_tokens
from simu_emperor.memory.exceptions import ParseError, RetrievalError
from simu_emperor.memory.models import StructuredQuery, ParseResult, RetrievalResult
from simu_emperor.memory.query_parser import QueryParser
from simu_emperor.memory.structured_retriever import StructuredRetriever
from simu_emperor.memory.tape_writer import TapeWriter

__all__ = [
    # V4 Config
    "SEGMENT_SIZE",
    "DEFAULT_MAX_RESULTS",
    "KEEP_RECENT_EVENTS",
    "TITLE_MATCH_WEIGHT",
    "SUMMARY_MATCH_WEIGHT",
    "SEGMENT_MATCH_WEIGHT",
    # V4 Models
    "TapeMetadataEntry",
    "TapeAnchor",
    "TapeView",
    "AnchorStrategy",
    # V4 Components
    "TapeMetadataManager",
    "TapeMetadataIndex",
    "SegmentSearcher",
    "TwoLevelSearcher",
    "VectorSearcher",
    # V3 Components
    "ContextManager",
    "ContextConfig",
    "count_tokens",
    "ParseError",
    "RetrievalError",
    "StructuredQuery",
    "ParseResult",
    "RetrievalResult",
    "QueryParser",
    "StructuredRetriever",
    "TapeWriter",
]
