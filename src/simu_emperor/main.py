"""
皇帝模拟器 V2 - 主入口

事件驱动的多 Agent 回合制策略游戏。
"""

import asyncio
import logging
import sys
from pathlib import Path

from simu_emperor.event_bus.core import EventBus
from simu_emperor.event_bus.logger import FileEventLogger, DatabaseEventLogger
from simu_emperor.config import settings
from simu_emperor.persistence import init_database, close_database
from simu_emperor.persistence.repositories import GameRepository
from simu_emperor.engine.tick_coordinator import TickCoordinator
from simu_emperor.engine.engine import Engine
from simu_emperor.engine.models.base_data import NationData, ProvinceData
from simu_emperor.cli.app import EmperorCLI
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

    # 1.5. 初始化游戏状态（如果为空）
    state = await repository.load_state()
    if not state.get("provinces"):
        from simu_emperor.engine.models.base_data import (
            ProvinceBaseData,
            NationalBaseData,
            PopulationData,
            AgricultureData,
            CommerceData,
            TradeData,
            MilitaryData,
            TaxationData,
            ConsumptionData,
            AdministrationData,
            CropData,
            CropType,
        )
        from decimal import Decimal

        # 创建直隶省
        zhili = ProvinceBaseData(
            province_id="zhili",
            name="直隶",
            population=PopulationData(
                total=Decimal("2600000"),
                happiness=Decimal("0.7"),
                growth_rate=Decimal("0.002"),
                labor_ratio=Decimal("0.55"),
            ),
            agriculture=AgricultureData(
                irrigation_level=Decimal("0.3"),
                crops=[
                    CropData(
                        crop_type=CropType.WHEAT,
                        area_mu=Decimal("300000"),
                        yield_per_mu=Decimal("1.3"),
                    ),
                    CropData(
                        crop_type=CropType.RICE,
                        area_mu=Decimal("100000"),
                        yield_per_mu=Decimal("3"),
                    ),
                ],
            ),
            commerce=CommerceData(
                merchant_households=Decimal("150000"),
                market_prosperity=Decimal("0.7"),
            ),
            trade=TradeData(
                trade_volume=Decimal("500000"),
                trade_route_quality=Decimal("0.6"),
            ),
            military=MilitaryData(
                soldiers=Decimal("50000"),
                morale=Decimal("0.7"),
                garrison_size=Decimal("30000"),
                equipment_level=Decimal("0.5"),
                upkeep_per_soldier=Decimal("3"),
            ),
            taxation=TaxationData(
                land_tax_rate=Decimal("0.03"),
                commercial_tax_rate=Decimal("0.05"),
                tariff_rate=Decimal("0.1"),
            ),
            consumption=ConsumptionData(
                civilian_grain_per_capita=Decimal("3"),
                military_grain_per_soldier=Decimal("5"),
            ),
            administration=AdministrationData(
                official_count=Decimal("5000"),
                official_salary=Decimal("20"),
                infrastructure_value=Decimal("0.5"),
            ),
            granary_stock=Decimal("1200000"),
            local_treasury=Decimal("80000"),
        )

        # 创建初始国家数据
        initial_state = NationalBaseData(
            turn=0,
            provinces=[zhili],
            imperial_treasury=Decimal("100000"),
            national_tax_modifier=Decimal("1.0"),
            tribute_rate=Decimal("0.1"),
        )

        # 使用 JSON 序列化模式保存（Decimal → float/string）
        await repository.save_state(initial_state.model_dump(mode="json"))
        logger.info(f"Initialized game state with {len(initial_state.provinces)} province(s)")
    else:
        logger.info(f"Game state already loaded with {len(state.get('provinces', []))} province(s)")

    # 2. 初始化事件日志记录器
    log_dir = Path(settings.log_dir) / "events"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_logger = FileEventLogger(log_dir)
    db_logger = DatabaseEventLogger(conn)
    logger.info("Event loggers initialized")

    # 2.5. 初始化事件总线
    event_bus = EventBus(file_logger=file_logger, db_logger=db_logger)
    logger.info("EventBus initialized")

    # 定义会话 ID
    session_id = "session:cli:default"

    # 3. 初始化 LLM Provider
    try:
        llm_provider = create_llm_provider()
        logger.info(f"LLM provider initialized: {settings.llm.provider}")
    except Exception as e:
        logger.error(f"Failed to initialize LLM provider: {e}")
        logger.info("Falling back to MockProvider")
        from simu_emperor.llm.mock import MockProvider

        llm_provider = MockProvider()

    # 4. 初始化 AgentManager（在 Calculator 之前）
    agent_manager = AgentManager(
        event_bus=event_bus,
        llm_provider=llm_provider,
        template_dir=settings.data_dir / "default_agents",
        agent_dir=settings.data_dir / "agent",
        repository=repository,
        session_id=session_id,
    )

    # 初始化并启动默认 agents
    default_agents = [
        "governor_zhili",
        "minister_of_revenue",
        "governor_jiangnan",
        "governor_huguang",
        "governor_sichuan",
        "governor_shaanxi",
        "governor_shandong",
        "governor_zhejiang",
        "governor_jiangxi",
        "governor_fujian",
    ]
    for agent_id in default_agents:
        if agent_manager.initialize_agent(agent_id):
            agent_manager.add_agent(agent_id)
            logger.info(f"Agent {agent_id} started")

    logger.info(f"AgentManager initialized with {len(default_agents)} agents")

    # 5. 初始化 V4 Engine 和 TickCoordinator
    # 创建简单的初始状态（V4 使用简化的数据模型）
    from decimal import Decimal

    initial_provinces = {
        "zhili": ProvinceData(
            province_id="zhili",
            name="直隶",
            production_value=Decimal("100000"),
            population=Decimal("2600000"),
            fixed_expenditure=Decimal("50000"),
            stockpile=Decimal("1200000"),
        )
    }
    initial_state = NationData(
        turn=0,
        base_tax_rate=Decimal("0.10"),
        tribute_rate=Decimal("0.8"),
        fixed_expenditure=Decimal("0"),
        imperial_treasury=Decimal("100000"),
        provinces=initial_provinces,
    )

    engine = Engine(initial_state)
    tick_coordinator = TickCoordinator(event_bus, engine)
    tick_coordinator.start()
    logger.info("TickCoordinator started")

    # 6. 初始化 CLI
    cli = EmperorCLI(event_bus, repository, agent_manager, session_id=session_id)
    logger.info("CLI initialized")

    # 7. 启动 CLI 主循环
    try:
        await cli.run()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    finally:
        # 清理资源
        tick_coordinator.stop()
        if agent_manager:
            agent_manager.stop_all()
        await close_database()
        logger.info("=== 皇帝模拟器 V2 正常退出 ===")


