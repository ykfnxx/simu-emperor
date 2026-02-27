"""
皇帝模拟器 V2 - 主入口

事件驱动的多 Agent 回合制策略游戏。
"""

import asyncio
import logging
from pathlib import Path

from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.logger import FileEventLogger
from simu_emperor.config import settings
from simu_emperor.persistence import init_database, close_database
from simu_emperor.persistence.repositories import GameRepository
from simu_emperor.core.calculator import Calculator
from simu_emperor.cli.app import EmperorCLI
from simu_emperor.llm.mock import MockProvider
from simu_emperor.agents.manager import AgentManager


def create_llm_provider():
    """根据配置创建 LLM Provider"""
    provider_type = settings.llm.provider.lower()

    if provider_type == "mock":
        from simu_emperor.llm.mock import MockProvider
        return MockProvider()

    elif provider_type == "anthropic":
        from simu_emperor.llm.anthropic import AnthropicProvider
        if not settings.llm.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for Anthropic provider")
        return AnthropicProvider(
            api_key=settings.llm.api_key,
            model=settings.llm.get_model(),
        )

    elif provider_type == "openai":
        from simu_emperor.llm.openai import OpenAIProvider
        if not settings.llm.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
        return OpenAIProvider(
            api_key=settings.llm.api_key,
            model=settings.llm.get_model(),
            base_url=settings.llm.api_base,
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider_type}")


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

    # 确保必要的目录存在
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)

    # 1. 初始化数据库
    db_path = settings.data_dir / "game.db"
    conn = await init_database(str(db_path))
    repository = GameRepository(conn)
    logger.info(f"Database initialized: {db_path}")

    # 2. 初始化事件总线
    log_dir = Path(settings.log_dir) / "events"
    log_dir.mkdir(parents=True, exist_ok=True)
    event_logger = FileEventLogger(log_dir)
    event_bus = EventBus(event_logger=event_logger)
    logger.info("EventBus initialized")

    # 3. 初始化 Calculator
    calculator = Calculator(event_bus, repository)
    calculator.start()
    logger.info("Calculator started")

    # 4. 初始化 LLM Provider
    try:
        llm_provider = create_llm_provider()
        logger.info(f"LLM provider initialized: {settings.llm.provider}")
    except Exception as e:
        logger.error(f"Failed to initialize LLM provider: {e}")
        logger.info("Falling back to MockProvider")
        from simu_emperor.llm.mock import MockProvider
        llm_provider = MockProvider()

    # 5. 初始化 AgentManager
    agent_manager = AgentManager(
        event_bus=event_bus,
        llm_provider=llm_provider,
        template_dir=settings.data_dir / "default_agents",
        agent_dir=settings.data_dir / "agent",
    )

    # 初始化并启动默认 agents
    default_agents = ["governor_zhili", "minister_of_revenue"]
    for agent_id in default_agents:
        if agent_manager.initialize_agent(agent_id):
            agent_manager.add_agent(agent_id)
            logger.info(f"Agent {agent_id} started")

    logger.info(f"AgentManager initialized with {len(default_agents)} agents")

    # 6. 初始化 CLI
    cli = EmperorCLI(event_bus, repository, agent_manager)
    logger.info("CLI initialized")

    # 7. 启动 CLI 主循环
    try:
        await cli.run()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    finally:
        # 清理资源
        calculator.stop()
        if agent_manager:
            agent_manager.stop_all()
        await close_database()
        logger.info("=== 皇帝模拟器 V2 正常退出 ===")


def entrypoint() -> None:
    """CLI 入口点（非 async）"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("收到中断信号，退出")
    except Exception as e:
        logger.error(f"发生错误: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    entrypoint()

