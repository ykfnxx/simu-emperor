"""ReActLoop - extracted from Agent for testable iteration control."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

from simu_emperor.agents.tools.registry import ToolRegistry, ToolResult
from simu_emperor.agents.utils import write_llm_log
from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType

if TYPE_CHECKING:
    from simu_emperor.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class ReActLoop:
    """ReAct loop — LLM calls, tool execution, iteration control.

    Extracted from Agent to create a testable unit. Holds a reference
    back to the agent for the few callbacks that remain agent-specific.
    """

    def __init__(
        self,
        agent_id: str,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        event_bus: EventBus,
        get_context_manager: Callable[[], Any],
        tape_writer: Any,
        agent_logger: logging.Logger,
        llm_log_path: Any,
        call_function: Callable,
        get_root_event_type: Callable,
        get_system_prompt: Callable,
        check_and_restore_state: Callable,
    ) -> None:
        self.agent_id = agent_id
        self.llm_provider = llm_provider
        self._tool_registry = tool_registry
        self.event_bus = event_bus
        self._get_context_manager = get_context_manager
        self._tape_writer = tape_writer
        self._agent_logger = agent_logger
        self._llm_log_path = llm_log_path
        self._call_function = call_function
        self._get_root_event_type = get_root_event_type
        self._get_system_prompt = get_system_prompt
        self._check_and_restore_state = check_and_restore_state

    @property
    def _context_manager(self) -> Any:
        return self._get_context_manager()

    async def run(self, event: Event, session_id: str) -> None:
        if not await self._check_and_restore_state(event, session_id):
            return

        turn_start_time = datetime.now(timezone.utc).isoformat()

        ctx = self._context_manager
        if ctx and ctx._system_prompt is None:
            root_event_type = await self._get_root_event_type(event, session_id)
            ctx._system_prompt = self._get_system_prompt(root_event_type)

        await ctx.add_event_and_maybe_compact(event)

        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            logger.info(
                f"🔄 [Agent:{self.agent_id}:{session_id}] Iteration {iteration}: Calling LLM..."
            )

            messages = await ctx.get_llm_messages()
            result = await self._call_llm(event, session_id, iteration, messages)

            tool_calls = result.get("tool_calls", [])
            response_text = result.get("response_text", "").strip()

            logger.info(
                f"🔧 [Agent:{self.agent_id}:{session_id}] Iteration {iteration}: LLM returned {len(tool_calls)} tool calls"
            )
            logger.info(
                f"💬 [Agent:{self.agent_id}:{session_id}] LLM response text: {response_text[:200] if response_text else '(empty)'}"
            )

            if not tool_calls:
                await self._handle_no_tool_calls(event, session_id, response_text)
                break

            observation = await self._execute_tools_and_create_observation(
                event,
                session_id,
                iteration,
                tool_calls,
                response_text,
                turn_start_time,
            )

            await self._add_observation_to_tape(event, session_id, observation)

            if observation.get("has_create_task_session"):
                logger.info(
                    f"📋 [Agent:{self.agent_id}:{session_id}] create_task_session called, ending loop"
                )
                break

            if observation.get("has_finish_loop"):
                logger.info(
                    f"🔄 [Agent:{self.agent_id}:{session_id}] finish_loop called, ending loop"
                )
                break

            if observation.get("has_send_message"):
                logger.info(
                    f"✅ [Agent:{self.agent_id}:{session_id}] send_message called, ending loop"
                )
                break

            if observation.get("has_finish_task_session"):
                logger.info(
                    f"🏁 [Agent:{self.agent_id}:{session_id}] finish_task_session/fail_task_session called, ending loop"
                )
                break

            logger.info(
                f"✅ [Agent:{self.agent_id}:{session_id}] Tool calls executed, requesting final response..."
            )

        if iteration >= max_iterations:
            logger.warning(
                f"⚠️  [Agent:{self.agent_id}:{session_id}] Reached max iterations ({max_iterations})"
            )

    async def _call_llm(
        self, event: Event, session_id: str, iteration: int, messages: list[dict]
    ) -> dict:
        start_time = datetime.now(timezone.utc)

        logger.debug(f"🔍 [Agent:{self.agent_id}:{session_id}] Messages being sent to LLM:")
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content_preview = str(msg.get("content", ""))[:100]
            msg_tool_calls = msg.get("tool_calls")
            if msg_tool_calls:
                logger.debug(f"  [{i}] role={role}, tool_calls={msg_tool_calls}")
            else:
                logger.debug(f"  [{i}] role={role}, content={content_preview}")

        functions = self._tool_registry.to_function_definitions()
        result = await self.llm_provider.call_with_functions(
            functions=functions,
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
            task_type="agent_response",
        )

        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        self._log_llm_call(
            event_id=event.event_id,
            session_id=event.session_id,
            iteration=iteration,
            request={"messages": messages, "functions": functions},
            response=result,
            duration_ms=duration_ms,
        )

        return result

    async def _execute_tools_and_create_observation(
        self,
        event: Event,
        session_id: str,
        iteration: int,
        tool_calls: list,
        response_text: str,
        turn_start_time: str,
    ) -> dict:
        observation: dict[str, Any] = {
            "thought": response_text,
            "actions": [],
            "has_send_message": False,
            "has_finish_loop": False,
            "has_create_task_session": False,
            "has_finish_task_session": False,
        }

        for idx, tool_call in enumerate(tool_calls, 1):
            function_name = tool_call["function"]["name"]
            function_args = json.loads(tool_call["function"]["arguments"])

            logger.info(
                f"⚙️  [Agent:{self.agent_id}:{session_id}] [Iter {iteration}, {idx}/{len(tool_calls)}] Calling: {function_name}"
            )

            result = await self._call_function(function_name, function_args, event)

            # Normalize to ToolResult
            if isinstance(result, ToolResult):
                tool_result = result
            elif isinstance(result, tuple):
                result_str, result_event = result
                tool_result = ToolResult(
                    output=result_str,
                    success=result_str.startswith("✅") or result_str.startswith("等待"),
                    side_effect=result_event,
                )
            else:
                tool_result = ToolResult(output=str(result))

            observation["actions"].append({"tool": function_name, "result": tool_result.output})

            if tool_result.side_effect:
                await self._context_manager.add_event_and_maybe_compact(tool_result.side_effect)

            if tool_result.ends_loop:
                observation["has_finish_loop"] = True

            if tool_result.creates_task:
                observation["has_create_task_session"] = True

            if tool_result.closes_task:
                observation["has_finish_task_session"] = True

            if function_name == "send_message" and tool_result.success:
                observation["has_send_message"] = True

            if function_name == "finish_loop" and not tool_result.success:
                logger.warning(
                    f"⚠️ [Agent:{self.agent_id}:{session_id}] finish_loop failed: {tool_result.output}"
                )

            if function_name == "create_task_session" and not tool_result.creates_task:
                try:
                    result_data = json.loads(tool_result.output)
                    if result_data.get("success") is True:
                        observation["has_create_task_session"] = True
                    else:
                        logger.warning(
                            f"⚠️ [Agent:{self.agent_id}:{session_id}] create_task_session failed: {tool_result.output}"
                        )
                except json.JSONDecodeError:
                    logger.warning(
                        f"⚠️ [Agent:{self.agent_id}:{session_id}] create_task_session invalid JSON: {tool_result.output}"
                    )

        return observation

    async def _add_observation_to_tape(
        self, event: Event, session_id: str, observation: dict
    ) -> None:
        observation_event = Event(
            src=f"agent:{self.agent_id}",
            dst=[f"benchmark:{session_id}"],
            type=EventType.OBSERVATION,
            payload=observation,
            session_id=event.session_id,
            parent_event_id=event.event_id,
            root_event_id=event.root_event_id,
        )
        await self._context_manager.add_event_and_maybe_compact(observation_event)
        await self.event_bus.send_event(observation_event)

    async def _handle_no_tool_calls(
        self, event: Event, session_id: str, response_text: str
    ) -> None:
        logger.info(f"✅ [Agent:{self.agent_id}:{session_id}] No more tool calls, ending loop")

        final_message = response_text if response_text else "抱歉，我暂时无法理解您的请求。"

        # Determine reply target based on event context
        if event.type == EventType.AGENT_MESSAGE:
            reply_target = [event.src]
        else:
            reply_target = ["player"]

        message_event = Event(
            src=f"agent:{self.agent_id}",
            dst=reply_target,
            type=EventType.AGENT_MESSAGE,
            payload={"content": final_message, "await_reply": False},
            session_id=event.session_id,
            parent_event_id=event.event_id,
            root_event_id=event.root_event_id,
        )
        await self.event_bus.send_event(message_event)

        if self._context_manager:
            await self._context_manager.add_event_and_maybe_compact(message_event)

        logger.info(
            f"💬 [Agent:{self.agent_id}:{session_id}] Sending final response: {final_message[:50]}..."
        )

    def _log_llm_call(
        self,
        event_id: str,
        session_id: str,
        iteration: int,
        request: dict,
        response: dict,
        duration_ms: float,
    ) -> None:
        write_llm_log(
            self._llm_log_path,
            event_id=event_id,
            session_id=session_id,
            iteration=iteration,
            model=getattr(self.llm_provider, "model", "unknown"),
            request=request,
            response=response,
            duration_ms=duration_ms,
        )
