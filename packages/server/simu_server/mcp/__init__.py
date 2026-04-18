"""MCP Server Layer — simu-mcp and role-mcp services.

Provides MCP (Model Context Protocol) interfaces for agent-server interaction,
replacing the V5 HTTP callback pattern with standard MCP tool calls.
"""

from simu_server.mcp.simu_mcp import simu_mcp, set_dependencies as set_simu_dependencies
from simu_server.mcp.role_mcp import role_mcp, set_dependencies as set_role_dependencies

__all__ = [
    "simu_mcp",
    "role_mcp",
    "set_simu_dependencies",
    "set_role_dependencies",
]
