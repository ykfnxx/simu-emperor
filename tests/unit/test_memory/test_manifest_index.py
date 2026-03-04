"""Test ManifestIndex for session management."""

from pathlib import Path
import json

import pytest

from simu_emperor.memory.manifest_index import ManifestIndex


class TestManifestIndex:
    """Test ManifestIndex class"""

    @pytest.mark.asyncio
    async def test_register_session_creates_manifest(self, tmp_path):
        """Test that register_session creates manifest.json"""
        manifest_index = ManifestIndex(memory_dir=tmp_path)

        await manifest_index.register_session(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            turn=5
        )

        # Verify manifest.json was created
        manifest_path = tmp_path / "manifest.json"
        assert manifest_path.exists()

        # Verify structure
        content = json.loads(manifest_path.read_text())
        assert "version" in content
        assert "sessions" in content
        assert "session:cli:default" in content["sessions"]
        assert "agents" in content["sessions"]["session:cli:default"]
        assert "revenue_minister" in content["sessions"]["session:cli:default"]["agents"]

    @pytest.mark.asyncio
    async def test_register_session_stores_metadata(self, tmp_path):
        """Test that register_session stores session metadata"""
        manifest_index = ManifestIndex(memory_dir=tmp_path)

        await manifest_index.register_session(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            turn=5
        )

        manifest_path = tmp_path / "manifest.json"
        content = json.loads(manifest_path.read_text())

        agent_data = content["sessions"]["session:cli:default"]["agents"]["revenue_minister"]
        assert agent_data["turn_start"] == 5
        assert agent_data["turn_end"] == 5
        assert "start_time" in agent_data
        assert agent_data["event_count"] == 0

    @pytest.mark.asyncio
    async def test_update_session_metadata(self, tmp_path):
        """Test that update_session updates session metadata"""
        manifest_index = ManifestIndex(memory_dir=tmp_path)

        # First register a session
        await manifest_index.register_session(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            turn=5
        )

        # Update metadata
        await manifest_index.update_session(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            key_topics=["拨款", "直隶"],
            summary="玩家询问直隶税收，随后决定拨款。",
            event_count=5
        )

        # Verify updates
        manifest_path = tmp_path / "manifest.json"
        content = json.loads(manifest_path.read_text())

        agent_data = content["sessions"]["session:cli:default"]["agents"]["revenue_minister"]
        assert agent_data["key_topics"] == ["拨款", "直隶"]
        assert agent_data["summary"] == "玩家询问直隶税收，随后决定拨款。"
        assert agent_data["event_count"] == 5

    @pytest.mark.asyncio
    async def test_get_candidate_sessions_by_entities(self, tmp_path):
        """Test that get_candidate_sessions matches by entities"""
        manifest_index = ManifestIndex(memory_dir=tmp_path)

        # Register multiple sessions with different topics
        await manifest_index.register_session(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            turn=5
        )
        await manifest_index.update_session(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            key_topics=["拨款", "直隶"],
            summary="拨款给直隶",
            event_count=3
        )

        await manifest_index.register_session(
            session_id="session:telegram:12345:chat:abc",
            agent_id="revenue_minister",
            turn=6
        )
        await manifest_index.update_session(
            session_id="session:telegram:12345:chat:abc",
            agent_id="revenue_minister",
            key_topics=["征税", "江南"],
            summary="讨论江南税收",
            event_count=2
        )

        # Query for sessions matching "拨款" action
        candidates = await manifest_index.get_candidate_sessions(
            agent_id="revenue_minister",
            entities={"action": ["拨款"], "target": ["直隶"], "time": "history"}
        )

        # Should return the first session with higher score
        assert len(candidates) > 0
        assert candidates[0]["session_id"] == "session:cli:default"

    @pytest.mark.asyncio
    async def test_register_session_handles_empty_manifest_file(self, tmp_path):
        """Test that register_session handles empty manifest.json file"""
        manifest_index = ManifestIndex(memory_dir=tmp_path)

        # Create an empty manifest.json file
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text("")

        # Register session should handle empty file gracefully
        await manifest_index.register_session(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            turn=5
        )

        # Verify manifest.json was created with proper structure
        assert manifest_path.exists()
        content = json.loads(manifest_path.read_text())
        assert "version" in content
        assert "sessions" in content
        assert "session:cli:default" in content["sessions"]

    @pytest.mark.asyncio
    async def test_register_session_handles_corrupted_manifest_file(self, tmp_path):
        """Test that register_session handles corrupted manifest.json file"""
        manifest_index = ManifestIndex(memory_dir=tmp_path)

        # Create a corrupted manifest.json file
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text("{invalid json content")

        # Register session should handle corrupted file gracefully
        await manifest_index.register_session(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            turn=5
        )

        # Verify manifest.json was recreated with proper structure
        content = json.loads(manifest_path.read_text())
        assert "version" in content
        assert "sessions" in content

    @pytest.mark.asyncio
    async def test_get_candidate_sessions_handles_empty_file(self, tmp_path):
        """Test that get_candidate_sessions handles empty manifest.json"""
        manifest_index = ManifestIndex(memory_dir=tmp_path)

        # Create an empty manifest.json file
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text("")

        # Should return empty list instead of crashing
        candidates = await manifest_index.get_candidate_sessions(
            agent_id="revenue_minister",
            entities={"action": ["拨款"]}
        )

        assert candidates == []

    @pytest.mark.asyncio
    async def test_get_candidate_sessions_handles_corrupted_file(self, tmp_path):
        """Test that get_candidate_sessions handles corrupted manifest.json"""
        manifest_index = ManifestIndex(memory_dir=tmp_path)

        # Create a corrupted manifest.json file
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text("{corrupted json")

        # Should return empty list instead of crashing
        candidates = await manifest_index.get_candidate_sessions(
            agent_id="revenue_minister",
            entities={"action": ["拨款"]}
        )

        assert candidates == []

    @pytest.mark.asyncio
    async def test_update_session_handles_empty_file(self, tmp_path):
        """Test that update_session handles empty manifest.json"""
        manifest_index = ManifestIndex(memory_dir=tmp_path)

        # Create an empty manifest.json file
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text("")

        # Update should handle empty file gracefully (no-op)
        await manifest_index.update_session(
            session_id="session:cli:default",
            agent_id="revenue_minister",
            key_topics=["拨款"]
        )

        # File should still be empty (no data to update)
        assert manifest_path.read_text() == ""
