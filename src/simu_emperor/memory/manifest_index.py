"""ManifestIndex for managing session metadata in manifest.json."""

from datetime import datetime, timezone
from pathlib import Path

from simu_emperor.common import FileOperationsHelper


class ManifestIndex:
    """Manages manifest.json for session indexing."""

    def __init__(self, memory_dir: Path):
        """
        Initialize ManifestIndex.

        Args:
            memory_dir: Base memory directory path
        """
        self.memory_dir = memory_dir
        self.manifest_path = memory_dir / "manifest.json"

    async def register_session(self, session_id: str, agent_id: str, turn: int) -> None:
        """
        Register a new session.

        Args:
            session_id: Session identifier
            agent_id: Agent identifier
            turn: Current turn number
        """
        # Load existing manifest or create new
        manifest = await FileOperationsHelper.read_json_file(self.manifest_path)
        if manifest is None or not manifest.get("sessions"):
            manifest = {
                "version": "1.0",
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "sessions": {},
            }

        # Initialize session structure if not exists
        if session_id not in manifest["sessions"]:
            manifest["sessions"][session_id] = {"agents": {}}

        # Add agent session entry
        manifest["sessions"][session_id]["agents"][agent_id] = {
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "turn_start": turn,
            "turn_end": turn,
            "key_topics": [],
            "summary": "",
            "summary_tokens": 0,
            "event_count": 0,
        }

        # Update last_updated
        manifest["last_updated"] = datetime.now(timezone.utc).isoformat()

        # Write back to file
        await FileOperationsHelper.write_json_file(self.manifest_path, manifest)

    async def update_session(self, session_id: str, agent_id: str, **updates) -> None:
        """
        Update session metadata.

        Args:
            session_id: Session identifier
            agent_id: Agent identifier
            **updates: Fields to update (key_topics, summary, event_count, etc.)
        """
        # Load manifest with error handling
        manifest = await FileOperationsHelper.read_json_file(self.manifest_path)
        if manifest is None or not manifest.get("sessions"):
            return  # No manifest to update

        # Update agent session data
        if session_id in manifest["sessions"]:
            if agent_id in manifest["sessions"][session_id]["agents"]:
                agent_data = manifest["sessions"][session_id]["agents"][agent_id]
                for key, value in updates.items():
                    agent_data[key] = value

        # Update last_updated and end_time
        manifest["last_updated"] = datetime.now(timezone.utc).isoformat()
        manifest["sessions"][session_id]["agents"][agent_id]["end_time"] = datetime.now(
            timezone.utc
        ).isoformat()

        # Write back
        await FileOperationsHelper.write_json_file(self.manifest_path, manifest)

    async def get_candidate_sessions(
        self, agent_id: str, entities: dict, exclude_session: str = None
    ) -> list[dict]:
        """
        Get candidate sessions based on entity matching.

        Args:
            agent_id: Agent identifier
            entities: Entity dict {action: [], target: [], time: ""}
            exclude_session: Optional session ID to exclude

        Returns:
            List of candidate session dicts, sorted by relevance score
        """
        # Load manifest with error handling
        manifest = await FileOperationsHelper.read_json_file(self.manifest_path)
        if manifest is None or not manifest.get("sessions"):
            return []

        candidates = []
        for session_id, session_data in manifest["sessions"].items():
            # Exclude specified session
            if exclude_session and session_id == exclude_session:
                continue

            # Only include sessions for this agent
            if agent_id not in session_data["agents"]:
                continue

            agent_session = session_data["agents"][agent_id]
            score = 0.0

            # Entity matching: action (0.4)
            if "action" in entities:
                for action in entities["action"]:
                    if agent_session.get("key_topics"):
                        for topic in agent_session["key_topics"]:
                            if action.lower() in topic.lower():
                                score += 0.4
                                break

            # Entity matching: target (0.3)
            if "target" in entities:
                for target in entities["target"]:
                    if agent_session.get("key_topics"):
                        for topic in agent_session["key_topics"]:
                            if target.lower() in topic.lower():
                                score += 0.3
                                break

            # Entity matching: time (0.2)
            if "time" in entities and entities["time"]:
                if entities["time"] in agent_session.get("summary", ""):
                    score += 0.2

            if score > 0:
                candidates.append({"session_id": session_id, "score": score, **agent_session})

        # Sort by score descending
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates

    async def get_session_summary(self, session_id: str, agent_id: str) -> str | None:
        """
        Get session summary.

        Args:
            session_id: Session identifier
            agent_id: Agent identifier

        Returns:
            Summary string or None if not found
        """
        manifest = await FileOperationsHelper.read_json_file(self.manifest_path)
        if manifest is None:
            return None

        session_data = manifest.get("sessions", {}).get(session_id, {})
        agent_session = session_data.get("agents", {}).get(agent_id, {})
        return agent_session.get("summary")

    async def refresh_session_summary(
        self,
        session_id: str,
        agent_id: str,
        llm_provider,
        tape_path: Path,
    ) -> None:
        """
        Refresh session summary using LLM.

        Args:
            session_id: Session identifier
            agent_id: Agent identifier
            llm_provider: LLM provider for summarization
            tape_path: Path to tape.jsonl file
        """
        # Load all events from tape
        from simu_emperor.memory.context_manager import count_tokens

        events = await FileOperationsHelper.read_jsonl_file(tape_path)
        if not events:
            return

        # Build summary text from events
        summary_parts = []
        for event in events:
            # Support both dict formats (tape.jsonl uses type/payload, old format used event_type/content)
            event_type = event.get("type") or event.get("event_type", "")
            payload = event.get("payload") or event.get("content", {})

            if event_type == "USER_QUERY":
                query = payload.get("query", "") if isinstance(payload, dict) else payload
                summary_parts.append(f"用户查询: {query}")
            elif event_type == "AGENT_RESPONSE":
                response = payload.get("response", "") if isinstance(payload, dict) else payload
                summary_parts.append(f"Agent响应: {response}")
            elif event_type == "GAME_EVENT":
                game_payload = payload if isinstance(payload, dict) else {}
                summary_parts.append(f"游戏事件: {game_payload.get('event_type', 'unknown')}")

        # Generate summary with LLM
        summary_text = "\n".join(summary_parts)
        if not summary_text:
            return

        # Simple summarization (can be enhanced with LLM)
        summary = summary_text[:500]  # Truncate for now
        summary_tokens = count_tokens(summary)

        # Update manifest
        await self.update_session(
            session_id,
            agent_id,
            summary=summary,
            summary_tokens=summary_tokens,
        )
