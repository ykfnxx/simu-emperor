import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from simu_emperor.mq.dealer import MQDealer
from simu_emperor.mq.event import Event
from simu_emperor.mq.publisher import MQPublisher
from simu_emperor.persistence.client import SeekDBClient

if TYPE_CHECKING:
    from simu_emperor.agent.context_manager import ContextManager
    from simu_emperor.agent.tool_registry import ToolRegistry
    from simu_emperor.agent.permissions import PermissionChecker


logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    provider: str = "mock"
    model: str = ""
    api_key: str = ""
    context_window: int = 128000
    temperature: float = 0.7


@dataclass
class AgentConfig:
    agent_id: str
    role_name: str
    soul_text: str = ""
    skills: list[str] = field(default_factory=list)
    permissions: dict[str, Any] = field(default_factory=dict)
    llm: LLMConfig = field(default_factory=LLMConfig)
    max_iterations: int = 10

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentConfig":
        llm_data = data.get("llm", {})
        llm = LLMConfig(
            provider=llm_data.get("provider", "mock"),
            model=llm_data.get("model", ""),
            api_key=llm_data.get("api_key", ""),
            context_window=llm_data.get("context_window", 128000),
            temperature=llm_data.get("temperature", 0.7),
        )
        return cls(
            agent_id=data.get("agent_id", ""),
            role_name=data.get("role_name", ""),
            soul_text=data.get("soul_text", ""),
            skills=data.get("skills", []),
            permissions=data.get("permissions", {}),
            llm=llm,
            max_iterations=data.get("max_iterations", 10),
        )


class Agent:
    def __init__(
        self,
        agent_id: str,
        config: AgentConfig,
        seekdb: SeekDBClient,
        mq_dealer: MQDealer,
        mq_publisher: MQPublisher,
    ):
        self.agent_id = agent_id
        self.config = config

        self._seekdb = seekdb
        self._mq_dealer = mq_dealer
        self._mq_publisher = mq_publisher

        self._tool_registry: "ToolRegistry | None" = None
        self._permissions: "PermissionChecker | None" = None
        self._context_managers: dict[str, "ContextManager"] = {}

        self._current_tick: int = 0

    def set_tool_registry(self, registry: "ToolRegistry") -> None:
        self._tool_registry = registry

    def set_permissions(self, permissions: "PermissionChecker") -> None:
        self._permissions = permissions

    async def handle_event(self, event: Event) -> Event:
        logger.info(f"Agent {self.agent_id} handling event: {event.event_type}")

        ctx = await self._get_context_manager(event.session_id)
        await ctx.add_event(event)

        return await self._process_event_with_llm(event, ctx)

    async def handle_broadcast(self, event: Event) -> None:
        logger.debug(f"Agent {self.agent_id} received broadcast: {event.event_type}")

        if event.event_type == "TICK_COMPLETED":
            self._current_tick = event.payload.get("tick", 0)

    async def _get_context_manager(self, session_id: str) -> "ContextManager":
        if session_id not in self._context_managers:
            from simu_emperor.agent.context_manager import ContextManager

            ctx = ContextManager(
                session_id=session_id,
                agent_id=self.agent_id,
                seekdb=self._seekdb,
            )
            await ctx.load()
            self._context_managers[session_id] = ctx

        return self._context_managers[session_id]

    async def _process_event_with_llm(self, event: Event, ctx: "ContextManager") -> Event:
        if not self._tool_registry:
            return self._build_error_response(event, "tool_registry_not_initialized")

        max_iterations = self.config.max_iterations

        for iteration in range(max_iterations):
            messages = await ctx.get_llm_messages()

            response = await self._call_llm(messages)

            if response.get("tool_calls"):
                for tool_call in response["tool_calls"]:
                    tool_name = tool_call.get("name", "")
                    tool_args = tool_call.get("args", {})

                    result = await self._tool_registry.dispatch(tool_name, tool_args, event, ctx)

                    await ctx.add_observation(tool_name, result)

                    if tool_name == "finish_loop":
                        return self._build_response(event, result)

                continue

            return self._build_response(event, response.get("text", ""))

        return self._build_error_response(event, "max_iterations_exceeded")

    async def _call_llm(self, messages: list[dict]) -> dict[str, Any]:
        if self.config.llm.provider == "mock":
            return {"text": f"Agent {self.agent_id} processed request", "tool_calls": None}

        return {"text": "", "tool_calls": None}

    def _build_response(self, event: Event, message: str) -> Event:
        return Event(
            event_id="",
            event_type="AGENT_MESSAGE",
            src=f"agent:{self.agent_id}",
            dst=[event.src],
            session_id=event.session_id,
            payload={"message": message},
            timestamp="",
        )

    def _build_error_response(self, event: Event, error: str) -> Event:
        return Event(
            event_id="",
            event_type="TASK_FAILED",
            src=f"agent:{self.agent_id}",
            dst=[event.src],
            session_id=event.session_id,
            payload={"error": error},
            timestamp="",
        )

    async def _check_task_timeouts(self) -> None:
        expired = await self._seekdb.fetch_all(
            """
            SELECT * FROM task_sessions 
            WHERE creator_id = ? AND status = 'pending'
            AND julianday('now') - julianday(created_at) * 86400 > timeout_seconds
            """,
            self.agent_id,
        )

        for task in expired or []:
            logger.warning(f"Task {task['task_id']} expired")