def entrypoint() -> None:
    """CLI 入口点（非 async）"""
    # 检查命令行参数
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "telegram":
            try:
                asyncio.run(main_telegram())
            except KeyboardInterrupt:
                logger.info("收到中断信号，退出")
            except Exception as e:
                logger.error(f"发生错误: {e}", exc_info=True)
                raise
            return

        elif command == "web":
            try:
                asyncio.run(main_web())
            except KeyboardInterrupt:
                logger.info("收到中断信号，退出")
            except Exception as e:
                logger.error(f"发生错误: {e}", exc_info=True)
                raise
            return

    # 默认：启动 CLI
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("收到中断信号，退出")
    except Exception as e:
        logger.error(f"发生错误: {e}", exc_info=True)
        raise


async def main_telegram() -> None:
    """
    Telegram Bot 主函数

    初始化所有模块并启动 Telegram Bot。
    """
    logger.info("=== 皇帝模拟器 V2 - Telegram Bot 启动 ===")

    # 验证配置
    if not settings.telegram.bot_token:
        raise ValueError("SIMU_TELEGRAM__BOT_TOKEN is required for Telegram Bot")

    # 确保必要的目录存在
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    sessions_dir = settings.data_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    # 1. 初始化 LLM Provider
    try:
        llm_provider = create_llm_provider()
        logger.info(f"LLM provider initialized: {settings.llm.provider}")
    except Exception as e:
        logger.error(f"Failed to initialize LLM provider: {e}")
        logger.info("Falling back to MockProvider")
        from simu_emperor.llm.mock import MockProvider

        llm_provider = MockProvider()

    # 2. 创建 Telegram Application（不启动）
    from telegram.ext import Application

    application = Application.builder().token(settings.telegram.bot_token).build()

    # 3. 初始化 SessionManager
    from simu_emperor.adapters.telegram.session import SessionManager

    session_manager = SessionManager(settings, application, llm_provider)
    logger.info("SessionManager initialized")

    # 4. 初始化 Bot
    from simu_emperor.adapters.telegram.bot import TelegramBotService

    bot = TelegramBotService(
        settings.telegram.bot_token,
        session_manager,
        settings.telegram.enabled_commands,
    )

    # 5. 启动轮询
    try:
        await bot.start_polling()
        logger.info("=== Telegram Bot is running... ===")
        logger.info(f"Max sessions: {settings.telegram.max_sessions}")
        logger.info(f"Session timeout: {settings.telegram.session_timeout_hours}h")
        logger.info("Send /start to your bot to begin")

        # 保持运行
        while True:
            await asyncio.sleep(3600)

    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    finally:
        # 清理所有会话
        await bot.stop()
        await session_manager.shutdown_all()
        logger.info("=== Telegram Bot 正常退出 ===")


async def main_web() -> None:
    """
    Web Adapter 主函数

    启动 FastAPI 服务器，提供 WebSocket 和 REST API。
    """
    logger.info("=== 皇帝模拟器 V2 - Web Adapter 启动 ===")

    # 解析命令行参数（支持 --host 和 --port）
    import uvicorn

    host = "0.0.0.0"
    port = 8000
    reload = False

    # 简单的参数解析
    args = sys.argv[2:]  # 跳过 "web" 命令
    i = 0
    while i < len(args):
        if args[i] == "--host" and i + 1 < len(args):
            host = args[i + 1]
            i += 2
        elif args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
        elif args[i] == "--reload":
            reload = True
            i += 1
        else:
            i += 1

    logger.info(f"Starting web server on {host}:{port}")

    # 导入 FastAPI 应用
    from simu_emperor.adapters.web.server import app

    # 启动服务器
    config = uvicorn.Config(
        "simu_emperor.adapters.web.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )
    server = uvicorn.Server(config)

    try:
        await server.serve()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    finally:
        logger.info("=== Web Adapter 正常退出 ===")


if __name__ == "__main__":
    entrypoint()
