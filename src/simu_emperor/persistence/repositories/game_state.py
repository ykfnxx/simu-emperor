import json
import logging
from decimal import Decimal
from typing import Any

from simu_emperor.persistence.client import SeekDBClient


logger = logging.getLogger(__name__)


TABLE_PROVINCES = "provinces"
TABLE_NATIONAL_TREASURY = "national_treasury"
TABLE_GAME_TICK = "game_tick"


class GameStateRepository:
    def __init__(self, client: SeekDBClient):
        self._client = client

    async def get_tick(self) -> int:
        row = await self._client.fetch_one("SELECT tick FROM game_tick WHERE id = 1")
        return row["tick"] if row else 0

    async def get_province(self, province_id: str) -> dict[str, Any] | None:
        return await self._client.fetch_one(
            "SELECT * FROM provinces WHERE province_id = ?", province_id
        )

    async def save_province(self, province_id: str, data: dict[str, Any]) -> None:
        fields = []
        values = []
        for key in ["population", "treasury", "tax_rate", "stability", "production_value"]:
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])

        if not fields:
            return

        sql = f"UPDATE provinces SET {', '.join(fields)} WHERE province_id = ?"
        await self._client.execute(sql, *values, province_id)

    async def get_national_treasury(self) -> dict[str, Any] | None:
        return await self._client.fetch_one("SELECT * FROM national_treasury WHERE id = 1")

    async def save_national_treasury(self, data: dict[str, Any]) -> None:
        fields = []
        values = []
        for key in ["total_silver", "monthly_income", "monthly_expense", "base_tax_rate"]:
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])

        if not fields:
            return

        sql = f"UPDATE national_treasury SET {', '.join(fields)} WHERE id = 1"
        await self._client.execute(sql, *values)

    async def increment_tick(self) -> int:
        await self._client.execute("UPDATE game_tick SET tick = tick + 1 WHERE id = 1")
