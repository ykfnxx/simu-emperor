"""Agent-related utility functions."""

from simu_emperor.common.constants import AGENT_DISPLAY_NAMES


def normalize_agent_id(agent_id: str) -> str:
    """Normalize agent ID to include 'agent:' prefix if missing.

    Args:
        agent_id: Agent ID with or without 'agent:' prefix

    Returns:
        Normalized agent ID with 'agent:' prefix
    """
    if agent_id.startswith("agent:"):
        return agent_id
    return f"agent:{agent_id}"


def strip_agent_prefix(agent_id: str) -> str:
    """Remove 'agent:' prefix from agent ID if present.

    Args:
        agent_id: Agent ID with or without 'agent:' prefix

    Returns:
        Agent ID without 'agent:' prefix
    """
    if agent_id.startswith("agent:"):
        return agent_id[6:]  # Remove "agent:" prefix
    return agent_id


def get_agent_display_name(src: str) -> str:
    """Get human-readable display name from agent source ID.

    Args:
        src: Agent source ID (e.g., "agent:governor_zhili")

    Returns:
        Display name (e.g., "直隶巡抚")
    """
    # Extract agent_id from source
    agent_id = strip_agent_prefix(src)
    return AGENT_DISPLAY_NAMES.get(agent_id, agent_id)
