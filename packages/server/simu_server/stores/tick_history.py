"""TickHistoryStore — persists per-tick snapshots for data visualization.

Each tick, a full NationData snapshot is serialized to JSON and stored.
Query methods extract time-series, cross-province comparisons, and
incident event timelines for the frontend charts.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from simu_shared.models import NationData
from simu_server.stores.database import Database

logger = logging.getLogger(__name__)


class TickHistoryStore:
    """Reads and writes tick snapshots in the tick_history table."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def save_snapshot(self, nation: NationData) -> None:
        """Persist a snapshot of the current nation state for the given turn."""
        ts = datetime.now(UTC).isoformat()
        await self._db.conn.execute(
            "INSERT OR REPLACE INTO tick_history (turn, timestamp, snapshot) VALUES (?, ?, ?)",
            (nation.turn, ts, nation.model_dump_json()),
        )
        await self._db.conn.commit()

    async def get_nation_ticks(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return nation-level time-series data (most recent *limit* ticks)."""
        cursor = await self._db.conn.execute(
            "SELECT turn, timestamp, snapshot FROM tick_history ORDER BY turn DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        result: list[dict[str, Any]] = []
        for turn, ts, raw in reversed(rows):  # oldest first
            nation = json.loads(raw)
            provinces = nation.get("provinces", {})
            result.append({
                "turn": turn,
                "timestamp": ts,
                "imperial_treasury": float(nation.get("imperial_treasury", 0)),
                "base_tax_rate": float(nation.get("base_tax_rate", 0)),
                "tribute_rate": float(nation.get("tribute_rate", 0)),
                "fixed_expenditure": float(nation.get("fixed_expenditure", 0)),
                "total_population": sum(
                    float(p.get("population", 0)) for p in provinces.values()
                ),
                "total_production": sum(
                    float(p.get("production_value", 0)) for p in provinces.values()
                ),
                "total_stockpile": sum(
                    float(p.get("stockpile", 0)) for p in provinces.values()
                ),
                "province_count": len(provinces),
                "active_incident_count": 0,  # filled by caller if needed
            })
        return result

    async def get_province_ticks(
        self, province_id: str, limit: int = 50
    ) -> dict[str, Any]:
        """Return time-series data for a single province."""
        cursor = await self._db.conn.execute(
            "SELECT turn, timestamp, snapshot FROM tick_history ORDER BY turn DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        ticks: list[dict[str, Any]] = []
        province_name = province_id
        for turn, ts, raw in reversed(rows):
            nation = json.loads(raw)
            prov = nation.get("provinces", {}).get(province_id)
            if prov is None:
                continue
            province_name = prov.get("name", province_id)
            base_tax = float(nation.get("base_tax_rate", 0))
            ticks.append({
                "turn": turn,
                "timestamp": ts,
                "production_value": float(prov.get("production_value", 0)),
                "population": float(prov.get("population", 0)),
                "stockpile": float(prov.get("stockpile", 0)),
                "fixed_expenditure": float(prov.get("fixed_expenditure", 0)),
                "tax_modifier": float(prov.get("tax_modifier", 0)),
                "base_production_growth": float(prov.get("base_production_growth", 0)),
                "base_population_growth": float(prov.get("base_population_growth", 0)),
                "actual_tax_rate": base_tax + float(prov.get("tax_modifier", 0)),
            })
        return {
            "province_id": province_id,
            "province_name": province_name,
            "ticks": ticks,
        }

    async def get_comparison(
        self, metric: str, turn: int | None = None
    ) -> dict[str, Any]:
        """Cross-province comparison for a given metric at a specific turn."""
        if turn is not None:
            cursor = await self._db.conn.execute(
                "SELECT turn, snapshot FROM tick_history WHERE turn = ?",
                (turn,),
            )
        else:
            cursor = await self._db.conn.execute(
                "SELECT turn, snapshot FROM tick_history ORDER BY turn DESC LIMIT 1",
            )
        row = await cursor.fetchone()
        if row is None:
            return {"turn": turn or 0, "metric": metric, "provinces": []}

        actual_turn, raw = row
        nation = json.loads(raw)
        provinces_data = nation.get("provinces", {})

        # Valid province-level numeric metrics
        valid_metrics = {
            "population", "production_value", "stockpile",
            "fixed_expenditure", "tax_modifier",
            "base_production_growth", "base_population_growth",
        }
        if metric not in valid_metrics:
            return {"turn": actual_turn, "metric": metric, "provinces": []}

        provinces = []
        for pid, prov in provinces_data.items():
            provinces.append({
                "province_id": pid,
                "name": prov.get("name", pid),
                "value": float(prov.get(metric, 0)),
            })
        provinces.sort(key=lambda x: x["value"], reverse=True)

        return {
            "turn": actual_turn,
            "metric": metric,
            "provinces": provinces,
        }
