"""
皇帝模拟器 V2 - 主入口

事件驱动的多 Agent 回合制策略游戏。
"""

import asyncio
import logging
from pathlib import Path

from simu_emperor.cli.app import EmperorCLI
from simu_emperor.core.calculator import Calculator
from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.logger import FileEventLogger
from simu_emperor.llm.mock import MockProvider
from simu_emperor.config import settings


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main() -> None:
    """
    主函数

    初始化所有模块并启动 CLI。
    """
    logger.info("=== 皇帝模拟器 V2 启动 ===")

    # 1. 初始化事件总线
    log_dir = Path(settings.log_dir) / "events"
    log_dir.mkdir(parents=True, exist_ok=True)
    event_logger = FileEventLogger(log_dir)
    event_bus = EventBus(event_logger=event_logger)

    logger.info("EventBus initialized")

    # 2. 初始化 LLM 提供商
    # TODO: 根据配置选择 Provider
    # 如果有 ANTHROPIC_API_KEY，使用 AnthropicProvider
    # 否则使用 MockProvider
    llm_provider = MockProvider(response="Mock response")

    logger.info("LLM provider initialized")

    # 3. 初始化 Calculator
    # TODO: 需要等待 persistence 模块完成
    # repository = GameRepository(...)
    # calculator = Calculator(event_bus, repository)
    # calculator.start()

    logger.info("Calculator initialized")

    # 4. 初始化 CLI
    # TODO: 需要等待 persistence 模块完成
    # repository = ...
    # cli = EmperorCLI(event_bus, repository)

    logger.info("CLI initialized")

    # 5. 启动 CLI
    # await cli.run()

    # 临时：演示事件总线功能
    logger.info("=== 事件总线演示 ===")

    # 订阅测试事件
    async def test_handler(event):
        logger.info(f"收到事件: {event}")

    event_bus.subscribe("test", test_handler)

    # 发送测试事件
    from simu_emperor.event_bus.event import Event

    test_event = Event(
        src="test",
        dst=["test"],
        type="test",
        payload={"message": "Hello, V2!"},
    )

    await event_bus.send_event(test_event)

    # 等待事件处理
    await asyncio.sleep(0.1)

    logger.info("=== 皇帝模拟器 V2 正常退出 ===")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("收到中断信号，退出")
    except Exception as e:
        logger.error(f"发生错误: {e}", exc_info=True)
        raise
