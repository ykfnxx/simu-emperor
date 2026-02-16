"""Repository 模式 CRUD 封装。"""

from datetime import datetime

from aiosqlite import Connection

from simu_emperor.engine.models.base_data import NationalBaseData
from simu_emperor.engine.models.events import AgentEvent, GameEvent, PlayerEvent
from simu_emperor.engine.models.state import GameState
from simu_emperor.persistence.serialization import (
    deserialize_event,
    deserialize_game_state,
    deserialize_national_data,
    serialize_event,
    serialize_game_state,
    serialize_national_data,
)


class GameSaveRepository:
    """游戏存档 Repository。"""

    def __init__(self, conn: Connection):
        self.conn = conn

    async def save(self, state: GameState) -> None:
        """保存游戏状态。

        Args:
            state: 游戏状态对象
        """
        state_json = serialize_game_state(state)
        await self.conn.execute(
            """
            INSERT OR REPLACE INTO game_saves (game_id, turn, state_json)
            VALUES (?, ?, ?)
            """,
            (state.game_id, state.current_turn, state_json),
        )
        await self.conn.commit()

    async def load(self, game_id: str, turn: int | None = None) -> GameState | None:
        """加载游戏状态。

        Args:
            game_id: 游戏 ID
            turn: 回合数，如果为 None 则加载最新存档

        Returns:
            GameState 对象，如果不存在返回 None
        """
        if turn is not None:
            cursor = await self.conn.execute(
                "SELECT state_json FROM game_saves WHERE game_id = ? AND turn = ?",
                (game_id, turn),
            )
        else:
            cursor = await self.conn.execute(
                "SELECT state_json FROM game_saves WHERE game_id = ? ORDER BY turn DESC LIMIT 1",
                (game_id,),
            )

        row = await cursor.fetchone()
        if row is None:
            return None
        return deserialize_game_state(row[0])

    async def list_saves(self, game_id: str) -> list[tuple[int, datetime]]:
        """列出所有存档。

        Args:
            game_id: 游戏 ID

        Returns:
            [(turn, created_at), ...] 列表
        """
        cursor = await self.conn.execute(
            "SELECT turn, created_at FROM game_saves WHERE game_id = ? ORDER BY turn",
            (game_id,),
        )
        rows = await cursor.fetchall()
        return [(row[0], datetime.fromisoformat(row[1])) for row in rows]

    async def delete(self, game_id: str, turn: int) -> None:
        """删除指定存档。

        Args:
            game_id: 游戏 ID
            turn: 回合数
        """
        await self.conn.execute(
            "DELETE FROM game_saves WHERE game_id = ? AND turn = ?",
            (game_id, turn),
        )
        await self.conn.commit()


