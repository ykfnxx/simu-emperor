# Tool Registration System

This directory contains tool handlers for Agent function calling.

## Architecture

The tool system has two components:

1. **Tool Handlers** (`query_tools.py`, `action_tools.py`, `memory_tools.py`)
   - Implement actual tool logic
   - Return formatted results to LLM

2. **ToolRegistry** (`tool_registry.py`) - NEW
   - Centralized tool registration with metadata
   - Provides unified interface for tool management
   - Supports OpenAI function schema conversion

## Migration Path

The Agent class currently uses `_function_handlers` dict directly.
Future versions will migrate to ToolRegistry for better organization.

## Tool Categories

- **Query**: Retrieve data without side effects (query_province_data, etc.)
- **Action**: Execute game actions with side effects (send_game_event, etc.)
- **Memory**: Retrieve historical information (retrieve_memory)

## Example Usage

```python
from simu_emperor.agents.tools.tool_registry import ToolRegistry, ToolMetadata

registry = ToolRegistry()

metadata = ToolMetadata(
    name="query_province_data",
    description="Query province-specific data",
    parameters={
        "type": "object",
        "properties": {
            "province_id": {"type": "string"},
            "field_path": {"type": "string"},
        },
        "required": ["province_id", "field_path"],
    },
    category="query",
)

registry.register(
    "query_province_data",
    self._query_tools.query_province_data,
    metadata,
)

# Get handler
handler = registry.get_handler("query_province_data")

# Get OpenAI schema
schemas = registry.to_openai_schemas()
```
