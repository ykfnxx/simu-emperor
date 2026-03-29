import asyncio
import json
import logging
from typing import Any

from simu_emperor.mq.dealer import MQDealer
from simu_emperor.mq.event import Event


logger = logging.getLogger(__name__)


class AgentWorker:
    def __init__(
        self,
        agent_id: str,
        dealer: MQDealer,
        max_iterations: int = 10,
    ):
        self.agent_id = agent_id
        self.dealer = dealer
        self.max_iterations = max_iterations
        self._tools: dict[str, Any] = {}

    def register_tool(self, name: str, handler: Any) -> None:
        self._tools[name] = handler
        logger.debug(f"Tool registered: {name}")

    async def handle_event(self, event: Event) -> None:
        logger.info(f"Agent {self.agent_id} handling event: {event.event_type}")

        response = await self._process_event_with_llm(event)

        if response:
            await self.dealer.send_event(response)

    async def handle_broadcast(self, event: Event) -> None:
        logger.debug(f"Agent {self.agent_id} received broadcast: {event.event_type}")

        if event.event_type == "TICK_COMPLETED":
            await self._on_tick_completed(event)

    async def _process_event_with_llm(self, event: Event) -> Event | None:
        for iteration in range(self.max_iterations):
            tool_call = await self._get_next_action(event, iteration)

            if not tool_call:
                text_response = await self._get_text_response(event)
                return self._build_response(event, text_response)

            tool_name = tool_call.get("name")
            tool_args = tool_call.get("args", {})

            if tool_name == "finish_loop":
                return self._build_response(event, tool_args.get("message", "Done"))

            result = await self._execute_tool(tool_name, tool_args, event)

            if result:
                logger.debug(f"Tool {tool_name} executed: {result}")

        return self._build_error_response(event, "max_iterations_exceeded")

    async def _get_next_action(self, event: Event, iteration: int) -> dict | None:
        return None

    async def _get_text_response(self, event: Event) -> str:
        return f"Agent {self.agent_id} processed event {event.event_type}"

    async def _execute_tool(self, name: str, args: dict, event: Event) -> Any:
        handler = self._tools.get(name)
        if handler:
            if asyncio.iscoroutinefunction(handler):
                return await handler(args, event)
            return handler(args, event)
        logger.warning(f"Unknown tool: {name}")
        return None

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

    async def _on_tick_completed(self, event: Event) -> None:
        tick = event.payload.get("tick", 0)
        logger.debug(f"Agent {self.agent_id} processing tick {tick}")