class EventLogRepository:
    """事件日志 Repository。"""

    def __init__(self, conn: Connection):
        self.conn = conn

    async def log_event(
        self, game_id: str, turn: int, event: GameEvent, action: str
    ) -> None:
        """记录事件日志。

        Args:
            game_id: 游戏 ID
            turn: 回合数
            event: 事件对象
            action: 动作类型（created/applied/expired）
        """
        event_json = serialize_event(event)
        event_type = event.source.value
        await self.conn.execute(
            """
            INSERT INTO event_log (game_id, turn, event_id, event_type, event_json, action)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (game_id, turn, event.event_id, event_type, event_json, action),
        )
        await self.conn.commit()

    async def get_events(
        self, game_id: str, turn: int
    ) -> list[tuple[GameEvent, str]]:
        """获取指定回合的所有事件。

        Args:
            game_id: 游戏 ID
            turn: 回合数

        Returns:
            [(event, action), ...] 列表
        """
        cursor = await self.conn.execute(
            "SELECT event_json, action FROM event_log WHERE game_id = ? AND turn = ? ORDER BY id",
            (game_id, turn),
        )
        rows = await cursor.fetchall()
        return [(deserialize_event(row[0]), row[1]) for row in rows]

    async def get_event_history(
        self, game_id: str, event_id: str
    ) -> list[tuple[str, datetime]]:
        """获取指定事件的历史记录。

        Args:
            game_id: 游戏 ID
            event_id: 事件 ID

        Returns:
            [(action, created_at), ...] 列表
        """
        cursor = await self.conn.execute(
            "SELECT action, created_at FROM event_log WHERE game_id = ? AND event_id = ? ORDER BY id",
            (game_id, event_id),
        )
        rows = await cursor.fetchall()
        return [(row[0], datetime.fromisoformat(row[1])) for row in rows]


class AgentReportRepository:
    """Agent 报告 Repository。"""

    def __init__(self, conn: Connection):
        self.conn = conn

    async def save_report(
        self,
        game_id: str,
        turn: int,
        agent_id: str,
        markdown: str,
        real_data: NationalBaseData,
        report_type: str = "report",
        file_name: str | None = None,
    ) -> None:
        """保存 Agent 报告。

        Args:
            game_id: 游戏 ID
            turn: 回合数
            agent_id: Agent ID
            markdown: 报告内容（Markdown 格式）
            real_data: 真实数据快照
            report_type: 报告类型（report/exec）
            file_name: workspace 文件名（如 003_report.md）
        """
        real_data_json = serialize_national_data(real_data)
        await self.conn.execute(
            """
            INSERT INTO agent_reports (game_id, turn, agent_id, report_type, file_name, report_markdown, real_data_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (game_id, turn, agent_id, report_type, file_name, markdown, real_data_json),
        )
        await self.conn.commit()

    async def get_report(
        self, game_id: str, turn: int, agent_id: str
    ) -> tuple[str, NationalBaseData] | None:
        """获取指定报告。

        Args:
            game_id: 游戏 ID
            turn: 回合数
            agent_id: Agent ID

        Returns:
            (markdown, real_data) 元组，如果不存在返回 None
        """
        cursor = await self.conn.execute(
            "SELECT report_markdown, real_data_json FROM agent_reports WHERE game_id = ? AND turn = ? AND agent_id = ?",
            (game_id, turn, agent_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return (row[0], deserialize_national_data(row[1]))

    async def list_reports(self, game_id: str, turn: int) -> list[tuple[str, str]]:
        """列出指定回合的所有报告。

        Args:
            game_id: 游戏 ID
            turn: 回合数

        Returns:
            [(agent_id, markdown), ...] 列表
        """
        cursor = await self.conn.execute(
            "SELECT agent_id, report_markdown FROM agent_reports WHERE game_id = ? AND turn = ?",
            (game_id, turn),
        )
        rows = await cursor.fetchall()
        return [(row[0], row[1]) for row in rows]

    async def list_all_reports(
        self, game_id: str, max_turn: int | None = None
    ) -> list[tuple[str, int, str, str, str | None]]:
        """列出所有报告（用于 workspace 重建）。

        Args:
            game_id: 游戏 ID
            max_turn: 最大回合数（可选，None 表示不限制）

        Returns:
            [(agent_id, turn, report_type, markdown, file_name), ...] 按 id ASC 排序
        """
        if max_turn is not None:
            cursor = await self.conn.execute(
                "SELECT agent_id, turn, report_type, report_markdown, file_name "
                "FROM agent_reports WHERE game_id = ? AND turn <= ? ORDER BY id",
                (game_id, max_turn),
            )
        else:
            cursor = await self.conn.execute(
                "SELECT agent_id, turn, report_type, report_markdown, file_name "
                "FROM agent_reports WHERE game_id = ? ORDER BY id",
                (game_id,),
            )
        rows = await cursor.fetchall()
        return [(row[0], row[1], row[2], row[3], row[4]) for row in rows]


class ChatHistoryRepository:
    """对话历史 Repository。"""

    def __init__(self, conn: Connection):
        self.conn = conn

    async def add_message(
        self, game_id: str, agent_id: str, role: str, message: str
    ) -> None:
        """添加对话消息。

        Args:
            game_id: 游戏 ID
            agent_id: Agent ID
            role: 角色（player/agent）
            message: 消息内容
        """
        await self.conn.execute(
            """
            INSERT INTO chat_history (game_id, agent_id, role, message)
            VALUES (?, ?, ?, ?)
            """,
            (game_id, agent_id, role, message),
        )
        await self.conn.commit()

    async def get_history(
        self, game_id: str, agent_id: str, limit: int = 50
    ) -> list[tuple[str, str, datetime]]:
        """获取对话历史。

        Args:
            game_id: 游戏 ID
            agent_id: Agent ID
            limit: 最大返回条数

        Returns:
            [(role, message, created_at), ...] 列表（按时间正序）
        """
        cursor = await self.conn.execute(
            """
            SELECT role, message, created_at FROM chat_history
            WHERE game_id = ? AND agent_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (game_id, agent_id, limit),
        )
        rows = await cursor.fetchall()
        # 反转以获得正序
        result = [
            (row[0], row[1], datetime.fromisoformat(row[2])) for row in reversed(rows)
        ]
        return result


class PlayerCommandRepository:
    """玩家命令 Repository。"""

    def __init__(self, conn: Connection):
        self.conn = conn

    async def save_command(
        self,
        game_id: str,
        turn: int,
        command: PlayerEvent,
        result: AgentEvent | None = None,
    ) -> None:
        """保存玩家命令。

        Args:
            game_id: 游戏 ID
            turn: 回合数
            command: 玩家命令事件
            result: 执行结果事件（可选）
        """
        result_event_json = serialize_event(result) if result else None
        fidelity = float(result.fidelity) if result else None

        import json

        parameters_json = json.dumps(command.parameters, ensure_ascii=False)

        await self.conn.execute(
            """
            INSERT INTO player_commands (game_id, turn, command_type, target_province_id, parameters_json, result_event_json, fidelity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game_id,
                turn,
                command.command_type,
                command.target_province_id,
                parameters_json,
                result_event_json,
                fidelity,
            ),
        )
        await self.conn.commit()

    async def get_commands(
        self, game_id: str, turn: int
    ) -> list[tuple[PlayerEvent, AgentEvent | None]]:
        """获取指定回合的所有命令。

        Args:
            game_id: 游戏 ID
            turn: 回合数

        Returns:
            [(command, result), ...] 列表
        """
        cursor = await self.conn.execute(
            "SELECT command_type, target_province_id, parameters_json, result_event_json FROM player_commands WHERE game_id = ? AND turn = ? ORDER BY id",
            (game_id, turn),
        )
        rows = await cursor.fetchall()

        import json

        from simu_emperor.engine.models.events import EventSource

        results: list[tuple[PlayerEvent, AgentEvent | None]] = []
        for row in rows:
            command_type, target_province_id, parameters_json, result_event_json = row

            # 重建 PlayerEvent
            parameters = json.loads(parameters_json) if parameters_json else {}
            command = PlayerEvent(
                source=EventSource.PLAYER,
                command_type=command_type,
                target_province_id=target_province_id,
                parameters=parameters,
                turn_created=turn,
                description=f"Command: {command_type}",
            )

            # 重建 AgentEvent（如果有）
            result = None
            if result_event_json:
                event = deserialize_event(result_event_json)
                if isinstance(event, AgentEvent):
                    result = event

            results.append((command, result))

        return results
