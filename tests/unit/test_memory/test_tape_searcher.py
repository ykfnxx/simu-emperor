"""Test TapeSearcher for searching tape.jsonl files."""

from simu_emperor.event_bus.event_types import EventType

from pathlib import Path
import json

import pytest

from simu_emperor.memory.tape_searcher import TapeSearcher


class TestTapeSearcher:
    """Test TapeSearcher class"""

    @pytest.mark.asyncio
    async def test_search_single_session(self, tmp_path):
        """Test searching a single session tape"""
        # Create sample tape file
        agent_dir = tmp_path / "agents" / "revenue_minister" / "sessions" / "session:cli:default"
        agent_dir.mkdir(parents=True)
        tape_path = agent_dir / "tape.jsonl"

        events = [
            {
                "event_id": "evt_001",
                "event_type": EventType.USER_QUERY,
                "content": {"query": "拨款给直隶"},
                "tokens": 10,
                "agent_id": "revenue_minister",
            },
            {
                "event_id": "evt_002",
                "event_type": EventType.TOOL_CALL,
                "content": {"tool": "allocate_funds", "args": {"province": "zhili"}},
                "tokens": 25,
                "agent_id": "revenue_minister",
            },
            {
                "event_id": "evt_003",
                "event_type": EventType.RESPONSE,
                "content": {"narrative": "已拨款"},
                "tokens": 15,
                "agent_id": "revenue_minister",
            },
        ]

        with open(tape_path, "w") as f:
            for event in events:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

        searcher = TapeSearcher(memory_dir=tmp_path)
        results = await searcher.search(
            agent_id="revenue_minister",
            session_ids=["session:cli:default"],
            entities={"action": ["拨款"], "target": ["直隶"]},
            max_results=10,
        )

        assert len(results) > 0
        # Should match events containing "拨款" or "直隶"
        assert any(
            "拨款" in str(r.get("content", {})) or "直隶" in str(r.get("content", {}))
            for r in results
        )
