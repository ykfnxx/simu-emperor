"""
事件类型常量

定义所有支持的事件类型。
"""


class EventType:
    """
    事件类型常量

    事件类型分类：
    - 玩家交互：COMMAND, CHAT
    - Agent 响应：RESPONSE, AGENT_MESSAGE
    - 记忆系统：USER_QUERY, ASSISTANT_RESPONSE, TOOL_RESULT
    - 游戏动作：ADJUST_TAX, BUILD_IRRIGATION, RECRUIT_TROOPS
    - 系统事件：READY, TURN_RESOLVED, END_TURN
    """

    # 玩家交互事件
    COMMAND = "command"  # 玩家 → Agent (执行命令)
    CHAT = "chat"  # 玩家 → Agent (进入对话)

    # Agent 响应事件
    RESPONSE = "response"  # Agent → 玩家 (叙述性响应)
    AGENT_MESSAGE = "agent_message"  # Agent → Agent (Agent 间通信)

    # 记忆系统事件（V3 Memory）
    USER_QUERY = "user_query"  # 用户查询（写入 tape）
    ASSISTANT_RESPONSE = "assistant_response"  # LLM 响应（写入 tape）
    TOOL_CALL = "tool_call"  # 工具调用（写入 tape）
    TOOL_RESULT = "tool_result"  # 工具执行结果（写入 tape）

    # 游戏动作事件 (Agent → Calculator)
    ALLOCATE_FUNDS = "allocate_funds"  # 拨款（从国库到省库）
    ADJUST_TAX = "adjust_tax"  # 调整税率
    BUILD_IRRIGATION = "build_irrigation"  # 建设水利
    RECRUIT_TROOPS = "recruit_troops"  # 招募军队

    # 系统事件
    READY = "ready"  # Agent → Calculator (回合准备完成)
    TURN_RESOLVED = "turn_resolved"  # Calculator → * (回合结算完成)
    END_TURN = "end_turn"  # 玩家 → * (结束回合)
    SESSION_STATE = "session_state"  # 系统 → 客户端 (session状态同步)

    # Task Session 生命周期事件
    TASK_CREATED = "task_created"  # Agent 创建 Task Session
    TASK_FINISHED = "task_finished"  # Agent 完成 Task
    TASK_FAILED = "task_failed"  # Agent 标记 Task 失败
    TASK_TIMEOUT = "task_timeout"  # TaskMonitor 检测到超时

    # Task Session 事件 (V4)
    TASK_CREATED = "task_created"  # Agent 创建 Task Session
    TASK_FINISHED = "task_finished"  # Agent 完成 Task
    TASK_FAILED = "task_failed"  # Agent 标记 Task 失败
    TASK_TIMEOUT = "task_timeout"  # TaskMonitor 检测到超时

    @classmethod
    def all(cls) -> list[str]:
        """获取所有事件类型"""
        return [
            cls.COMMAND,
            cls.CHAT,
            cls.RESPONSE,
            cls.AGENT_MESSAGE,
            cls.USER_QUERY,
            cls.ASSISTANT_RESPONSE,
            cls.TOOL_CALL,
            cls.TOOL_RESULT,
            cls.ALLOCATE_FUNDS,
            cls.ADJUST_TAX,
            cls.BUILD_IRRIGATION,
            cls.RECRUIT_TROOPS,
            cls.READY,
            cls.TURN_RESOLVED,
            cls.END_TURN,
            cls.SESSION_STATE,
            cls.TASK_CREATED,
            cls.TASK_FINISHED,
            cls.TASK_FAILED,
            cls.TASK_TIMEOUT,
        ]

    @classmethod
    def is_valid(cls, event_type: str) -> bool:
        """检查事件类型是否有效"""
        return event_type in cls.all()

    @classmethod
    def player_events(cls) -> list[str]:
        """玩家发起的事件类型"""
        return [cls.COMMAND, cls.CHAT, cls.END_TURN]

    @classmethod
    def agent_events(cls) -> list[str]:
        """Agent 发起的事件类型"""
        return [
            cls.RESPONSE,
            cls.AGENT_MESSAGE,
            cls.ALLOCATE_FUNDS,
            cls.ADJUST_TAX,
            cls.BUILD_IRRIGATION,
            cls.RECRUIT_TROOPS,
            cls.READY,
            cls.TASK_CREATED,
            cls.TASK_FINISHED,
            cls.TASK_FAILED,
        ]

    @classmethod
    def system_events(cls) -> list[str]:
        """系统事件类型"""
        return [cls.TURN_RESOLVED, cls.TASK_TIMEOUT, cls.SESSION_STATE]
