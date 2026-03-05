"""TapeSearcher for searching tape.jsonl files."""

import aiofiles
import asyncio
import json
from pathlib import Path


class TapeSearcher:
    """
    Searches tape.jsonl files for relevant events.

    Uses entity matching and scoring to find relevant events across sessions.
    """

    def __init__(self, memory_dir: Path):
        """
        Initialize TapeSearcher.

        Args:
            memory_dir: Base memory directory path
        """
        self.memory_dir = memory_dir

    async def search(
        self, agent_id: str, session_ids: list[str], entities: dict, max_results: int = 10
    ) -> list[dict]:
        """
        Search multiple session tapes for matching events.

        Args:
            agent_id: Agent identifier
            session_ids: List of session IDs to search
            entities: Entity dict for matching {action: [], target: [], time: ""}
            max_results: Maximum number of results to return

        Returns:
            List of matching event dicts, sorted by relevance score
        """
        # Build tape paths
        tape_paths = [
            self.memory_dir / "agents" / agent_id / "sessions" / session_id / "tape.jsonl"
            for session_id in session_ids
        ]

        # Filter to existing paths
        existing_paths = [p for p in tape_paths if p.exists()]

        if not existing_paths:
            return []

        # Read all tapes concurrently
        all_events = await self._read_tapes_concurrent(existing_paths, session_ids)

        # Score and filter events
        scored_events = []
        for event in all_events:
            score = self._calculate_score(event, entities)
            if score > 0:
                event["relevance_score"] = score
                scored_events.append(event)

        # Sort by score and return top N
        scored_events.sort(key=lambda e: e["relevance_score"], reverse=True)
        return scored_events[:max_results]

    async def _read_tapes_concurrent(
        self, tape_paths: list[Path], session_ids: list[str]
    ) -> list[dict]:
        """
        Read multiple tape files concurrently.

        Args:
            tape_paths: List of tape.jsonl paths
            session_ids: Corresponding session IDs

        Returns:
            List of all events from all tapes
        """

        async def read_tape(tape_path: Path, session_id: str) -> list[dict]:
            events = []
            try:
                async with aiofiles.open(tape_path, mode="r", encoding="utf-8") as f:
                    async for line in f:
                        if line.strip():
                            event = json.loads(line)
                            event["session_id"] = session_id
                            events.append(event)
            except Exception:
                pass  # Skip files that can't be read
            return events

        # Create tasks
        tasks = [
            read_tape(path, sid) for path, sid in zip(tape_paths, session_ids) if path.exists()
        ]

        # Execute concurrently
        results = await asyncio.gather(*tasks)

        # Flatten results
        all_events = []
        for events in results:
            all_events.extend(events)

        return all_events

    def _calculate_score(self, event: dict, entities: dict) -> float:
        """
        Calculate relevance score for an event.

        Args:
            event: Event dict
            entities: Entity dict for matching

        Returns:
            Relevance score (0-1)
        """
        score = 0.0

        event_content = str(event.get("content", {}))
        event_type = event.get("event_type", "")

        # Action matching: +0.4
        actions = entities.get("action", [])
        for action in actions:
            if action in event_content or action in event_type:
                score += 0.4

        # Target matching: +0.3
        targets = entities.get("target", [])
        for target in targets:
            if target in event_content:
                score += 0.3

        # Time matching: +0.2
        time_entity = entities.get("time", "")
        if time_entity == "history":
            score += 0.2

        return score
