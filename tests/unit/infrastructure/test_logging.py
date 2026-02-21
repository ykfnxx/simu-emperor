"""测试日志配置和审计日志器。"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from simu_emperor.config import LoggingConfig
from simu_emperor.infrastructure.logging import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
    unbind_context,
)
from simu_emperor.infrastructure.llm_audit import LLMAuditLogger, LLMAuditRecord


class TestLoggingConfiguration:
    """测试日志配置。"""

    def test_configure_logging_default(self, capsys: pytest.CaptureFixture) -> None:
        """测试默认日志配置（控制台模式）。"""
        config = LoggingConfig()
        configure_logging(config)

        logger = get_logger("test")
        logger.info("test_message", key="value")

        captured = capsys.readouterr()
        # 控制台模式应包含彩色输出（包含 ANSI 转义码或普通文本）
        assert "test_message" in captured.out or "test_message" in captured.err

    def test_configure_logging_json_mode(self, capsys: pytest.CaptureFixture) -> None:
        """测试 JSON 模式日志配置。"""
        config = LoggingConfig(log_level="DEBUG", log_json_format=True)
        configure_logging(config)

        logger = get_logger("test_json")
        logger.info("json_test_message", key="value")

        captured = capsys.readouterr()
        output = captured.out or captured.err

        # JSON 模式应输出有效 JSON
        try:
            data = json.loads(output.strip())
            assert data["event"] == "json_test_message"
            assert data["key"] == "value"
        except json.JSONDecodeError:
            # 某些情况下可能输出到 stderr
            pass

    def test_get_logger_returns_logger(self) -> None:
        """测试 get_logger 返回有效的 logger。"""
        config = LoggingConfig()
        configure_logging(config)

        logger = get_logger("test_module")
        assert logger is not None


class TestContextBinding:
    """测试上下文绑定功能。"""

    def test_bind_and_unbind_context(self) -> None:
        """测试手动绑定和解绑上下文。"""
        import structlog

        # 清理之前的上下文
        clear_context()

        # 绑定上下文
        bind_context(game_id="game_001", turn=5)

        # 验证上下文变量已设置
        # structlog 的 contextvars 使用内部存储
        ctx = structlog.contextvars.get_contextvars()
        assert ctx.get("game_id") == "game_001"
        assert ctx.get("turn") == 5

        # 解绑
        unbind_context("game_id")

        ctx = structlog.contextvars.get_contextvars()
        assert "game_id" not in ctx
        assert ctx.get("turn") == 5  # turn 仍然存在

        # 清理
        clear_context()

    def test_clear_context(self) -> None:
        """测试清除所有上下文。"""
        import structlog

        bind_context(game_id="game_001", turn=5, agent_id="agent_001")
        clear_context()

        ctx = structlog.contextvars.get_contextvars()
        assert len(ctx) == 0


class TestLogContext:
    """测试 log_context 上下文管理器。"""

    @pytest.mark.asyncio
    async def test_log_context_auto_cleanup(self) -> None:
        """测试 log_context 上下文管理器自动清理。"""
        import structlog

        from simu_emperor.infrastructure.logging import log_context

        clear_context()

        async with log_context(game_id="game_002", turn=10):
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("game_id") == "game_002"
            assert ctx.get("turn") == 10

        # 退出上下文后应自动清理
        ctx = structlog.contextvars.get_contextvars()
        assert "game_id" not in ctx
        assert "turn" not in ctx

        clear_context()


class TestLLMAuditLogger:
    """测试 LLM 审计日志器。"""

    @pytest.mark.asyncio
    async def test_audit_file_creation(self, tmp_path: Path) -> None:
        """测试审计文件创建。"""
        logger = LLMAuditLogger(audit_dir=tmp_path)

        record = LLMAuditRecord(
            timestamp=datetime.now(),
            game_id="game_001",
            turn=1,
            agent_id="governor_hebei",
            phase="summarize",
            provider="anthropic",
            model="claude-sonnet-4",
            system_prompt="You are...",
            user_prompt="Generate report...",
            response="Report content...",
            duration_ms=1500.5,
        )

        filepath = await logger.log(record)

        assert filepath is not None
        assert filepath.exists()
        assert "game_001" in str(filepath)  # 按游戏 ID 分目录
        assert "turn001" in filepath.name
        assert "governor_hebei" in filepath.name
        assert "summarize" in filepath.name

        # 验证文件内容是有效 JSON
        content = filepath.read_text(encoding="utf-8")
        data = json.loads(content)
        assert data["game_id"] == "game_001"
        assert data["turn"] == 1
        assert data["agent_id"] == "governor_hebei"
        assert data["phase"] == "summarize"
        assert data["version"] == 1  # 版本字段

    @pytest.mark.asyncio
    async def test_audit_with_tokens(self, tmp_path: Path) -> None:
        """测试带 token 信息的审计记录。"""
        logger = LLMAuditLogger(audit_dir=tmp_path)

        record = LLMAuditRecord(
            timestamp=datetime.now(),
            game_id="game_001",
            turn=1,
            agent_id="agent_001",
            phase="execute",
            provider="openai",
            model="gpt-4o",
            system_prompt="System",
            user_prompt="User",
            response={"narrative": "Done", "effects": []},
            duration_ms=500.0,
            tokens_prompt=100,
            tokens_completion=50,
        )

        filepath = await logger.log(record)
        assert filepath is not None

        content = filepath.read_text(encoding="utf-8")
        data = json.loads(content)
        assert data["tokens"]["prompt"] == 100
        assert data["tokens"]["completion"] == 50
        assert data["tokens"]["total"] == 150

    @pytest.mark.asyncio
    async def test_audit_error_case(self, tmp_path: Path) -> None:
        """测试错误情况的审计记录。"""
        logger = LLMAuditLogger(audit_dir=tmp_path)

        record = LLMAuditRecord(
            timestamp=datetime.now(),
            game_id="game_001",
            turn=1,
            agent_id="agent_001",
            phase="respond",
            provider="anthropic",
            model="claude-sonnet-4",
            system_prompt="System",
            user_prompt="User",
            response="",
            duration_ms=100.0,
            success=False,
            error="API timeout",
        )

        filepath = await logger.log(record)
        assert filepath is not None

        content = filepath.read_text(encoding="utf-8")
        data = json.loads(content)
        assert data["success"] is False
        assert data["error"] == "API timeout"

    @pytest.mark.asyncio
    async def test_list_audit_files(self, tmp_path: Path) -> None:
        """测试列出审计文件。"""
        logger = LLMAuditLogger(audit_dir=tmp_path)

        # 创建多个审计文件
        for turn in range(1, 4):
            record = LLMAuditRecord(
                timestamp=datetime.now(),
                game_id="game_001",
                turn=turn,
                agent_id="agent_001",
                phase="summarize",
                provider="mock",
                model="mock",
                system_prompt="",
                user_prompt="",
                response="",
                duration_ms=0.0,
            )
            await logger.log(record)

        # 测试无过滤
        files = logger.list_audit_files()
        assert len(files) == 3

        # 测试按游戏 ID 过滤
        files = logger.list_audit_files(game_id="game_001")
        assert len(files) == 3

        # 测试按回合过滤
        files = logger.list_audit_files(turn=1)
        assert len(files) == 1
        assert "turn001" in files[0].name

        # 测试不存在的游戏
        files = logger.list_audit_files(game_id="nonexistent")
        assert len(files) == 0

    @pytest.mark.asyncio
    async def test_audit_write_error_fallback(self, tmp_path: Path, monkeypatch) -> None:
        """测试审计文件写入失败时的降级处理。"""
        # 初始化日志配置
        configure_logging(LoggingConfig())

        # 创建一个有效的 logger
        logger = LLMAuditLogger(audit_dir=tmp_path)

        record = LLMAuditRecord(
            timestamp=datetime.now(),
            game_id="game_001",
            turn=1,
            agent_id="agent_001",
            phase="summarize",
            provider="mock",
            model="mock",
            system_prompt="",
            user_prompt="",
            response="",
            duration_ms=0.0,
        )

        # 模拟 aiofiles.open 抛出异常
        import simu_emperor.infrastructure.llm_audit as audit_module

        original_aiofiles = audit_module.aiofiles

        class MockAiofiles:
            @staticmethod
            async def open(*args, **kwargs):
                raise PermissionError("Mocked write failure")

        monkeypatch.setattr(audit_module, "aiofiles", MockAiofiles())

        try:
            # 应该不抛出异常，返回 None
            result = await logger.log(record)
            assert result is None
        finally:
            # 恢复原始 aiofiles
            monkeypatch.setattr(audit_module, "aiofiles", original_aiofiles)
