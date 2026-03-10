"""Memory system configuration constants."""

# Segment-based search configuration
SEGMENT_SIZE = 10  # Number of events per segment

# Search result limits
DEFAULT_MAX_RESULTS = 5  # Default maximum number of results to return

# Context management
KEEP_RECENT_EVENTS = 20  # Number of recent events to keep after window compaction

# Scoring weights for metadata matching
TITLE_MATCH_WEIGHT = 0.4
SUMMARY_MATCH_WEIGHT = 0.3
SEGMENT_MATCH_WEIGHT = 0.2

__all__ = [
    "SEGMENT_SIZE",
    "DEFAULT_MAX_RESULTS",
    "KEEP_RECENT_EVENTS",
    "TITLE_MATCH_WEIGHT",
    "SUMMARY_MATCH_WEIGHT",
    "SEGMENT_MATCH_WEIGHT",
]
