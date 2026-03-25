"""Unit tests for task session Plan-Execute guards in Agent."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from simu_emperor.agents.agent import Agent
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.llm.mock import MockProvider


@pytest.fixture
def mock_event_bus():
    event_bus = MagicMock()
    event_bus.subscribe = MagicMock()
    event_bus.unsubscribe = MagicMock()
    event_bus.send_event = AsyncMock()
    return event_bus


@pytest.fixture
def mock_repository():
    repo = Mock()
    repo.load_nation_data = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def temp_data_dir(tmp_path):
    agent_dir = tmp_path / "data" / "agent" / "test_agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "soul.md").write_text("# Test Soul\nYou are a test agent.", encoding="utf-8")
    (agent_dir / "data_scope.yaml").write_text("query: []\n", encoding="utf-8")
    return agent_dir


@pytest.fixture
def agent(mock_event_bus, temp_data_dir, mock_repository, tmp_path, monkeypatch):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()

    from simu_emperor.config import settings

    monkeypatch.setattr(settings.memory, "memory_dir", memory_dir)

    mock_session = MagicMock()
    mock_session.is_task = False
    mock_session.status = "ACTIVE"
    mock_session.pending_async_replies = 0
    mock_session.parent_id = None
    mock_session.pending_message_ids = []
    mock_session.created_by = "player"

    mock_session_manager = MagicMock()
    mock_session_manager.get_session = AsyncMock(return_value=mock_session)
    mock_session_manager.get_agent_state = AsyncMock(return_value=None)
    mock_session_manager.increment_async_replies = AsyncMock()
    mock_session_manager.save_manifest = AsyncMock()
    mock_session_manager.get_context_manager = AsyncMock()

    mock_tape_writer = MagicMock()
    mock_tape_writer._get_tape_path = MagicMock(return_value=memory_dir / "tape.jsonl")
    mock_tape_writer.write_event = AsyncMock(return_value="event_id")
    mock_tape_metadata_mgr = AsyncMock()

    return Agent(
        agent_id="test_agent",
        event_bus=mock_event_bus,
        llm_provider=MockProvider(response="", tool_calls=[]),
        data_dir=temp_data_dir,
        repository=mock_repository,
        session_manager=mock_session_manager,
        tape_writer=mock_tape_writer,
        tape_metadata_mgr=mock_tape_metadata_mgr,
    )


def _task_session(created_by: str = "agent:test_agent") -> MagicMock:
    session = MagicMock()
    session.is_task = True
    session.status = "ACTIVE"
    session.created_by = created_by
    session.pending_async_replies = 0
    return session


class TestTaskSessionPlanExecuteGuards:
    @pytest.mark.asyncio
    async def test_create_task_session_wrapper_forwards_goal_and_constraints(self, agent):
        event = Event(
            src="player",
            dst=["agent:test_agent"],
            type=EventType.CHAT,
            payload={"message": "test"},
            session_id="session:main",
        )

        agent._task_session_tools.create_task_session = AsyncMock(
            return_value={"success": True, "task_session_id": "task:test_agent:123"}
        )

        result = await agent._wrap_create_task_session(
            {
                "timeout_seconds": 120,
                "description": "核实直隶状态",
                "goal": "向李卫核实直隶近况",
                "constraints": "需在一次询问后结束",
            },
            event,
        )

        data = json.loads(result)
        assert data["success"] is True
        agent._task_session_tools.create_task_session.assert_awaited_once_with(
            timeout_seconds=120,
            description="核实直隶状态",
            current_session_id="session:main",
            goal="向李卫核实直隶近况",
            constraints="需在一次询问后结束",
        )

    @pytest.mark.asyncio
    async def test_finish_task_session_rejected_in_plan_phase(self, agent):
        task = _task_session()
        agent.session_manager.get_session = AsyncMock(return_value=task)
        agent._task_session_tools.finish_task_session = AsyncMock(
            return_value={"success": True, "status": "FINISHED"}
        )
        agent._context_manager = SimpleNamespace(
            session_id="task:test_agent:1",
            events=[
                {
                    "type": EventType.TASK_CREATED,
                    "src": "agent:test_agent",
                    "payload": {"goal": "核实数据"},
                }
            ],
        )

        event = Event(
            src="agent:test_agent",
            dst=["agent:test_agent"],
            type=EventType.TASK_CREATED,
            payload={},
            session_id="task:test_agent:1",
        )

        result = await agent._wrap_finish_task_session({"result": "done"}, event)
        data = json.loads(result)

        assert data["success"] is False
        assert "Plan 阶段" in data["error"]
        agent._task_session_tools.finish_task_session.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_finish_task_session_rejected_before_reply(self, agent):
        task = _task_session()
        agent.session_manager.get_session = AsyncMock(return_value=task)
        agent._task_session_tools.finish_task_session = AsyncMock(
            return_value={"success": True, "status": "FINISHED"}
        )
        agent._context_manager = SimpleNamespace(
            session_id="task:test_agent:1",
            events=[
                {
                    "type": EventType.TASK_CREATED,
                    "src": "agent:test_agent",
                    "payload": {"goal": "核实数据"},
                },
                {
                    "type": EventType.AGENT_MESSAGE,
                    "src": "agent:test_agent",
                    "payload": {"content": "请核实", "await_reply": True},
                },
            ],
        )

        event = Event(
            src="agent:test_agent",
            dst=["agent:test_agent"],
            type=EventType.TASK_CREATED,
            payload={},
            session_id="task:test_agent:1",
        )

        result = await agent._wrap_finish_task_session({"result": "done"}, event)
        data = json.loads(result)

        assert data["success"] is False
        assert "尚未收到有效回复" in data["error"]
        agent._task_session_tools.finish_task_session.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_finish_task_session_allowed_after_reply(self, agent):
        task = _task_session()
        agent.session_manager.get_session = AsyncMock(return_value=task)
        agent._task_session_tools.finish_task_session = AsyncMock(
            return_value={"success": True, "status": "FINISHED"}
        )
        agent._context_manager = SimpleNamespace(
            session_id="task:test_agent:1",
            events=[
                {
                    "type": EventType.TASK_CREATED,
                    "src": "agent:test_agent",
                    "payload": {"goal": "核实数据"},
                },
                {
                    "type": EventType.AGENT_MESSAGE,
                    "src": "agent:test_agent",
                    "payload": {"content": "请核实", "await_reply": True},
                },
                {
                    "type": EventType.AGENT_MESSAGE,
                    "src": "agent:governor_zhili",
                    "payload": {"content": "直隶情况正常"},
                },
            ],
        )

        event = Event(
            src="agent:governor_zhili",
            dst=["agent:test_agent"],
            type=EventType.AGENT_MESSAGE,
            payload={"content": "直隶情况正常"},
            session_id="task:test_agent:1",
        )

        result = await agent._wrap_finish_task_session({"result": "done"}, event)
        data = json.loads(result)

        assert data["success"] is True
        agent._task_session_tools.finish_task_session.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fail_task_session_rejected_in_plan_phase(self, agent):
        task = _task_session()
        agent.session_manager.get_session = AsyncMock(return_value=task)
        agent._task_session_tools.fail_task_session = AsyncMock(
            return_value={"success": True, "status": "FAILED"}
        )
        agent._context_manager = SimpleNamespace(
            session_id="task:test_agent:1",
            events=[{"type": EventType.TASK_CREATED, "src": "agent:test_agent", "payload": {}}],
        )

        event = Event(
            src="agent:test_agent",
            dst=["agent:test_agent"],
            type=EventType.TASK_CREATED,
            payload={},
            session_id="task:test_agent:1",
        )

        result = await agent._wrap_fail_task_session({"reason": "fail"}, event)
        data = json.loads(result)

        assert data["success"] is False
        assert "Plan 阶段" in data["error"]
        agent._task_session_tools.fail_task_session.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_should_process_task_timeout_when_waiting_reply(self, agent):
        task = _task_session()
        agent.session_manager.get_session = AsyncMock(return_value=task)
        agent.session_manager.get_agent_state = AsyncMock(return_value="WAITING_REPLY")

        timeout_event = Event(
            src="system:task_monitor",
            dst=["agent:test_agent"],
            type=EventType.TASK_TIMEOUT,
            payload={"task_session_id": "task:test_agent:1"},
            session_id="task:test_agent:1",
        )

        should_process = await agent._should_process_event(timeout_event)
        assert should_process is True

    @pytest.mark.asyncio
    async def test_task_session_loop_cap_is_8_and_auto_fails(self, agent):
        task = _task_session(created_by="agent:test_agent")
        agent.session_manager.get_session = AsyncMock(return_value=task)
        agent._check_and_restore_agent_state = AsyncMock(return_value=True)
        agent._context_manager = SimpleNamespace(
            _system_prompt="existing prompt",
            add_event_and_maybe_compact=AsyncMock(),
            get_llm_messages=AsyncMock(return_value=[]),
            events=[],
            session_id="task:test_agent:1",
        )
        agent._call_llm = AsyncMock(
            return_value={
                "response_text": "thinking",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "query_national_data",
                            "arguments": '{"field_name":"imperial_treasury"}',
                        },
                    }
                ],
            }
        )
        agent._execute_tools_and_create_observation = AsyncMock(
            return_value={
                "thought": "thinking",
                "actions": [],
                "has_send_message": False,
                "has_finish_loop": False,
                "has_create_task_session": False,
            }
        )
        agent._add_observation_to_tape = AsyncMock()
        agent._task_session_tools.fail_task_session = AsyncMock(
            return_value={"success": True, "status": "FAILED"}
        )

        event = Event(
            src="agent:test_agent",
            dst=["agent:test_agent"],
            type=EventType.TASK_CREATED,
            payload={"task_session_id": "task:test_agent:1"},
            session_id="task:test_agent:1",
        )

        await agent._process_event_with_llm(event, "task:test_agent:1")

        assert agent._call_llm.await_count == 8
        agent._task_session_tools.fail_task_session.assert_awaited_once()
