"""
皇帝模拟器 V2 - 主入口

事件驱动的多 Agent 回合制策略游戏。
"""

import asyncio
import logging
import sys

from simu_emperor.config import settings


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
            context_window=settings.llm.context_window,
        )

    elif provider_type == "openai":
        from simu_emperor.llm.openai import OpenAIProvider

        if not settings.llm.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
        return OpenAIProvider(
            api_key=settings.llm.api_key,
            model=settings.llm.get_model(),
            base_url=settings.llm.api_base,
            context_window=settings.llm.context_window,
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider_type}")


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


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
    args = sys.argv[1:] if len(sys.argv) > 1 else []
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

    # 启动服务器
    config = uvicorn.Config(
        "simu_emperor.adapters.web.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
    server = uvicorn.Server(config)

    try:
        await server.serve()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    finally:
        logger.info("=== Web Adapter 正常退出 ===")


def entrypoint() -> None:
    """入口点（非 async）"""
    try:
        asyncio.run(main_web())
    except KeyboardInterrupt:
        logger.info("收到中断信号，退出")
    except Exception as e:
        logger.error(f"发生错误: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    entrypoint()
