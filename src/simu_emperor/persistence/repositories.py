"""
Repository 模式 CRUD 封装（V2）

V2 简化设计：
- GameRepository - 游戏状态和回合指标管理
- AgentRepository - Agent 状态管理
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from aiosqlite import Connection

from simu_emperor.persistence.database import get_connection


logger = logging.getLogger(__name__)


class GameRepository:
    """
    游戏状态 Repository（V2）

    负责：
    - 加载/保存游戏状态
    - 加载/保存回合指标
    - 获取当前回合数
    """

    def __init__(self, conn: Connection | None = None):
        """
        初始化 Repository

        Args:
            conn: 数据库连接，如果为 None 则自动获取
        """
        self.conn = conn

    async def _get_conn(self) -> Connection:
        """获取数据库连接"""
        if self.conn is None:
            return await get_connection()
        return self.conn

    async def load_state(self) -> dict[str, Any]:
        """
        加载游戏状态

        Returns:
            游戏状态字典（JSON 解析后）
        """
        conn = await self._get_conn()
        cursor = await conn.execute("SELECT state_json FROM game_state WHERE id = 1")
        row = await cursor.fetchone()

        if row is None:
            logger.warning("No game state found, returning empty state")
            return {}

        state_json = row[0]
        return json.loads(state_json) if state_json else {}

    async def save_state(self, state: dict[str, Any]) -> None:
        """
        保存游戏状态

        Args:
            state: 游戏状态字典
        """
        conn = await self._get_conn()
        state_json = json.dumps(state, ensure_ascii=False)

        await conn.execute(
            """
            UPDATE game_state
            SET state_json = ?, updated_at = ?
            WHERE id = 1
            """,
            (state_json, datetime.now(timezone.utc).isoformat()),
        )
        await conn.commit()
        logger.debug(f"Game state saved: turn={state.get('turn', 'unknown')}")

    async def load_turn_metrics(self, turn: int) -> dict[str, Any] | None:
        """
        加载回合指标

        Args:
            turn: 回合数

        Returns:
            回合指标字典，如果不存在返回 None
        """
        conn = await self._get_conn()
        cursor = await conn.execute(
            """
            SELECT metrics_json FROM turn_metrics
            WHERE game_id = 'default' AND turn = ?
            """,
            (turn,),
        )
        row = await cursor.fetchone()

        if row is None:
            return None

        metrics_json = row[0]
        return json.loads(metrics_json)

    async def save_turn_metrics(self, turn: int, metrics: dict[str, Any]) -> None:
        """
        保存回合指标

        Args:
            turn: 回合数
            metrics: 回合指标字典
        """
        conn = await self._get_conn()
        metrics_json = json.dumps(metrics, ensure_ascii=False)

        await conn.execute(
            """
            INSERT OR REPLACE INTO turn_metrics (game_id, turn, metrics_json, created_at)
            VALUES ('default', ?, ?, ?)
            """,
            (turn, metrics_json, datetime.now(timezone.utc).isoformat()),
        )
        await conn.commit()
        logger.debug(f"Turn metrics saved: turn={turn}")

    async def get_current_turn(self) -> int:
        """
        获取当前回合数

        Returns:
            当前回合数
        """
        state = await self.load_state()
        return state.get("turn", 0)

    async def increment_turn(self) -> int:
        """
        增加回合数

        Returns:
            新的回合数
        """
        # 加载当前状态
        state = await self.load_state()
        current_turn = state.get("turn", 0)
        new_turn = current_turn + 1

        # 更新 state_json 中的 turn 字段
        state["turn"] = new_turn
        await self.save_state(state)

        # 同时更新数据库的 turn 列（用于索引和查询）
        conn = await self._get_conn()
        await conn.execute("UPDATE game_state SET turn = ? WHERE id = 1", (new_turn,))
        await conn.commit()

        logger.info(f"Turn incremented to {new_turn}")
        return new_turn

    async def update_province_data(self, province_id: str, field_path: str, value: Any) -> None:
        """
        更新省份特定字段

        Args:
            province_id: 省份 ID
            field_path: 字段路径（如 "taxation"）
            value: 新值（可以是具体值或 dict，用于批量更新）
        """
        state = await self.load_state()

        # provinces 是 list，需要找到匹配的省份
        provinces = state.get("provinces", [])
        province_data = None
        province_index = -1

        for idx, p in enumerate(provinces):
            if p.get("province_id") == province_id:
                province_data = p
                province_index = idx
                break

        if province_data is None:
            logger.warning(f"Province {province_id} not found in state")
            return

        # 解析并更新嵌套字段
        parts = field_path.split(".")

        # 导航到目标字段
        current = province_data
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # 更新值
        target_field = parts[-1]

        if isinstance(value, dict):
            # 批量更新：合并 dict
            if target_field not in current:
                current[target_field] = {}
            current[target_field].update(value)
        else:
            # 单个值：直接赋值
            current[target_field] = value

        # 更新 provinces list
        provinces[province_index] = province_data
        state["provinces"] = provinces

        await self.save_state(state)
        logger.debug(f"Updated {province_id}.{field_path} = {value}")


class AgentRepository:
    """
    Agent 状态 Repository（V2）

    负责：
    - 管理 Agent 活跃状态
    - 保存/加载 Agent 配置（soul, data_scope）
    """

    def __init__(self, conn: Connection | None = None):
        """
        初始化 Repository

        Args:
            conn: 数据库连接，如果为 None 则自动获取
        """
        self.conn = conn

    async def _get_conn(self) -> Connection:
        """获取数据库连接"""
        if self.conn is None:
            return await get_connection()
        return self.conn

    async def get_active_agents(self) -> list[str]:
        """
        获取所有活跃的 Agent ID

        Returns:
            Agent ID 列表
        """
        conn = await self._get_conn()
        cursor = await conn.execute("SELECT agent_id FROM agent_state WHERE is_active = 1")
        rows = await cursor.fetchall()

        return [row[0] for row in rows]

    async def set_agent_active(self, agent_id: str, is_active: bool = True) -> None:
        """
        设置 Agent 活跃状态

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
        """
        保存 Agent 配置

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
        """
        加载 Agent 配置

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
