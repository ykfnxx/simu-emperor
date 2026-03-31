"""Tool handlers for Agent function calling.

Provides QueryTools, ActionTools, and the decorator-based registry system.
"""

from simu_emperor.agents.tools.action_tools import ActionTools
from simu_emperor.agents.tools.query_tools import QueryTools
from simu_emperor.agents.tools.registry import ToolProvider, ToolRegistry, ToolResult, tool

__all__ = ["QueryTools", "ActionTools", "ToolProvider", "ToolRegistry", "ToolResult", "tool"]
