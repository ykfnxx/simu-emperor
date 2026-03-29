import asyncio
import json
import logging
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

from simu_emperor.mq.dealer import MQDealer
from simu_emperor.mq.event import Event
from simu_emperor.gateway.ws_handler import WebSocketHandler


logger = logging.getLogger(__name__)


class GatewayProcess:
    def __init__(
        self,
        router_addr: str = "ipc://@simu_router",
        host: str = "0.0.0.0",
        port: int = 8000,
    ):
        self.router_addr = router_addr
        self.host = host
        self.port = port

        self.dealer: MQDealer | None = None
        self.ws_handler: WebSocketHandler | None = None
        self._running = False

        self.app = FastAPI(title="Emperor Simulator Gateway")
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.ws_handler.handle(websocket)

        @self.app.get("/health")
        async def health():
            return {"status": "ok", "connected": self._running}

        @self.app.get("/agents")
        async def list_agents():
            return {"agents": []}

    async def start(self) -> None:
        self.dealer = MQDealer(self.router_addr, identity="gateway:*")
        await self.dealer.connect()

        await self.dealer.send(json.dumps({"type": "REGISTER", "agent_id": "gateway:*"}))

        self.ws_handler = WebSocketHandler(
            dealer=self.dealer,
            gateway_id=str(uuid4()),
        )

        self._running = True
        logger.info(f"Gateway process started on {self.host}:{self.port}")

        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        server = uvicorn.Server(config)

        await server.serve()

    async def stop(self) -> None:
        self._running = False
        if self.dealer:
            await self.dealer.close()
        logger.info("Gateway process stopped")
