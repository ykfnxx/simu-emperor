"""Minister of Revenue (户部尚书) — manages taxation and national finances.

This is a reference implementation showing how to build a specialized
Agent using the SDK.  The minister monitors treasury levels, advises
on tax policy, and reports financial summaries after each tick.
"""

from __future__ import annotations

import json

from simu_shared.models import TapeEvent
from simu_sdk import tool
from simu_sdk.config import AgentConfig
from simu_agents.base_minister import BaseMinister


class MinisterOfRevenue(BaseMinister):
    """户部尚书 — the Emperor's chief financial advisor."""

    @tool(
        name="propose_tax_change",
        description="Propose a change to the national base tax rate.",
        parameters={
            "new_rate": {
                "type": "number",
                "description": "Proposed new tax rate (0.0 to 1.0).",
            },
            "reason": {
                "type": "string",
                "description": "Justification for the proposed change.",
            },
        },
        category="domain",
    )
    async def propose_tax_change(self, args: dict, event: TapeEvent) -> str:
        new_rate = args.get("new_rate", 0.1)
        reason = args.get("reason", "")
        await self.server.post_message(
            recipients=["player"],
            message=f"臣建议将税率调整为 {new_rate * 100:.1f}%。理由：{reason}",
            session_id=event.session_id,
        )
        return f"Tax change proposal sent: {new_rate * 100:.1f}%"

    @tool(
        name="financial_report",
        description="Generate a summary financial report of the empire.",
        parameters={},
        category="domain",
    )
    async def financial_report(self, args: dict, event: TapeEvent) -> str:
        state = await self.server.query_state()
        treasury = state.get("imperial_treasury", "unknown")
        turn = state.get("turn", 0)
        provinces = state.get("provinces", {})

        total_prod = sum(
            float(p.get("production_value", 0))
            for p in provinces.values()
        ) if isinstance(provinces, dict) else 0

        return json.dumps({
            "turn": turn,
            "imperial_treasury": str(treasury),
            "total_production": f"{total_prod:.2f}",
            "province_count": len(provinces) if isinstance(provinces, dict) else 0,
        }, ensure_ascii=False)
