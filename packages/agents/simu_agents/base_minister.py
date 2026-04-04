"""BaseMinister — common base for all imperial court agents.

Extends ``BaseAgent`` with domain-specific tools shared by all ministers
(e.g. querying treasury, proposing edicts).  Individual ministers override
``on_event`` or add their own ``@tool`` methods for specialized behavior.
"""

from __future__ import annotations

import json
from typing import Any

from simu_shared.constants import EventType
from simu_shared.models import TapeEvent
from simu_sdk import BaseAgent, tool
from simu_sdk.config import AgentConfig


class BaseMinister(BaseAgent):
    """Base class for imperial court Agent implementations.

    Adds domain tools beyond the SDK's standard ``send_message`` / ``query_state``.
    """

    @tool(
        name="query_treasury",
        description="Query the imperial treasury balance and tax information.",
        parameters={},
        category="domain",
    )
    async def query_treasury(self, args: dict, event: TapeEvent) -> str:
        result = await self.server.query_state(path="imperial_treasury")
        return json.dumps(result, ensure_ascii=False, default=str)

    @tool(
        name="query_province",
        description="Query detailed data for a specific province.",
        parameters={
            "province_id": {
                "type": "string",
                "description": "The province identifier, e.g. 'zhili'.",
            },
        },
        category="domain",
    )
    async def query_province(self, args: dict, event: TapeEvent) -> str:
        province_id = args.get("province_id", "")
        result = await self.server.query_state(path=f"provinces.{province_id}")
        return json.dumps(result, ensure_ascii=False, default=str)

    @tool(
        name="query_all_provinces",
        description="Query summary data for all provinces.",
        parameters={},
        category="domain",
    )
    async def query_all_provinces(self, args: dict, event: TapeEvent) -> str:
        result = await self.server.query_state(path="provinces")
        return json.dumps(result, ensure_ascii=False, default=str)

    async def on_event(self, event: TapeEvent) -> None:
        """Default dispatch — tick events get special handling."""
        if event.event_type == EventType.TICK_COMPLETED:
            await self._handle_tick(event)
        else:
            await super().on_event(event)

    async def _handle_tick(self, event: TapeEvent) -> None:
        """Process a tick event — can be overridden by specific ministers."""
        await self.react(event)
