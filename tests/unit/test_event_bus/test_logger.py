"""
测试 EventLogger 功能
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from simu_emperor.event_bus.event import Event
from simu_emperor.event_bus.event_types import EventType
from simu_emperor.event_bus.logger import FileEventLogger


class TestFileEventLogger:
    """测试 FileEventLogger 类"""

    @pytest.fixture
    def temp_log_dir(self):
        """创建临时日志目录"""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        # 清理
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def logger(self, temp_log_dir):
        """创建 FileEventLogger 实例"""
        return FileEventLogger(temp_log_dir)

    @pytest.fixture
    def sample_event(self):
        """创建示例事件"""
        return Event(
            src="player",
            dst=["agent:revenue_minister"],
            type=EventType.COMMAND,
            payload={"action": "adjust_tax", "rate": 0.1},
            session_id="session:test",
        )

    def test_logger_init(self, temp_log_dir):
        """测试初始化"""
        logger = FileEventLogger(temp_log_dir)
        assert logger.log_dir == temp_log_dir
        assert temp_log_dir.exists()

    def test_log_event(self, logger, sample_event):
        """测试记录事件"""
        logger.log(sample_event)

        # 检查文件是否创建
        assert logger.current_file is not None
        assert logger.current_file.exists()

        # 读取并验证内容
        with open(logger.current_file, "r") as f:
            content = f.read()
            assert "player" in content
            assert "agent:revenue_minister" in content
            assert "command" in content

    def test_log_multiple_events(self, logger):
        """测试记录多个事件"""
        events = [
            Event(src="player", dst=["agent:a"], type="command", session_id="session:test"),
            Event(src="agent:a", dst=["player"], type="response", session_id="session:test"),
            Event(src="player", dst=["agent:b"], type="query", session_id="session:test"),
        ]

        for event in events:
            logger.log(event)

        # 读取所有行
        with open(logger.current_file, "r") as f:
            lines = f.readlines()

        assert len(lines) == 3

    def test_log_rotation(self, temp_log_dir):
        """测试日志轮转（不同日期）"""
        # 注意：实际测试日期轮转需要 mock datetime
        # 这里只测试文件创建逻辑
        logger = FileEventLogger(temp_log_dir)

        # 记录事件
        event = Event(src="player", dst=["*"], type="test", session_id="session:test")
        logger.log(event)

        # 验证文件名格式
        assert logger.current_file is not None
        assert logger.current_file.name.startswith("events_")
        assert logger.current_file.suffix == ".jsonl"

    def test_query_events_by_type(self, logger):
        """测试按类型查询事件"""
        events = [
            Event(src="player", dst=["agent:a"], type="command", session_id="session:test"),
            Event(src="agent:a", dst=["player"], type="response", session_id="session:test"),
            Event(src="player", dst=["agent:b"], type="command", session_id="session:test"),
        ]

        for event in events:
            logger.log(event)

        # 查询 command 类型
        command_events = logger.query_events(event_type="command")
        assert len(command_events) == 2

        # 查询 response 类型
        response_events = logger.query_events(event_type="response")
        assert len(response_events) == 1

    def test_query_events_by_src(self, logger):
        """测试按源查询事件"""
        events = [
            Event(src="player", dst=["agent:a"], type="command", session_id="session:test"),
            Event(src="agent:a", dst=["player"], type="response", session_id="session:test"),
            Event(src="player", dst=["agent:b"], type="query", session_id="session:test"),
        ]

        for event in events:
            logger.log(event)

        # 查询 player 发起的事件
        player_events = logger.query_events(src="player")
        assert len(player_events) == 2

        # 查询 agent:a 发起的事件
        agent_events = logger.query_events(src="agent:a")
        assert len(agent_events) == 1

    def test_query_events_by_dst(self, logger):
        """测试按目标查询事件"""
        events = [
            Event(src="system", dst=["player"], type="notification", session_id="session:test"),
            Event(src="player", dst=["agent:a"], type="command", session_id="session:test"),
            Event(src="system", dst=["player"], type="alert", session_id="session:test"),
        ]

        for event in events:
            logger.log(event)

        # 查询发送到 player 的事件
        player_events = logger.query_events(dst="player")
        assert len(player_events) == 2

    def test_query_events_with_limit(self, logger):
        """测试限制返回数量"""
        events = [
            Event(src="player", dst=["agent:a"], type="command", session_id="session:test"),
            Event(src="agent:a", dst=["player"], type="response", session_id="session:test"),
            Event(src="player", dst=["agent:b"], type="query", session_id="session:test"),
        ]

        for event in events:
            logger.log(event)

        # 限制返回 2 条
        result = logger.query_events(limit=2)
        assert len(result) == 2

    def test_query_events_no_file(self, logger):
        """测试查询不存在的文件"""
        # 不存在的日期
        result = logger.query_events(date="20260101")
        assert len(result) == 0

    def test_get_log_files(self, logger):
        """测试获取日志文件列表"""
        # 记录一些事件
        for i in range(3):
            event = Event(src="test", dst=["*"], type=f"test_{i}", session_id="session:test")
            logger.log(event)

        files = logger.get_log_files()
        assert len(files) >= 1
        assert all(f.suffix == ".jsonl" for f in files)

    @pytest.mark.asyncio
    async def test_log_async(self, logger, sample_event):
        """测试异步记录事件"""
        await logger.log_async(sample_event)

        # 检查文件是否创建
        assert logger.current_file is not None
        assert logger.current_file.exists()

        # 读取并验证内容
        with open(logger.current_file, "r") as f:
            content = f.read()
            assert "player" in content
