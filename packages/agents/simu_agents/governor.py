"""Governor (地方官) — manages a specific province.

Monitors local economic indicators, handles incidents affecting the
province, and reports to the court.
"""

from __future__ import annotations

import json

from simu_shared.models import TapeEvent
from simu_sdk import tool
from simu_agents.base_minister import BaseMinister


class Governor(BaseMinister):
    """地方官 — provincial administrator."""

    @property
    def province_id(self) -> str:
        """Read province assignment from data_scope config."""
        return self.data_scope.get("province_id", "")

    @tool(
        name="local_report",
        description="Generate a report on the governor's province.",
        parameters={},
        category="domain",
    )
    async def local_report(self, args: dict, event: TapeEvent) -> str:
        if not self.province_id:
            return "No province assigned."
        result = await self.server.query_state(path=f"provinces.{self.province_id}")
        return json.dumps(result, ensure_ascii=False, default=str)

    @tool(
        name="request_funds",
        description="Request funds from the imperial treasury for local projects.",
        parameters={
            "amount": {"type": "number", "description": "Amount requested."},
            "purpose": {"type": "string", "description": "Purpose of the request."},
        },
        category="domain",
    )
    async def request_funds(self, args: dict, event: TapeEvent) -> str:
        amount = args.get("amount", 0)
        purpose = args.get("purpose", "")
        await self.server.post_message(
            recipients=["player"],
            message=f"臣请求拨款 {amount}，用于{purpose}。",
            session_id=event.session_id,
        )
        return f"Fund request sent: {amount} for {purpose}"
