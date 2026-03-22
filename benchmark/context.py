"""BenchmarkContext — self-contained service container for benchmark evaluation.

Wraps ApplicationServices lifecycle so evaluators can send messages to agents
and interact with the memory system without an HTTP server.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from benchmark.config import BenchmarkConfig

logger = logging.getLogger(__name__)


class BenchmarkContext:
    """Service container that manages a full ApplicationServices lifecycle for benchmarks."""

    def __init__(self) -> None:
        self.services: Any = None  # ApplicationServices
        self._temp_dir: str = ""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self, config: BenchmarkConfig) -> None:
        """Bootstrap an isolated game environment in a temp directory."""
        from simu_emperor.application.services import ApplicationServices
        from simu_emperor.config import GameConfig, LLMConfig, MemoryConfig

        # 1. Create temp directory and copy necessary data files
        self._temp_dir = tempfile.mkdtemp(prefix="benchmark_")
        data_dir = Path(self._temp_dir) / "data"
        data_dir.mkdir()

        project_root = Path(__file__).resolve().parents[1]
        src_data = project_root / "data"

        # Copy default agents (only governor_zhili for benchmark)
        src_agents = src_data / "default_agents" / "governor_zhili"
        dst_agents = data_dir / "default_agents" / "governor_zhili"
        if src_agents.exists():
            shutil.copytree(src_agents, dst_agents)

        # Copy skills
        src_skills = src_data / "skills"
        dst_skills = data_dir / "skills"
        if src_skills.exists():
            shutil.copytree(src_skills, dst_skills)

        # Copy initial state
        src_state = src_data / "initial_state_v4.json"
        if src_state.exists():
            shutil.copy2(src_state, data_dir / "initial_state_v4.json")

        # 2. Build GameConfig
        log_dir = Path(self._temp_dir) / "logs"
        log_dir.mkdir()

        llm_kwargs: dict[str, Any] = {}
        if config.provider:
            llm_kwargs["provider"] = config.provider
        if config.model:
            llm_kwargs["model"] = config.model
        if config.api_key:
            llm_kwargs["api_key"] = config.api_key
        if config.base_url:
            llm_kwargs["api_base"] = config.base_url

        game_config = GameConfig(
            db_path=":memory:",
            data_dir=data_dir,
            log_dir=log_dir,
            llm=LLMConfig(**llm_kwargs),
            memory=MemoryConfig(memory_dir=str(data_dir / "memory")),
        )

        # 3. Create services (only governor_zhili, no tick coordinator)
        self.services = await ApplicationServices.create(game_config)

        # Manually initialize engine WITHOUT starting TickCoordinator
        # (game_service.initialize() would start ticks, causing continuous LLM calls)
        game_service = self.services.game_service
        initial_state = await game_service._load_initial_state()
        from simu_emperor.engine.engine import Engine

        game_service._engine = Engine(initial_state, game_service.event_bus)
        game_service._running = True

        # Persist initial state to DB so query tools can read it
        await self.services.repository.save_nation_data(initial_state)

        if game_service.engine:
            self.services.agent_service.engine = game_service.engine

        await self.services.agent_service.initialize_agents(["governor_zhili"])

        logger.info("BenchmarkContext initialized (temp_dir=%s)", self._temp_dir)

    async def shutdown(self) -> None:
        """Shutdown services and clean up temp directory."""
        if self.services:
            try:
                await self.services.shutdown()
            except Exception as e:
                logger.warning("Error during services shutdown: %s", e)
            self.services = None

        if self._temp_dir:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = ""

    # ------------------------------------------------------------------
    # Agent interaction
    # ------------------------------------------------------------------

    async def send_message(
        self,
        message: str,
        agent_id: str = "governor_zhili",
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        """Send a chat message to an agent and collect the response.

        Returns:
            {"response": str, "tool_calls": list[dict], "latency_ms": float}
        """
        from simu_emperor.event_bus.event import Event
        from simu_emperor.event_bus.event_types import EventType

        event_bus = self.services.event_bus
        benchmark_session_id = f"benchmark:{agent_id}:{uuid.uuid4().hex[:8]}"

        collected_tool_calls: list[dict[str, Any]] = []
        response_text = ""
        response_received = asyncio.Event()
        start_time = time.perf_counter()

        async def _handler(event: Event) -> None:
            nonlocal response_text

            if event.session_id != benchmark_session_id:
                return

            if event.type == EventType.OBSERVATION:
                actions = event.payload.get("actions", [])
                for action in actions:
                    tool_name = action.get("tool", "")
                    tool_result = action.get("result", "")
                    if tool_name:
                        collected_tool_calls.append(
                            {"name": tool_name, "args": {}, "result": str(tool_result)}
                        )

            if event.type in (EventType.AGENT_MESSAGE, EventType.RESPONSE):
                payload = event.payload or {}
                response_text = (
                    payload.get("content")
                    or payload.get("message")
                    or payload.get("response", "")
                )
                response_received.set()

        event_bus.subscribe("*", _handler)
        try:
            chat_event = Event(
                src="benchmark",
                dst=[f"agent:{agent_id}"],
                type=EventType.CHAT,
                payload={"message": message},
                session_id=benchmark_session_id,
            )
            await event_bus.send_event(chat_event)

            try:
                await asyncio.wait_for(response_received.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                pass

            latency_ms = (time.perf_counter() - start_time) * 1000
            return {
                "response": response_text,
                "tool_calls": collected_tool_calls,
                "latency_ms": latency_ms,
            }
        finally:
            event_bus.unsubscribe("*", _handler)

    # ------------------------------------------------------------------
    # Memory helpers
    # ------------------------------------------------------------------

    async def inject_memory_events(
        self,
        session_id: str,
        events: list[dict[str, Any]],
        agent_id: str = "governor_zhili",
    ) -> None:
        """Write pre-built events into a tape for testing.

        Accepts two formats:
        - Raw Event format: {"type": "chat", "payload": {...}}
        - Benchmark format: {"id": "e001", "content": "...", "event_type": "..."}
        """
        from simu_emperor.event_bus.event import Event

        tape_writer = self.services.agent_service.tape_writer
        if tape_writer is None:
            raise RuntimeError("TapeWriter not available on agent_service")

        for evt_data in events:
            # Support benchmark data format (id/content/event_type)
            if "content" in evt_data and "payload" not in evt_data:
                event_id = evt_data.get("id", "")
                payload = {
                    "message": evt_data["content"],
                    "benchmark_event_id": event_id,
                }
                event = Event(
                    event_id=event_id,
                    src=evt_data.get("src", f"agent:{agent_id}"),
                    dst=evt_data.get("dst", ["player"]),
                    type=evt_data.get("event_type", "chat"),
                    payload=payload,
                    session_id=session_id,
                )
            else:
                event = Event(
                    src=evt_data.get("src", f"agent:{agent_id}"),
                    dst=evt_data.get("dst", ["player"]),
                    type=evt_data.get("type", "chat"),
                    payload=evt_data.get("payload", {}),
                    session_id=session_id,
                )
            await tape_writer.write_event(event, agent_id=agent_id)

    async def search_tape_segments(
        self,
        query: str,
        agent_id: str = "governor_zhili",
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Search tape.jsonl files directly via SegmentSearcher (no metadata index needed)."""
        from simu_emperor.memory.models import StructuredQuery
        from simu_emperor.memory.segment_searcher import SegmentSearcher
        from simu_emperor.memory.tape_metadata import TapeMetadataEntry

        memory_dir = self.services.memory_dir
        searcher = SegmentSearcher(memory_dir=memory_dir)

        # Extract Chinese keywords from query for entity matching
        import re
        # Remove punctuation
        clean = re.sub(r'[？！。，、：；\u201c\u201d\u2018\u2019（）]+', '', query)
        # Chinese text has no spaces; use the full cleaned query as one keyword
        # plus 2-char bigrams for partial matching
        words = [clean] if len(clean) >= 2 else []
        # Add bigrams for better partial matching
        for i in range(0, max(0, len(clean) - 1)):
            bigram = clean[i:i + 2]
            if bigram.strip():
                words.append(bigram)

        structured_query = StructuredQuery(
            raw_query=query,
            intent="query_history",
            entities={"action": words[:3], "target": words[:3], "time": "history"},
            scope="cross_session",
            depth="tape",
        )

        # Find all tape.jsonl files for this agent
        agent_sessions_dir = memory_dir / "agents" / agent_id / "sessions"
        if not agent_sessions_dir.exists():
            return []

        # Build fake metadata entries for each session that has a tape.jsonl
        matching_entries = []
        for session_dir in agent_sessions_dir.iterdir():
            if session_dir.is_dir() and (session_dir / "tape.jsonl").exists():
                entry = TapeMetadataEntry(
                    session_id=session_dir.name,
                    title=session_dir.name,
                    created_tick=None,
                    created_time="",
                    last_updated_tick=None,
                    last_updated_time="",
                    event_count=0,
                    window_offset=0,
                    summary="",
                    segment_index=[],
                )
                matching_entries.append(entry)

        if not matching_entries:
            return []

        segments = await searcher.search_segments(
            agent_id=agent_id,
            matching_entries=matching_entries,
            query=structured_query,
            max_results=max_results,
        )

        return [seg.to_dict() for seg in segments]

    def get_context_manager(
        self,
        session_id: str,
        agent_id: str = "governor_zhili",
        max_tokens: int | None = None,
    ):
        """Create a ContextManager bound to a specific session for compression testing."""
        from simu_emperor.memory.context_manager import ContextConfig, ContextManager

        memory_dir = self.services.memory_dir
        tape_path = memory_dir / "agents" / agent_id / "sessions" / session_id / "tape.jsonl"

        llm_provider = self.services.agent_service.llm_provider

        config = ContextConfig()
        if max_tokens is not None:
            config.max_tokens = max_tokens
            # Scale keep_recent_events proportionally
            config.keep_recent_events = max(3, max_tokens // 100)

        return ContextManager(
            session_id=session_id,
            agent_id=agent_id,
            tape_path=tape_path,
            config=config,
            llm_provider=llm_provider,
            tape_metadata_mgr=self.services.agent_service.tape_metadata_mgr,
            tape_writer=self.services.agent_service.tape_writer,
        )
