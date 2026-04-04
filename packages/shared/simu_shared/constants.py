"""Shared constants and event type definitions."""


class EventType:
    """Event types used across Server and Agent communication.

    Organized by source domain to make intent clear.
    """

    # Player interaction
    CHAT = "chat"

    # Agent responses
    RESPONSE = "response"
    AGENT_MESSAGE = "agent_message"

    # ReAct loop (tool execution)
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    OBSERVATION = "observation"

    # System / engine events
    TICK_COMPLETED = "tick_completed"
    INCIDENT_CREATED = "incident_created"
    INCIDENT_EXPIRED = "incident_expired"
    SYSTEM = "system"

    # Task session lifecycle
    TASK_CREATED = "task_created"
    TASK_FINISHED = "task_finished"
    TASK_FAILED = "task_failed"
    TASK_TIMEOUT = "task_timeout"

    # Agent lifecycle signals (Server → Agent via SSE)
    SHUTDOWN = "shutdown"
    RELOAD_CONFIG = "reload_config"

    @classmethod
    def all(cls) -> list[str]:
        return [
            v
            for k, v in vars(cls).items()
            if not k.startswith("_") and isinstance(v, str)
        ]

    @classmethod
    def is_valid(cls, event_type: str) -> bool:
        return event_type in cls.all()
