"""ManifestIndex for managing session metadata in manifest.json."""

import aiofiles
import json
from datetime import datetime, timezone
from pathlib import Path

from simu_emperor.event_bus.event_types import EventType


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
        manifest = {
            "version": "1.0",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "sessions": {},
        }

        if self.manifest_path.exists():
            try:
                async with aiofiles.open(self.manifest_path, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                    if content.strip():  # Only parse if file is not empty
                        manifest = json.loads(content)
            except (json.JSONDecodeError, IOError) as e:
                # Log warning but continue with default manifest
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to load manifest.json, using default: {e}")

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
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(self.manifest_path, mode="w", encoding="utf-8") as f:
            await f.write(json.dumps(manifest, ensure_ascii=False, indent=2))

    async def update_session(self, session_id: str, agent_id: str, **updates) -> None:
        """
        Update session metadata.

        Args:
            session_id: Session identifier
            agent_id: Agent identifier
            **updates: Fields to update (key_topics, summary, event_count, etc.)
        """
        # Load manifest with error handling
        if not self.manifest_path.exists():
            return  # No manifest to update

        try:
            async with aiofiles.open(self.manifest_path, mode="r", encoding="utf-8") as f:
                content = await f.read()
                if not content.strip():
                    return  # Empty file, nothing to update
                manifest = json.loads(content)
        except (json.JSONDecodeError, IOError) as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to load manifest.json for update: {e}")
            return

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
        async with aiofiles.open(self.manifest_path, mode="w", encoding="utf-8") as f:
            await f.write(json.dumps(manifest, ensure_ascii=False, indent=2))

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
        if not self.manifest_path.exists():
            return []

        try:
            async with aiofiles.open(self.manifest_path, mode="r", encoding="utf-8") as f:
                content = await f.read()
                if not content.strip():
                    return []  # Empty file
                manifest = json.loads(content)
        except (json.JSONDecodeError, IOError):
            # Failed to parse, return empty candidates
            return []

        candidates = []
        for session_id, session_data in manifest["sessions"].items():
            # Exclude specified session
            if exclude_session and session_id == exclude_session:
                continue

            # Check if agent is in this session
            if agent_id not in session_data["agents"]:
                continue

            agent_data = session_data["agents"][agent_id]

            # Calculate relevance score based on entity matching
            score = 0.0
            key_topics = agent_data.get("key_topics", [])

            # Action matching: weight 0.4
            actions = entities.get("action", [])
            for action in actions:
                if action in key_topics:
                    score += 0.4

            # Target matching: weight 0.3
            targets = entities.get("target", [])
            for target in targets:
                if target in key_topics:
                    score += 0.3

            # Time matching: weight 0.2
            time_entity = entities.get("time", "")
            if time_entity == "history":
                score += 0.2

            if score > 0:
                candidates.append(
                    {
                        "session_id": session_id,
                        "score": score,
                        "turn_start": agent_data.get("turn_start", 0),
                        "turn_end": agent_data.get("turn_end", 0),
                        "summary": agent_data.get("summary", ""),
                        "key_topics": key_topics,
                        "event_count": agent_data.get("event_count", 0),
                    }
                )

        # Sort by score (highest first)
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates

    async def refresh_session_summary(
        self, session_id: str, agent_id: str, llm_provider, tape_path: Path
    ) -> None:
        """
        刷新session总结（基于完整tape）

        SPEC: V3_MEMORY_SYSTEM_SPEC.md §4.2
        """
        # 读取tape文件
        all_events = []
        if tape_path.exists():
            try:
                async with aiofiles.open(tape_path, mode="r", encoding="utf-8") as f:
                    async for line in f:
                        line = line.strip()
                        if line:
                            try:
                                event_data = json.loads(line)
                                all_events.append(event_data)
                            except json.JSONDecodeError:
                                continue
            except Exception as e:
                import logging

                logging.getLogger(__name__).warning(f"Failed to read tape for summary: {e}")
                return

        # 限制读取最近N条事件（避免tape过大时LLM调用失败）
        if len(all_events) > 100:
            all_events = all_events[-100:]

        # 构建对话文本
        conversation_parts = []
        for event in all_events:
            event_type = event.get("event_type", "UNKNOWN")
            content = event.get("content", {})

            # 格式化事件类型
            if event_type in (EventType.USER_QUERY, "user_query"):
                role = "用户"
                text = content.get("query", "") if isinstance(content, dict) else str(content)
            elif event_type in (EventType.AGENT_RESPONSE, "agent_response"):
                role = "官员"
                text = content.get("response", "") if isinstance(content, dict) else str(content)
            elif event_type in (EventType.ASSISTANT_RESPONSE, "assistant_response"):
                # 中间响应标记为"思考"
                role = "思考"
                text = content.get("response", "") if isinstance(content, dict) else str(content)
            elif event_type in (EventType.TOOL_RESULT, "tool_result"):
                # 工具结果
                tool = content.get("tool", "") if isinstance(content, dict) else str(content)
                result = content.get("result", "") if isinstance(content, dict) else str(content)
                # 限制结果显示长度
                result_preview = (
                    str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
                )
                text = f"工具 {tool} 返回: {result_preview}"
            else:
                role = event_type
                text = str(content)

            conversation_parts.append(f"{role}: {text}")

        conversation = "\n".join(conversation_parts)

        # 调用LLM生成总结
        prompt = f"""请用2-3句话总结以下对话的要点：

{conversation}

总结："""

        try:
            response = await llm_provider.call(
                prompt=prompt,
                system_prompt="你是一个游戏记录助手，负责总结会话内容。",
                max_tokens=200,
                temperature=0.3,
            )
            summary = response.strip()

            # 更新manifest
            await self.update_session(
                session_id=session_id,
                agent_id=agent_id,
                summary=summary,
                event_count=len(all_events),
            )
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"Failed to generate summary: {e}")

    async def get_session_summary(self, session_id: str, agent_id: str) -> str | None:
        """
        获取指定session的summary

        SPEC: V3_MEMORY_SYSTEM_SPEC.md §4.2
        """
        if not self.manifest_path.exists():
            return None

        try:
            async with aiofiles.open(self.manifest_path, mode="r", encoding="utf-8") as f:
                content = await f.read()
                if not content.strip():
                    return None
                manifest = json.loads(content)
        except (json.JSONDecodeError, IOError):
            return None

        session_data = manifest.get("sessions", {}).get(session_id)
        if not session_data:
            return None

        agents = session_data.get("agents", {})
        if agent_id and agent_id in agents:
            return agents[agent_id].get("summary")
        elif len(agents) == 1:
            # 如果只有一个agent，返回它的summary
            return list(agents.values())[0].get("summary")
        return None
