"""
Unit tests for CLI web command
"""

from unittest.mock import patch


class TestCLIWebCommand:
    """测试 CLI web 命令"""

    @patch("simu_emperor.main.asyncio.run")
    def test_web_command_calls_main_web(self, mock_run):
        """测试 web 命令调用 main_web"""
        import sys
        from simu_emperor.main import entrypoint

        # 模拟命令行参数
        original_argv = sys.argv
        sys.argv = ["simu-emperor", "web"]

        try:
            entrypoint()

            # 验证 asyncio.run 被调用
            assert mock_run.called
        finally:
            sys.argv = original_argv

    @patch("simu_emperor.main.asyncio.run")
    def test_web_command_with_host_port(self, mock_run):
        """测试 web 命令带 host 和 port 参数"""
        import sys
        from simu_emperor.main import entrypoint

        # 模拟命令行参数
        original_argv = sys.argv
        sys.argv = ["simu-emperor", "web", "--host", "127.0.0.1", "--port", "9000"]

        try:
            entrypoint()

            # 验证 asyncio.run 被调用
            assert mock_run.called
        finally:
            sys.argv = original_argv

    @patch("simu_emperor.main.asyncio.run")
    def test_web_command_with_reload(self, mock_run):
        """测试 web 命令带 reload 参数"""
        import sys
        from simu_emperor.main import entrypoint

        # 模拟命令行参数
        original_argv = sys.argv
        sys.argv = ["simu-emperor", "web", "--reload"]

        try:
            entrypoint()

            # 验证 asyncio.run 被调用
            assert mock_run.called
        finally:
            sys.argv = original_argv

    @patch("simu_emperor.main.asyncio.run")
    def test_default_command_runs_cli(self, mock_run):
        """测试默认命令运行 CLI"""
        import sys
        from simu_emperor.main import entrypoint

        # 模拟命令行参数（无子命令）
        original_argv = sys.argv
        sys.argv = ["simu-emperor"]

        try:
            entrypoint()

            # 验证 asyncio.run 被调用
            assert mock_run.called
        finally:
            sys.argv = original_argv
