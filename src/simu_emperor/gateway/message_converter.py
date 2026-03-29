import json
from typing import Any

from simu_emperor.mq.event import Event


class MessageConverter:
    @staticmethod
    def client_to_event(data: dict[str, Any], client_id: str, gateway_id: str) -> Event:
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
            payload={"message": text, "gateway_id": gateway_id},
            timestamp="",
        )

    @staticmethod
    def event_to_client(event: Event) -> dict[str, Any]:
        return {
            "type": event.event_type,
            "src": event.src,
            "message": event.payload.get("message", ""),
            "session_id": event.session_id,
            "timestamp": event.timestamp,
        }

    @staticmethod
    def error_to_client(error: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        result = {"error": error}
        if details:
            result["details"] = details
        return result
