"""Group Chat Service unit tests."""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from simu_emperor.application.group_chat_service import GroupChatService, utcnow


@pytest.fixture
def mock_session_manager():
    """Create mock session manager."""
    return AsyncMock()


@pytest.fixture
def memory_dir(tmp_path: Path) -> Path:
    """Create memory directory."""
    memory = tmp_path / "memory"
    memory.mkdir(parents=True, exist_ok=True)
    return memory


class TestGroupChatService:
    """Test GroupChatService."""

    def test_init(self, mock_session_manager, memory_dir):
        """Test group chat service initialization."""
        service = GroupChatService(
            session_manager=mock_session_manager,
            memory_dir=memory_dir,
        )

        assert service.session_manager == mock_session_manager
        assert service.memory_dir == memory_dir
        assert len(service._group_chats) == 0

    async def test_create_group_chat(self, mock_session_manager, memory_dir):
        """Test creating a new group chat."""
        service = GroupChatService(
            session_manager=mock_session_manager,
            memory_dir=memory_dir,
        )

        with patch.object(service, "_save_group_chats", new=AsyncMock()):
            result = await service.create_group_chat(
                name="Test Group",
                agent_ids=["governor_zhili", "minister_of_revenue"],
                session_id="session:web:main",
            )

            assert result.name == "Test Group"
            assert result.agent_ids == ["governor_zhili", "minister_of_revenue"]
            assert result.session_id == "session:web:main"
            # Verify the group was stored
            assert result.group_id in service._group_chats

    async def test_create_group_chat_generates_id(self, mock_session_manager, memory_dir):
        """Test that group chat IDs are generated correctly."""
        service = GroupChatService(
            session_manager=mock_session_manager,
            memory_dir=memory_dir,
        )

        with patch.object(service, "_save_group_chats", new=AsyncMock()):
            result = await service.create_group_chat(
                name="Test",
                agent_ids=["governor_zhili"],
            )

            assert result.group_id.startswith("group:web:")
            # Group ID should have timestamp and uuid components
            parts = result.group_id.split(":")
            assert len(parts) == 4  # group:web:timestamp:suffix

    async def test_list_group_chats(self, mock_session_manager, memory_dir):
        """Test listing all group chats."""
        service = GroupChatService(
            session_manager=mock_session_manager,
            memory_dir=memory_dir,
        )

        # Add some mock group chats
        mock_chat1 = MagicMock()
        mock_chat1.group_id = "group:web:001"
        mock_chat2 = MagicMock()
        mock_chat2.group_id = "group:web:002"

        service._group_chats = {
            "group:web:001": mock_chat1,
            "group:web:002": mock_chat2,
        }

        result = await service.list_group_chats()

        assert len(result) == 2
        assert mock_chat1 in result
        assert mock_chat2 in result

    async def test_get_group_chat(self, mock_session_manager, memory_dir):
        """Test getting a specific group chat."""
        service = GroupChatService(
            session_manager=mock_session_manager,
            memory_dir=memory_dir,
        )

        mock_chat = MagicMock()
        mock_chat.group_id = "group:web:001"
        service._group_chats["group:web:001"] = mock_chat

        result = await service.get_group_chat("group:web:001")

        assert result == mock_chat

    async def test_get_group_chat_not_found(self, mock_session_manager, memory_dir):
        """Test getting non-existent group chat returns None."""
        service = GroupChatService(
            session_manager=mock_session_manager,
            memory_dir=memory_dir,
        )

        result = await service.get_group_chat("group:web:nonexistent")

        assert result is None

    async def test_send_to_group_chat(self, mock_session_manager, memory_dir):
        """Test sending message to group chat."""
        service = GroupChatService(
            session_manager=mock_session_manager,
            memory_dir=memory_dir,
        )

        mock_chat = MagicMock()
        mock_chat.group_id = "group:web:001"
        mock_chat.agent_ids = ["governor_zhili", "minister_of_revenue"]
        mock_chat.message_count = 5
        service._group_chats["group:web:001"] = mock_chat

        with patch.object(service, "_save_group_chats", new=AsyncMock()):
            result = await service.send_to_group_chat("group:web:001", "Test message")

            assert result == ["governor_zhili", "minister_of_revenue"]
            assert mock_chat.message_count == 6

    async def test_send_to_group_chat_not_found(self, mock_session_manager, memory_dir):
        """Test sending to non-existent group raises error."""
        service = GroupChatService(
            session_manager=mock_session_manager,
            memory_dir=memory_dir,
        )

        with pytest.raises(ValueError, match="Group chat not found"):
            await service.send_to_group_chat("group:web:nonexistent", "Test")

    async def test_add_agent_to_group(self, mock_session_manager, memory_dir):
        """Test adding agent to group chat."""
        service = GroupChatService(
            session_manager=mock_session_manager,
            memory_dir=memory_dir,
        )

        mock_chat = MagicMock()
        mock_chat.group_id = "group:web:001"
        mock_chat.agent_ids = ["governor_zhili"]
        service._group_chats["group:web:001"] = mock_chat

        with patch.object(service, "_save_group_chats", new=AsyncMock()):
            result = await service.add_agent_to_group("group:web:001", "minister_of_revenue")

            assert result is True
            assert "minister_of_revenue" in mock_chat.agent_ids

    async def test_add_agent_to_group_already_present(self, mock_session_manager, memory_dir):
        """Test adding agent that's already in group returns False."""
        service = GroupChatService(
            session_manager=mock_session_manager,
            memory_dir=memory_dir,
        )

        mock_chat = MagicMock()
        mock_chat.group_id = "group:web:001"
        mock_chat.agent_ids = ["governor_zhili"]
        service._group_chats["group:web:001"] = mock_chat

        with patch.object(service, "_save_group_chats", new=AsyncMock()):
            result = await service.add_agent_to_group("group:web:001", "governor_zhili")

            assert result is False

    async def test_add_agent_to_group_not_found(self, mock_session_manager, memory_dir):
        """Test adding agent to non-existent group raises error."""
        service = GroupChatService(
            session_manager=mock_session_manager,
            memory_dir=memory_dir,
        )

        with pytest.raises(ValueError, match="Group chat not found"):
            await service.add_agent_to_group("group:web:nonexistent", "agent_id")

    async def test_remove_agent_from_group(self, mock_session_manager, memory_dir):
        """Test removing agent from group chat."""
        service = GroupChatService(
            session_manager=mock_session_manager,
            memory_dir=memory_dir,
        )

        mock_chat = MagicMock()
        mock_chat.group_id = "group:web:001"
        mock_chat.agent_ids = ["governor_zhili", "minister_of_revenue"]
        service._group_chats["group:web:001"] = mock_chat

        with patch.object(service, "_save_group_chats", new=AsyncMock()):
            result = await service.remove_agent_from_group("group:web:001", "governor_zhili")

            assert result is True
            assert "governor_zhili" not in mock_chat.agent_ids
            assert "minister_of_revenue" in mock_chat.agent_ids

    async def test_remove_agent_from_group_not_present(self, mock_session_manager, memory_dir):
        """Test removing agent not in group returns False."""
        service = GroupChatService(
            session_manager=mock_session_manager,
            memory_dir=memory_dir,
        )

        mock_chat = MagicMock()
        mock_chat.group_id = "group:web:001"
        mock_chat.agent_ids = ["minister_of_revenue"]
        service._group_chats["group:web:001"] = mock_chat

        with patch.object(service, "_save_group_chats", new=AsyncMock()):
            result = await service.remove_agent_from_group("group:web:001", "governor_zhili")

            assert result is False

    async def test_load_group_chats_from_storage(self, mock_session_manager, memory_dir):
        """Test loading group chats from file."""
        # Create a mock group chats file
        group_chats_path = memory_dir / "group_chats.json"
        test_data = {
            "group_chats": [
                {
                    "group_id": "group:web:001",
                    "name": "Test Group",
                    "agent_ids": ["governor_zhili"],
                    "created_by": "player:web",
                    "created_at": "2026-03-01T12:00:00Z",
                    "session_id": "session:web:main",
                    "message_count": 0,
                }
            ],
            "last_updated": "2026-03-01T12:00:00Z",
        }
        group_chats_path.write_text(json.dumps(test_data))

        service = GroupChatService(
            session_manager=mock_session_manager,
            memory_dir=memory_dir,
        )

        await service._load_group_chats()

        assert "group:web:001" in service._group_chats
        assert service._group_chats["group:web:001"].name == "Test Group"

    async def test_save_group_chats_to_storage(self, mock_session_manager, memory_dir):
        """Test saving group chats to file."""
        service = GroupChatService(
            session_manager=mock_session_manager,
            memory_dir=memory_dir,
        )

        mock_chat = MagicMock()
        mock_chat.to_dict = MagicMock(return_value={
            "group_id": "group:web:001",
            "name": "Test Group",
        })
        service._group_chats["group:web:001"] = mock_chat

        await service._save_group_chats()

        group_chats_path = memory_dir / "group_chats.json"
        assert group_chats_path.exists()

        data = json.loads(group_chats_path.read_text())
        assert "group_chats" in data
        assert len(data["group_chats"]) == 1

    def test_utcnow(self):
        """Test utcnow helper returns aware datetime."""
        result = utcnow()
        assert result.tzinfo is not None
