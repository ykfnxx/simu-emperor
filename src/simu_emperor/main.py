"""
Emperor Simulator V5 - Main Entry Point

V5 多进程架构：
- Gateway: HTTP/WebSocket 接入
- Router: ZeroMQ 消息路由
- Engine: 游戏状态管理
- Worker: Agent 执行

使用方式:
    # 启动完整系统 (通过 Orchestrator)
    python -m simu_emperor --mode orchestrator

    # 启动单个进程
    python -m simu_emperor --mode gateway
    python -m simu_emperor --mode router
    python -m simu_emperor --mode engine
    python -m simu_emperor --mode worker --agent-id governor_zhili
"""

import argparse
import asyncio
import logging
import sys

from simu_emperor.orchestrator import Orchestrator


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Emperor Simulator V5 - Multi-process Architecture"
    )
    parser.add_argument(
        "--mode",
        choices=["orchestrator", "gateway", "router", "engine", "worker"],
        default="orchestrator",
        help="运行模式 (default: orchestrator)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Gateway 监听地址 (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Gateway 监听端口 (default: 8000)",
    )
    parser.add_argument(
        "--router-addr",
        default="ipc://@simu_router",
        help="Router address (default: ipc://@simu_router)",
    )
    parser.add_argument(
        "--broadcast-addr",
        default="ipc://@simu_broadcast",
        help="Broadcast address (default: ipc://@simu_broadcast)",
    )
    parser.add_argument(
        "--agent-id",
        help="Worker 模式: Agent ID",
    )
    parser.add_argument(
        "--tick-interval",
        type=float,
        default=5.0,
        help="Engine tick 间隔秒数 (default: 5.0)",
    )
    parser.add_argument(
        "--db-host",
        default="localhost",
        help="SeekDB 主机 (default: localhost)",
    )
    parser.add_argument(
        "--db-port",
        type=int,
        default=3306,
        help="SeekDB 端口 (default: 3306)",
    )
    parser.add_argument(
        "--db-user",
        default="root",
        help="SeekDB 用户 (default: root)",
    )
    parser.add_argument(
        "--db-password",
        default="root",
        help="SeekDB 密码 (default: root)",
    )
    parser.add_argument(
        "--db-name",
        default="simu_emperor",
        help="SeekDB 数据库名 (default: simu_emperor)",
    )
    return parser


async def run_orchestrator(args: argparse.Namespace) -> None:
    from simu_emperor.orchestrator import OrchestratorConfig

    config = OrchestratorConfig(
        gateway_host=args.host,
        gateway_port=args.port,
        router_addr=args.router_addr,
        broadcast_addr=args.broadcast_addr,
        tick_interval=args.tick_interval,
        db_host=args.db_host,
        db_port=args.db_port,
        db_user=args.db_user,
        db_password=args.db_password,
        db_name=args.db_name,
    )
    orchestrator = Orchestrator(config)

    try:
        await orchestrator.start_all()
        await orchestrator.wait_for_shutdown()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    finally:
        await orchestrator.stop_all()


async def run_gateway(args: argparse.Namespace) -> None:
    from simu_emperor.gateway.main import GatewayProcess

    gateway = GatewayProcess(
        router_addr=args.router_addr,
        host=args.host,
        port=args.port,
    )
    try:
        await gateway.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    finally:
        await gateway.stop()


async def run_router(args: argparse.Namespace) -> None:
    from simu_emperor.router.router import Router

    router = Router(router_addr=args.router_addr)
    try:
        await router.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    finally:
        await router.stop()


async def run_engine(args: argparse.Namespace) -> None:
    from simu_emperor.engine_v5.main import EngineProcess

    engine = EngineProcess(
        router_addr=args.router_addr,
        broadcast_addr=args.broadcast_addr,
        tick_interval=args.tick_interval,
    )
    try:
        await engine.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    finally:
        await engine.stop()


async def run_worker(args: argparse.Namespace) -> None:
    if not args.agent_id:
        logger.error("Worker 模式需要 --agent-id 参数")
        sys.exit(1)

    from simu_emperor.worker.main import WorkerProcess

    worker = WorkerProcess(
        agent_id=args.agent_id,
        router_addr=args.router_addr,
        broadcast_addr=args.broadcast_addr,
    )
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    finally:
        await worker.stop()


MODE_HANDLERS = {
    "orchestrator": run_orchestrator,
    "gateway": run_gateway,
    "router": run_router,
    "engine": run_engine,
    "worker": run_worker,
}


async def async_main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    logger.info(f"=== Emperor Simulator V5 - {args.mode.upper()} 模式 ===")

    handler = MODE_HANDLERS.get(args.mode)
    if handler:
        await handler(args)
    else:
        logger.error(f"Unknown mode: {args.mode}")
        sys.exit(1)


def entrypoint() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("退出")
    except Exception as e:
        logger.error(f"发生错误: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    entrypoint()
