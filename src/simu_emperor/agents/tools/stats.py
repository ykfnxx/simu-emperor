"""Token statistics tracking for tool calls."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TokenStats(BaseModel):
    """Token usage statistics for a single LLM call with tools."""

    agent_id: str = Field(description="Agent identifier")
    turn: int = Field(description="Game turn number")
    phase: Literal["respond", "execute"] = Field(description="Game phase")
    prompt_tokens: int = Field(description="Number of prompt/input tokens")
    completion_tokens: int = Field(description="Number of completion/output tokens")
    tool_calls_count: int = Field(default=0, description="Number of tool calls made")
    iteration: int = Field(default=1, description="Iteration number within the loop")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When the LLM call was made",
    )

    @property
    def total_tokens(self) -> int:
        """Total tokens used in this call."""
        return self.prompt_tokens + self.completion_tokens


class TokenStatsCollector:
    """Collector for aggregating token statistics."""

    def __init__(self) -> None:
        self._stats: list[TokenStats] = []

    def add(self, stats: TokenStats) -> None:
        """Add a token stats record."""
        self._stats.append(stats)

    def get_all(self) -> list[TokenStats]:
        """Get all collected stats."""
        return list(self._stats)

    def get_by_agent(self, agent_id: str) -> list[TokenStats]:
        """Get stats for a specific agent."""
        return [s for s in self._stats if s.agent_id == agent_id]

    def get_by_turn(self, turn: int) -> list[TokenStats]:
        """Get stats for a specific turn."""
        return [s for s in self._stats if s.turn == turn]

    def get_total_tokens(self) -> int:
        """Get total tokens across all records."""
        return sum(s.total_tokens for s in self._stats)

    def get_total_by_agent(self, agent_id: str) -> int:
        """Get total tokens for a specific agent."""
        return sum(s.total_tokens for s in self._stats if s.agent_id == agent_id)

    def clear(self) -> None:
        """Clear all collected stats."""
        self._stats.clear()
