"""Repository 模式 CRUD 封装 (V4).

V4 数据模型：
- GameRepository - NationData 持久化
- AgentRepository - Agent 状态管理
"""

import logging
from datetime import datetime, timezone
from typing import Any

from aiosqlite import Connection

from simu_emperor.persistence.database import get_connection
from simu_emperor.persistence.serialization import (
    serialize_nation_data,
    deserialize_nation_data,
)
from simu_emperor.engine.models.base_data import NationData


logger = logging.getLogger(__name__)


class GameRepository:
    """游戏状态 Repository (V4).

    负责：
    - 加载/保存 NationData
    - 获取当前 tick 数
    """

    def __init__(self, conn: Connection | None = None):
        """初始化 Repository.

        Args:
            conn: 数据库连接，如果为 None 则自动获取
        """
        self.conn = conn

    async def _get_conn(self) -> Connection:
        """获取数据库连接."""
        if self.conn is None:
            return await get_connection()
        return self.conn

    async def load_nation_data(self) -> NationData:
        """加载游戏状态.

        Returns:
            NationData 对象，如果不存在返回默认空状态 (turn=0)
        """
        conn = await self._get_conn()
        cursor = await conn.execute("SELECT state_json FROM game_state WHERE id = 1")
        row = await cursor.fetchone()

        if row is None or not row[0]:
            logger.warning("No game state found, returning default state")
            return NationData(turn=0)

        state_json = row[0]
        try:
            return deserialize_nation_data(state_json)
        except Exception as e:
            logger.error(f"Failed to deserialize game state: {e}")
            return NationData(turn=0)

    async def save_nation_data(self, nation: NationData) -> None:
        """保存游戏状态.

        Args:
            nation: NationData 对象
        """
        conn = await self._get_conn()
        state_json = serialize_nation_data(nation)

        await conn.execute(
            """
            INSERT INTO game_state (id, state_json, created_at, updated_at)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
            """,
            (
                state_json,
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await conn.commit()
        logger.debug(f"Game state saved: tick={nation.turn}")

    async def get_current_tick(self) -> int:
        """获取当前 tick 数.

        Returns:
            当前 tick 数
        """
        state = await self.load_nation_data()
        return state.turn

    async def initialize_default_state(self) -> None:
        """初始化默认游戏状态 (如果不存在)."""
        conn = await self._get_conn()
        cursor = await conn.execute("SELECT state_json FROM game_state WHERE id = 1")
        row = await cursor.fetchone()

        if row is None or not row[0]:
            # 创建初始状态
            from simu_emperor.persistence.serialization import serialize_nation_data

            default_state = NationData(turn=0)
            state_json = serialize_nation_data(default_state)

            await conn.execute(
                """
                INSERT INTO game_state (id, state_json, created_at, updated_at)
                VALUES (1, ?, ?, ?)
                """,
                (
                    state_json,
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            await conn.commit()
            logger.info("Initialized default game state")

    # 保留旧方法以兼容 (标记为 deprecated)
    async def load_state(self) -> dict[str, Any]:
        """[已废弃] 使用 load_nation_data 替代."""
        nation = await self.load_nation_data()
        from dataclasses import asdict

        return asdict(nation)

    async def save_state(self, state: dict[str, Any]) -> None:
        """[已废弃] 使用 save_nation_data 替代."""
        # 尝试从字典重建 NationData
        from simu_emperor.engine.models.base_data import ProvinceData
        from decimal import Decimal

        provinces = {}
        for pid, p_dict in state.get("provinces", {}).items():
            if isinstance(p_dict, dict):
                # 转换字符串值为 Decimal
                provinces[pid] = ProvinceData(
                    province_id=p_dict.get("province_id", pid),
                    name=p_dict.get("name", ""),
                    production_value=Decimal(str(p_dict.get("production_value", "0"))),
                    population=Decimal(str(p_dict.get("population", "0"))),
                    fixed_expenditure=Decimal(str(p_dict.get("fixed_expenditure", "0"))),
                    stockpile=Decimal(str(p_dict.get("stockpile", "0"))),
                    base_production_growth=Decimal(
                        str(p_dict.get("base_production_growth", "0.01"))
                    ),
                    base_population_growth=Decimal(
                        str(p_dict.get("base_population_growth", "0.005"))
                    ),
                    tax_modifier=Decimal(str(p_dict.get("tax_modifier", "0.0"))),
                )

        nation = NationData(
            turn=state.get("turn", 0),
            base_tax_rate=Decimal(str(state.get("base_tax_rate", "0.10"))),
            tribute_rate=Decimal(str(state.get("tribute_rate", "0.8"))),
            fixed_expenditure=Decimal(str(state.get("fixed_expenditure", "0"))),
            imperial_treasury=Decimal(str(state.get("imperial_treasury", "0"))),
            provinces=provinces,
        )
        await self.save_nation_data(nation)


class AgentRepository:
    """Agent 状态 Repository (V4).

    负责：
    - 管理 Agent 活跃状态
    - 保存/加载 Agent 配置 (soul, data_scope)
    """

    def __init__(self, conn: Connection | None = None):
        """初始化 Repository.

        Args:
            conn: 数据库连接，如果为 None 则自动获取
        """
        self.conn = conn

    async def _get_conn(self) -> Connection:
        """获取数据库连接."""
        if self.conn is None:
            return await get_connection()
        return self.conn

    async def get_active_agents(self) -> list[str]:
        """获取所有活跃的 Agent ID.

        Returns:
            Agent ID 列表
        """
        conn = await self._get_conn()
        cursor = await conn.execute("SELECT agent_id FROM agent_state WHERE is_active = 1")
        rows = await cursor.fetchall()

        return [row[0] for row in rows]

    async def set_agent_active(self, agent_id: str, is_active: bool = True) -> None:
        """设置 Agent 活跃状态.

        Args:
            agent_id: Agent ID
            is_active: 是否活跃
        """
        conn = await self._get_conn()
        await conn.execute(
            """
            INSERT OR REPLACE INTO agent_state (agent_id, is_active, updated_at)
            VALUES (?, ?, ?)
            """,
            (agent_id, 1 if is_active else 0, datetime.now(timezone.utc).isoformat()),
        )
        await conn.commit()
        logger.info(f"Agent {agent_id} active status set to {is_active}")

    async def save_agent_config(
        self,
        agent_id: str,
        soul_markdown: str | None = None,
        data_scope_yaml: str | None = None,
    ) -> None:
        """保存 Agent 配置.

        Args:
            agent_id: Agent ID
            soul_markdown: Soul 内容
            data_scope_yaml: Data Scope 内容
        """
        conn = await self._get_conn()
        await conn.execute(
            """
            INSERT OR REPLACE INTO agent_state (agent_id, soul_markdown, data_scope_yaml, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                agent_id,
                soul_markdown,
                data_scope_yaml,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await conn.commit()
        logger.debug(f"Agent config saved: {agent_id}")

    async def load_agent_config(self, agent_id: str) -> dict[str, str | None]:
        """加载 Agent 配置.

        Args:
            agent_id: Agent ID

        Returns:
            配置字典，包含 soul_markdown 和 data_scope_yaml
        """
        conn = await self._get_conn()
        cursor = await conn.execute(
            "SELECT soul_markdown, data_scope_yaml FROM agent_state WHERE agent_id = ?",
            (agent_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            return {"soul_markdown": None, "data_scope_yaml": None}

        return {
            "soul_markdown": row[0],
            "data_scope_yaml": row[1],
        }
