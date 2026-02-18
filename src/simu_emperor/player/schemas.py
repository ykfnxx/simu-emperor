"""API 请求/响应 schema。"""

from pydantic import BaseModel, Field


# ── 请求 schema ──


class ChatRequest(BaseModel):
    """Agent 对话请求。"""

    message: str = Field(description="玩家消息")


class CommandRequest(BaseModel):
    """玩家命令请求。"""

    command_type: str = Field(description="命令类型")
    description: str = Field(description="命令描述")
    target_province_id: str | None = Field(default=None, description="目标省份 ID")
    parameters: dict[str, str] = Field(default_factory=dict, description="命令参数")
    direct: bool = Field(default=False, description="True=皇帝亲政直接生效")


class AdvanceRequest(BaseModel):
    """阶段推进请求（空 body）。"""


# ── 响应 schema ──


class StateResponse(BaseModel):
    """游戏状态摘要响应。"""

    game_id: str
    current_turn: int
    phase: str
    provinces: list[dict]
    imperial_treasury: str
    active_events_count: int


class ChatResponse(BaseModel):
    """Agent 对话响应。"""

    agent_id: str
    response: str


class ReportResponse(BaseModel):
    """Agent 报告响应。"""

    agent_id: str
    turn: int
    markdown: str


class AdvanceResponse(BaseModel):
    """阶段推进响应。"""

    phase: str
    turn: int
    message: str
    reports: dict[str, str] | None = None
    events: list[dict] | None = None


class CommandResponse(BaseModel):
    """命令提交响应。"""

    status: str
    command_type: str
    direct: bool


class ErrorResponse(BaseModel):
    """错误响应。"""

    error: str
    detail: str | None = None
