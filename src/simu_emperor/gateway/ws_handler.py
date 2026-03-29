import asyncio
import json
import logging
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect

from simu_emperor.mq.dealer import MQDealer
from simu_emperor.mq.event import Event


logger = logging.getLogger(__name__)


class WebSocketHandler:
    def __init__(self, dealer: MQDealer, gateway_id: str):
        self.dealer = dealer
        self.gateway_id = gateway_id
        self._connections: dict[str, WebSocket] = {}

    async def handle(self, websocket: WebSocket) -> None:
        await websocket.accept()
        client_id = str(uuid4())
        self._connections[client_id] = websocket

        logger.info(f"Client connected: {client_id}")

        try:
            while True:
                data = await websocket.receive_json()

                event = self._client_message_to_event(data, client_id)

                await self.dealer.send_event(event)

                try:
                    response = await asyncio.wait_for(self.dealer.receive_event(), timeout=30.0)
                    await websocket.send_json(response.to_dict())
                except asyncio.TimeoutError:
                    await websocket.send_json({"error": "timeout"})

        except WebSocketDisconnect:
            logger.info(f"Client disconnected: {client_id}")
        finally:
            del self._connections[client_id]

    def _client_message_to_event(self, data: dict, client_id: str) -> Event:
        msg_type = data.get("type", "chat")
        agent_id = data.get("agent", "governor_zhili")
        session_id = data.get("session_id", f"web:{client_id}")
        text = data.get("text", "")

        event_type = "CHAT" if msg_type == "chat" else "COMMAND"

        return Event(
            event_id="",
            event_type=event_type,
            src=f"player:web:{client_id}",
            dst=[f"agent:{agent_id}"],
            session_id=session_id,
            payload={"message": text, "gateway_id": self.gateway_id},
            timestamp="",
        )

    async def broadcast_to_clients(self, event: Event) -> None:
        message = event.to_dict()
        for ws in self._connections.values():
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")

    def get_client_count(self) -> int:
        return len(self._connections)
