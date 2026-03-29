import asyncio
import logging
import signal
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from simu_emperor.router.router import Router
from simu_emperor.engine_v5.main import EngineProcess
from simu_emperor.worker.main import WorkerProcess
from simu_emperor.gateway.main import GatewayProcess
from simu_emperor.mq.publisher import MQPublisher


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class ServiceHandle:
    name: str
    task: asyncio.Task | None = None
    status: ServiceStatus = ServiceStatus.STOPPED
    error: Exception | None = None
    instance: Any = None


@dataclass
class OrchestratorConfig:
    router_addr: str = "ipc://@simu_router"
    broadcast_addr: str = "ipc://@simu_broadcast"
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000
    tick_interval: float = 5.0
    agent_ids: list[str] = field(default_factory=lambda: ["governor_zhili", "minister_revenue"])
    # Database config
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = "root"
    db_name: str = "simu_emperor"


class Orchestrator:
    def __init__(self, config: OrchestratorConfig | None = None):
        self.config = config or OrchestratorConfig()
        self.services: dict[str, ServiceHandle] = {}
        self._shutdown_event = asyncio.Event()
        self._publisher: MQPublisher | None = None

    async def start_router(self) -> None:
        handle = self.services["router"]
        handle.status = ServiceStatus.STARTING

        router = Router(router_addr=self.config.router_addr)
        handle.instance = router

        async def run_router():
            try:
                handle.status = ServiceStatus.RUNNING
                await router.start()
            except Exception as e:
                handle.status = ServiceStatus.ERROR
                handle.error = e
                logger.error(f"Router error: {e}")
                raise

        handle.task = asyncio.create_task(run_router())
        await asyncio.sleep(0.1)

    async def start_broadcast(self) -> None:
        handle = self.services["broadcast"]
        handle.status = ServiceStatus.STARTING

        publisher = MQPublisher(self.config.broadcast_addr)
        handle.instance = publisher

        async def run_broadcast():
            try:
                await publisher.bind()
                handle.status = ServiceStatus.RUNNING
                self._publisher = publisher
                while not self._shutdown_event.is_set():
                    await asyncio.sleep(1)
            except Exception as e:
                handle.status = ServiceStatus.ERROR
                handle.error = e
                logger.error(f"Broadcast error: {e}")
                raise

        handle.task = asyncio.create_task(run_broadcast())
        await asyncio.sleep(0.1)

    async def start_engine(self) -> None:
        handle = self.services["engine"]
        handle.status = ServiceStatus.STARTING

        engine = EngineProcess(
            router_addr=self.config.router_addr,
            broadcast_addr=self.config.broadcast_addr,
            tick_interval=self.config.tick_interval,
        )
        handle.instance = engine

        async def run_engine():
            try:
                handle.status = ServiceStatus.RUNNING
                await engine.start()
            except Exception as e:
                handle.status = ServiceStatus.ERROR
                handle.error = e
                logger.error(f"Engine error: {e}")
                raise

        handle.task = asyncio.create_task(run_engine())
        await asyncio.sleep(0.2)

    async def start_workers(self) -> None:
        for agent_id in self.config.agent_ids:
            handle = self.services[f"worker:{agent_id}"]
            handle.status = ServiceStatus.STARTING

            worker = WorkerProcess(
                agent_id=agent_id,
                router_addr=self.config.router_addr,
                broadcast_addr=self.config.broadcast_addr,
            )
            handle.instance = worker

            async def run_worker(w=worker, h=handle):
                try:
                    h.status = ServiceStatus.RUNNING
                    await w.start()
                except Exception as e:
                    h.status = ServiceStatus.ERROR
                    h.error = e
                    logger.error(f"Worker {w.agent_id} error: {e}")
                    raise

            handle.task = asyncio.create_task(run_worker())

        await asyncio.sleep(0.3)

    async def start_gateway(self) -> None:
        handle = self.services["gateway"]
        handle.status = ServiceStatus.STARTING

        gateway = GatewayProcess(
            router_addr=self.config.router_addr,
            host=self.config.gateway_host,
            port=self.config.gateway_port,
        )
        handle.instance = gateway

        async def run_gateway():
            try:
                handle.status = ServiceStatus.RUNNING
                await gateway.start()
            except Exception as e:
                handle.status = ServiceStatus.ERROR
                handle.error = e
                logger.error(f"Gateway error: {e}")
                raise

        handle.task = asyncio.create_task(run_gateway())
        await asyncio.sleep(0.2)

    def _init_services(self) -> None:
        self.services = {
            "router": ServiceHandle(name="router"),
            "broadcast": ServiceHandle(name="broadcast"),
            "engine": ServiceHandle(name="engine"),
            "gateway": ServiceHandle(name="gateway"),
        }
        for agent_id in self.config.agent_ids:
            self.services[f"worker:{agent_id}"] = ServiceHandle(name=f"worker:{agent_id}")

    async def start_all(self) -> None:
        self._init_services()

        logger.info("Starting V5 stack...")

        await self.start_router()
        logger.info("Router started")

        await self.start_broadcast()
        logger.info("Broadcast started")

        await self.start_engine()
        logger.info("Engine started")

        await self.start_workers()
        logger.info(f"Workers started: {self.config.agent_ids}")

        await self.start_gateway()
        logger.info(f"Gateway started on {self.config.gateway_host}:{self.config.gateway_port}")

        logger.info("All services started successfully")

    async def stop_all(self) -> None:
        logger.info("Stopping all services...")
        self._shutdown_event.set()

        stop_order = (
            ["gateway", "engine"]
            + [f"worker:{a}" for a in self.config.agent_ids]
            + ["broadcast", "router"]
        )

        for service_name in stop_order:
            handle = self.services.get(service_name)
            if not handle:
                continue

            handle.status = ServiceStatus.STOPPING

            if handle.instance and hasattr(handle.instance, "stop"):
                try:
                    await handle.instance.stop()
                except Exception as e:
                    logger.error(f"Error stopping {service_name}: {e}")

            if handle.task and not handle.task.done():
                handle.task.cancel()
                try:
                    await handle.task
                except asyncio.CancelledError:
                    pass

            handle.status = ServiceStatus.STOPPED
            logger.info(f"{service_name} stopped")

        logger.info("All services stopped")

    def get_status(self) -> dict[str, Any]:
        return {
            name: {
                "status": handle.status.value,
                "error": str(handle.error) if handle.error else None,
            }
            for name, handle in self.services.items()
        }

    async def wait_for_shutdown(self) -> None:
        await self._shutdown_event.wait()

    def request_shutdown(self) -> None:
        self._shutdown_event.set()


async def main():
    config = OrchestratorConfig()
    orchestrator = Orchestrator(config)

    loop = asyncio.get_running_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        orchestrator.request_shutdown()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await orchestrator.start_all()

        await orchestrator.wait_for_shutdown()

    finally:
        await orchestrator.stop_all()


if __name__ == "__main__":
    asyncio.run(main())
