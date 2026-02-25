"""Data models for tool function calling."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """Parameter definition for a tool."""

    name: str = Field(description="Parameter name")
    description: str = Field(description="Parameter description")
    type: Literal["string", "number", "integer", "boolean", "array", "object"] = Field(
        description="Parameter type"
    )
    required: bool = Field(default=True, description="Whether parameter is required")
    enum: list[Any] | None = Field(default=None, description="Allowed values if enum")


class Tool(BaseModel):
    """Tool definition."""

    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    parameters: list[ToolParameter] = Field(default_factory=list, description="Tool parameters")


class ToolCall(BaseModel):
    """A tool call request from the LLM."""

    tool_name: str = Field(description="Name of tool to call")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")
    call_id: str = Field(description="Unique identifier for this call")


class ToolResult(BaseModel):
    """Result of a tool execution."""

    call_id: str = Field(description="ID of the corresponding tool call")
    tool_name: str = Field(description="Name of the tool that was executed")
    result: Any = Field(description="Tool execution result (serialized JSON)")
    error: str | None = Field(default=None, description="Error message if execution failed")


class ToolCallResponse(BaseModel):
    """Response from LLM that may contain tool calls."""

    content: str | None = Field(default=None, description="Text content if any")
    tool_calls: list[ToolCall] | None = Field(default=None, description="Tool calls if any")

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return bool(self.tool_calls)
