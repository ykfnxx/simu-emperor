"""持久化层：数据库连接、序列化、Repository。"""

from simu_emperor.persistence.database import (
    close_database,
    get_connection,
    init_database,
)
from simu_emperor.persistence.repositories import (
    AgentReportRepository,
    ChatHistoryRepository,
    EventLogRepository,
    GameSaveRepository,
    PlayerCommandRepository,
)
from simu_emperor.persistence.serialization import (
    deserialize_event,
    deserialize_game_state,
    deserialize_national_data,
    serialize_event,
    serialize_game_state,
    serialize_national_data,
)

__all__ = [
    # Database
    "init_database",
    "get_connection",
    "close_database",
    # Serialization
    "serialize_game_state",
    "deserialize_game_state",
    "serialize_event",
    "deserialize_event",
    "serialize_national_data",
    "deserialize_national_data",
    # Repositories
    "GameSaveRepository",
    "EventLogRepository",
    "AgentReportRepository",
    "ChatHistoryRepository",
    "PlayerCommandRepository",
]
