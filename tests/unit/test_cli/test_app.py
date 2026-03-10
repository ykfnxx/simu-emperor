"""
测试 EmperorCLI
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from simu_emperor.cli.app import EmperorCLI
from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType


@pytest.fixture
def mock_event_bus():
    """Mock EventBus"""
    event_bus = MagicMock(spec=EventBus)
    event_bus.subscribe = MagicMock()
    event_bus.send_event = AsyncMock()
    return event_bus


@pytest.fixture
def mock_repository():
    """Mock Repository"""
    return MagicMock()


@pytest.fixture
def cli(mock_event_bus, mock_repository):
    """创建 CLI 实例"""
    return EmperorCLI(mock_event_bus, mock_repository)


class TestEmperorCLI:
    """测试 EmperorCLI 类"""

    def test_init(self, cli, mock_event_bus, mock_repository):
        """测试初始化"""
        assert cli.event_bus == mock_event_bus
        assert cli.repository == mock_repository
        assert cli._running is False
        assert cli._chat_mode is False

    @pytest.mark.asyncio
    async def test_handle_command_help(self, cli, capsys):
        """测试处理 /help 命令"""
        await cli._handle_command("/help")

        captured = capsys.readouterr()
        assert "命令帮助" in captured.out

    @pytest.mark.asyncio
    async def test_handle_command_quit(self, cli):
        """测试处理 /quit 命令"""
        cli._running = True
        await cli._handle_command("/quit")

        assert cli._running is False

    @pytest.mark.asyncio
    async def test_handle_command_unknown(self, cli, capsys):
        """测试处理未知命令"""
        await cli._handle_command("/unknown")

        captured = capsys.readouterr()
        assert "未知命令" in captured.out

    @pytest.mark.asyncio
    async def test_enter_chat_mode(self, cli):
        """测试进入对话模式"""
        await cli._enter_chat_mode("test_agent")

        assert cli._chat_mode is True
        assert cli._chat_agent_id == "test_agent"

    @pytest.mark.asyncio
    async def test_enter_chat_mode_no_agent(self, cli, capsys):
        """测试进入对话模式（无 Agent ID）"""
        await cli._enter_chat_mode(None)

        assert cli._chat_mode is False

    @pytest.mark.asyncio
    async def test_exit_chat_mode(self, cli):
        """测试退出对话模式"""
        cli._chat_mode = True
        cli._chat_agent_id = "test_agent"

        cli._exit_chat_mode()

        assert cli._chat_mode is False
        assert cli._chat_agent_id == ""

    @pytest.mark.asyncio
    async def test_on_response(self, cli):
        """测试处理响应事件"""
        event = Event(
            src="agent:test",
            dst=["player"],
            type=EventType.RESPONSE,
            payload={"narrative": "Test response"},
            session_id="test_session_response",
        )

        await cli._on_response(event)

        # 验证事件被放入队列
        assert not cli._response_queue.empty()
        queued_event = await cli._response_queue.get()
        assert queued_event.payload["narrative"] == "Test response"

    def test_get_agent_display_name(self, cli):
        """测试获取 Agent 显示名称"""
        name = cli._get_agent_display_name("revenue_minister")

        assert name == "Revenue Minister"
