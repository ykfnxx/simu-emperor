"""Agent-related utility functions."""

from pathlib import Path

from simu_emperor.common.constants import AGENT_DISPLAY_NAMES
from simu_emperor.config import settings


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


def get_agent_display_name(src: str, data_dir: Path | None = None) -> str:
    """Get human-readable display name from agent source ID.

    Args:
        src: Agent source ID (e.g., "agent:governor_zhili")
        data_dir: Data directory path (for dynamic agents)

    Returns:
        Display name (e.g., "直隶巡抚")
    """
    # Extract agent_id from source
    agent_id = strip_agent_prefix(src)

    # First check static mapping
    if agent_id in AGENT_DISPLAY_NAMES:
        return AGENT_DISPLAY_NAMES[agent_id]

    # For dynamic agents, try to read from soul.md
    _data_dir = data_dir or settings.data_dir
    agent_dir = _data_dir / "agent" / "web" / agent_id
    soul_path = agent_dir / "soul.md"

    if soul_path.exists():
        try:
            content = soul_path.read_text(encoding="utf-8")
            # Extract title from first line (format: "# {title} - {name}")
            first_line = content.split("\n")[0]
            if first_line.startswith("# "):
                # Remove "# " prefix and extract title (before " - ")
                title_part = first_line[2:]
                if " - " in title_part:
                    title = title_part.split(" - ")[0].strip()
                    return title
                return title_part.strip()
        except Exception:
            pass

    # Fallback to agent_id
    return agent_id
