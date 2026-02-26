"""
事件类型常量

定义所有支持的事件类型。
"""


class EventType:
    """
    事件类型常量

    事件类型分类：
    - 玩家交互：COMMAND, QUERY, CHAT
    - Agent 响应：RESPONSE, AGENT_MESSAGE
    - 游戏动作：ADJUST_TAX, BUILD_IRRIGATION, RECRUIT_TROOPS
    - 系统事件：READY, TURN_RESOLVED, END_TURN
    """

    # 玩家交互事件
    COMMAND = "command"  # 玩家 → Agent (执行命令)
    QUERY = "query"  # 玩家 → Agent (查询信息)
    CHAT = "chat"  # 玩家 → Agent (进入对话)

    # Agent 响应事件
    RESPONSE = "response"  # Agent → 玩家 (叙述性响应)
    AGENT_MESSAGE = "agent_message"  # Agent → Agent (Agent 间通信)

    # 游戏动作事件 (Agent → Calculator)
    ADJUST_TAX = "adjust_tax"  # 调整税率
    BUILD_IRRIGATION = "build_irrigation"  # 建设水利
    RECRUIT_TROOPS = "recruit_troops"  # 招募军队

    # 系统事件
    READY = "ready"  # Agent → Calculator (回合准备完成)
    TURN_RESOLVED = "turn_resolved"  # Calculator → * (回合结算完成)
    END_TURN = "end_turn"  # 玩家 → * (结束回合)

    @classmethod
    def all(cls) -> list[str]:
        """获取所有事件类型"""
        return [
            cls.COMMAND,
            cls.QUERY,
            cls.CHAT,
            cls.RESPONSE,
            cls.AGENT_MESSAGE,
            cls.ADJUST_TAX,
            cls.BUILD_IRRIGATION,
            cls.RECRUIT_TROOPS,
            cls.READY,
            cls.TURN_RESOLVED,
            cls.END_TURN,
        ]

    @classmethod
    def is_valid(cls, event_type: str) -> bool:
        """检查事件类型是否有效"""
        return event_type in cls.all()

    @classmethod
    def player_events(cls) -> list[str]:
        """玩家发起的事件类型"""
        return [cls.COMMAND, cls.QUERY, cls.CHAT, cls.END_TURN]

    @classmethod
    def agent_events(cls) -> list[str]:
        """Agent 发起的事件类型"""
        return [
            cls.RESPONSE,
            cls.AGENT_MESSAGE,
            cls.ADJUST_TAX,
            cls.BUILD_IRRIGATION,
            cls.RECRUIT_TROOPS,
            cls.READY,
        ]

    @classmethod
    def system_events(cls) -> list[str]:
        """系统事件类型"""
        return [cls.TURN_RESOLVED]
