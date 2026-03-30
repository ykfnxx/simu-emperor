"""
事件类型常量

定义所有支持的事件类型。
"""


class EventType:
    """
    事件类型常量

    事件类型分类：
    - 玩家交互：CHAT
    - Agent 响应：RESPONSE, AGENT_MESSAGE
    - 记忆系统：USER_QUERY, ASSISTANT_RESPONSE, TOOL_RESULT
    - 系统事件：SESSION_STATE, TICK_COMPLETED, INCIDENT_CREATED, INCIDENT_EXPIRED
    - Task 生命周期：TASK_CREATED, TASK_FINISHED, TASK_FAILED, TASK_TIMEOUT
    - 工具执行：OBSERVATION
    """

    # 玩家交互事件
    CHAT = "chat"  # 玩家 → Agent (进入对话)

    # Agent 响应事件
    RESPONSE = "response"  # Agent → 玩家 (叙述性响应)
    AGENT_MESSAGE = "agent_message"  # Agent → Agent (Agent 间通信)

    # 工具执行事件（ReAct 模式）
    OBSERVATION = "observation"  # 工具执行观察结果

    # 记忆系统事件（V3 Memory）
    USER_QUERY = "user_query"  # 用户查询（写入 tape）
    ASSISTANT_RESPONSE = "assistant_response"  # LLM 响应（写入 tape）
    TOOL_CALL = "tool_call"  # 工具调用（写入 tape）
    TOOL_RESULT = "tool_result"  # 工具执行结果（写入 tape）

    # 记忆注入事件
    MEMORY_INJECTED = "memory_injected"  # 记忆注入完成

    # 系统事件
    SESSION_STATE = "session_state"  # 系统 → 客户端 (session状态同步)
    TICK_COMPLETED = "tick_completed"  # TickCoordinator → * (tick 完成，V4 新增)
    INCIDENT_CREATED = "incident_created"  # Agent → Engine (创建 Incident，V4 新增)
    INCIDENT_EXPIRED = "incident_expired"  # Engine → * (Incident 过期，V4 新增)

    # Task Session 生命周期事件
    TASK_CREATED = "task_created"  # Agent 创建 Task Session
    TASK_FINISHED = "task_finished"  # Agent 完成 Task
    TASK_FAILED = "task_failed"  # Agent 标记 Task 失败
    TASK_TIMEOUT = "task_timeout"  # TaskMonitor 检测到超时

    @classmethod
    def all(cls) -> list[str]:
        """获取所有事件类型"""
        return [
            cls.CHAT,
            cls.RESPONSE,
            cls.AGENT_MESSAGE,
            cls.OBSERVATION,
            cls.USER_QUERY,
            cls.ASSISTANT_RESPONSE,
            cls.TOOL_CALL,
            cls.TOOL_RESULT,
            cls.SESSION_STATE,
            cls.TICK_COMPLETED,
            cls.INCIDENT_CREATED,
            cls.INCIDENT_EXPIRED,
            cls.TASK_CREATED,
            cls.TASK_FINISHED,
            cls.TASK_FAILED,
            cls.TASK_TIMEOUT,
            cls.MEMORY_INJECTED,
        ]

    @classmethod
    def is_valid(cls, event_type: str) -> bool:
        """检查事件类型是否有效"""
        return event_type in cls.all()

    @classmethod
    def player_events(cls) -> list[str]:
        """玩家发起的事件类型"""
        return [cls.CHAT]

    @classmethod
    def agent_events(cls) -> list[str]:
        """Agent 发起的事件类型"""
        return [
            cls.RESPONSE,
            cls.AGENT_MESSAGE,
            cls.OBSERVATION,
            cls.TASK_CREATED,
            cls.TASK_FINISHED,
            cls.TASK_FAILED,
        ]

    @classmethod
    def system_events(cls) -> list[str]:
        """系统事件类型"""
        return [cls.TASK_TIMEOUT, cls.SESSION_STATE, cls.TICK_COMPLETED]
