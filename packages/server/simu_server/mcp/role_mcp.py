"""role-mcp — Role and agent information MCP server.

Exposes MCP tools for:
- query_role_map: get the role assignment map
- get_agents: list all registered agents and their status
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from simu_server.mcp.auth import get_agent_id

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dependency injection
# ---------------------------------------------------------------------------

_deps: dict[str, Any] = {}


def set_dependencies(**kwargs: Any) -> None:
    _deps.update(kwargs)


def _get(name: str) -> Any:
    v = _deps.get(name)
    if v is None:
        raise RuntimeError(f"MCP dependency not set: {name}")
    return v


# ---------------------------------------------------------------------------
# FastMCP server instance
# ---------------------------------------------------------------------------

role_mcp = FastMCP("role-mcp")


# ---------------------------------------------------------------------------
# Tool: query_role_map
# ---------------------------------------------------------------------------

@role_mcp.tool()
async def query_role_map() -> str:
    """Query the role assignment map.

    Returns structured data about all official roles, including
    title, agent_id, name, and duty for each role.
    """
    get_agent_id()  # ensure authenticated

    from simu_server.config import settings

    role_map_path = settings.data_dir / "role_map.md"
    if not role_map_path.exists():
        return json.dumps({"roles": []})

    text = role_map_path.read_text(encoding="utf-8")
    roles: list[dict[str, str]] = []
    current: dict[str, str] = {}

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("## "):
            if current:
                roles.append(current)
            title_part = line[3:].strip()
            agent_id = ""
            title = title_part
            if "(" in title_part and ")" in title_part:
                idx = title_part.index("(")
                title = title_part[:idx].strip()
                agent_id = title_part[idx + 1 : title_part.index(")")].strip()
            current = {"title": title, "agent_id": agent_id, "name": "", "duty": ""}
        elif line.startswith("- 姓名：") and current:
            current["name"] = line[len("- 姓名：") :].strip()
        elif line.startswith("- 职责：") and current:
            current["duty"] = line[len("- 职责：") :].strip()

    if current:
        roles.append(current)

    return json.dumps({"roles": roles}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool: get_agents
# ---------------------------------------------------------------------------

@role_mcp.tool()
async def get_agents() -> str:
    """List all registered agents with their status.

    Returns a JSON array with agent_id, display_name, and status
    for each registered agent.
    """
    get_agent_id()  # ensure authenticated

    agents = await _get("agent_registry").list_all()
    result = [
        {"agent_id": a.agent_id, "display_name": a.display_name, "status": a.status.value}
        for a in agents
    ]
    return json.dumps(result, ensure_ascii=False)
