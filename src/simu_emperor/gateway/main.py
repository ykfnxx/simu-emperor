import asyncio
import json
import logging
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

from simu_emperor.mq.dealer import MQDealer
from simu_emperor.mq.event import Event
from simu_emperor.mq.subscriber import MQSubscriber
from simu_emperor.gateway.ws_handler import WebSocketHandler
from simu_emperor.gateway.frontend_adapter import event_to_frontend
from simu_emperor.gateway.routes import router
from simu_emperor.persistence.client import SeekDBClient
from simu_emperor.persistence.repositories.game_state import GameStateRepository
from simu_emperor.persistence.repositories.agent_config import AgentConfigRepository


logger = logging.getLogger(__name__)


class GatewayProcess:
    def __init__(
        self,
        router_addr: str = "ipc://@simu_router",
        host: str = "0.0.0.0",
        port: int = 8000,
        db_host: str = "localhost",
        db_port: int = 3306,
        db_user: str = "root",
        db_password: str = "root",
        db_name: str = "simu_emperor",
    ):
        self.router_addr = router_addr
        self.host = host
        self.port = port
        self.db_host = db_host
        self.db_port = db_port
        self.db_user = db_user
        self.db_password = db_password
        self.db_name = db_name
        self.dealer: MQDealer | None = None
        self.subscriber: MQSubscriber | None = None
        self.ws_handler: WebSocketHandler | None = None
        self.db_client: SeekDBClient | None = None
        self.game_state_repo: GameStateRepository | None = None
        self.agent_config_repo: AgentConfigRepository | None = None
        self._running = False
        self._setup_routes()
        self.app = FastAPI(title="Emperor Simulator Gateway")

        self.app.include_router(router, prefix="/api")

        self._setup_routes()

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.ws_handler.handle(websocket)

        @self.app.get("/health")
        async def health():
            return {"status": "ok", "connected": self._running}

        @self.app.get("/agents")
        async def list_agents():
            if not self.agent_config_repo:
                return {"agents": []}
            return await self.agent_config_repo.get_all()

        @self.app.get("/state")
        async def get_state():
            if not self.game_state_repo:
                return {"turn": 0, "provinces": {}}
            tick = await self.game_state_repo.get_tick()
            treasury = await self.game_state_repo.get_national_treasury()
            return {
                "turn": tick,
                "imperial_treasury": treasury.get("total_silver", 0) if treasury else 0,
                "provinces": {},
            }

        @self.app.get("/overview")
        async def get_overview():
            if not self.game_state_repo:
                return {"turn": 0, "treasury": 0}
            tick = await self.game_state_repo.get_tick()
            treasury = await self.game_state_repo.get_national_treasury()
            return {
                "turn": tick,
                "treasury": treasury.get("total_silver", 0) if treasury else 0,
                "population": 0,
                "province_count": 0,
            }

    async def start(self) -> None:
        self.db_client = SeekDBClient(
            host=self.db_host,
            port=self.db_port,
            user=self.db_user,
            password=self.db_password,
            database=self.db_name,
        )
        await self.db_client.connect()

        self.game_state_repo = GameStateRepository(self.db_client)
        self.agent_config_repo = AgentConfigRepository(self.db_client)

        self.dealer = MQDealer(self.router_addr, identity="gateway:*")
        await self.dealer.connect()

        await self.dealer.send(json.dumps({"type": "REGISTER", "agent_id": "gateway:*"}))

        self.subscriber = MQSubscriber(self.router_addr.replace("@simu_router", "@simu_broadcast"))
        await self.subscriber.connect()
        await self.subscriber.subscribe("state.*")
        await self.subscriber.subscribe("agent.*")

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

        if self.subscriber:
            await self.subscriber.close()
        if self.dealer:
            await self.dealer.close()
        if self.db_client:
            await self.db_client.close()

        logger.info("Gateway process stopped")
