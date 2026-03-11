"""Memory system configuration constants.

V4: Configurable via pydantic-settings for environment variable overrides.
"""


from pydantic_settings import BaseSettings, SettingsConfigDict


# Legacy constants for backward compatibility
# Deprecated: Use MemoryConfig class instead
SEGMENT_SIZE = 10  # Number of events per segment
DEFAULT_MAX_RESULTS = 5  # Default maximum number of results to return
KEEP_RECENT_EVENTS = 20  # Number of recent events to keep after window compaction
TITLE_MATCH_WEIGHT = 0.4
SUMMARY_MATCH_WEIGHT = 0.3
SEGMENT_MATCH_WEIGHT = 0.2


class SearchWeights(BaseSettings):
    """
    Scoring weights for metadata matching.

    Environment variables:
        MEMORY_TITLE_MATCH_WEIGHT: Weight for title matching (default: 0.4)
        MEMORY_SUMMARY_MATCH_WEIGHT: Weight for summary matching (default: 0.3)
        MEMORY_SEGMENT_MATCH_WEIGHT: Weight for segment matching (default: 0.2)
    """

    model_config = SettingsConfigDict(
        env_prefix="MEMORY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    title: float = 0.4
    summary: float = 0.3
    segment: float = 0.2


class MemoryConfig(BaseSettings):
    """
    Memory system configuration with environment variable support.

    Environment variables:
        MEMORY_SEGMENT_SIZE: Number of events per segment (default: 10)
        MEMORY_MAX_RESULTS: Default maximum number of results to return (default: 5)
        MEMORY_KEEP_RECENT_EVENTS: Number of recent events to keep after compaction (default: 20)
        MEMORY_TITLE_MATCH_WEIGHT: Weight for title matching (default: 0.4)
        MEMORY_SUMMARY_MATCH_WEIGHT: Weight for summary matching (default: 0.3)
        MEMORY_SEGMENT_MATCH_WEIGHT: Weight for segment matching (default: 0.2)

    Example:
        # Override via environment
        export MEMORY_SEGMENT_SIZE=20
        export MEMORY_KEEP_RECENT_EVENTS=30

        # Or create custom config
        config = MemoryConfig(segment_size=20, keep_recent_events=30)
    """

    model_config = SettingsConfigDict(
        env_prefix="MEMORY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Segment-based search configuration
    segment_size: int = 10

    # Search result limits
    max_results: int = 5

    # Context management
    keep_recent_events: int = 20

    # Scoring weights (deprecated - use SearchWeights class)
    title_match_weight: float = 0.4
    summary_match_weight: float = 0.3
    segment_match_weight: float = 0.2

    def get_search_weights(self) -> SearchWeights:
        """Get search weights as a nested config object."""
        return SearchWeights(
            title=self.title_match_weight,
            summary=self.summary_match_weight,
            segment=self.segment_match_weight,
        )


# Default singleton instance
_default_config: MemoryConfig | None = None


def get_memory_config() -> MemoryConfig:
    """Get the default memory configuration singleton."""
    global _default_config
    if _default_config is None:
        _default_config = MemoryConfig()
    return _default_config


def reset_memory_config() -> None:
    """Reset the default memory configuration singleton (for testing)."""
    global _default_config
    _default_config = None


__all__ = [
    # Legacy constants (deprecated)
    "SEGMENT_SIZE",
    "DEFAULT_MAX_RESULTS",
    "KEEP_RECENT_EVENTS",
    "TITLE_MATCH_WEIGHT",
    "SUMMARY_MATCH_WEIGHT",
    "SEGMENT_MATCH_WEIGHT",
    # New configurable classes
    "MemoryConfig",
    "SearchWeights",
    "get_memory_config",
    "reset_memory_config",
]
