import logging
from simu_emperor.mq.event import Event
from typing import Any

logger = logging.getLogger(__name__)


def event_to_frontend(event: Event) -> dict:
    event_type = event.event_type

    if event_type in ("CHAT", "AGENT_MESSAGE"):
        return {
            "kind": "chat",
            "data": {
                "agent": event.src.replace("agent:", "") if event.src else "unknown",
                "agentDisplayName": event.payload.get("agent_name", event.src),
                "text": event.payload.get("content", event.payload.get("message", "")),
                "timestamp": event.timestamp,
                "session_id": event.session_id,
            },
        }
    elif event_type in ("STATE_UPDATE", "tick_completed"):
        return {
            "kind": "state",
            "data": event.payload,
        }
    elif event_type in ("INCIDENT_CREATED", "INCIDENT_EXPIRED"):
        return {
            "kind": "event",
            "data": {
                "id": event.payload.get("incident_id", ""),
                "title": event.payload.get("title", ""),
                "description": event.payload.get("description", ""),
                "severity": event.payload.get("severity", "medium"),
                "timestamp": event.timestamp,
            },
        }
    elif event_type == "ERROR":
        return {
            "kind": "error",
            "data": {
                "message": event.payload.get("message", "Unknown error"),
                "code": event.payload.get("code"),
                "details": event.payload.get("details"),
            },
        }
    elif event_type == "SESSION_STATE":
        return {
            "kind": "session_state",
            "data": event.payload,
        }
    else:
        return {
            "kind": "event",
            "data": event.to_dict(),
        }


def frontend_to_event(data: dict, client_id: str, gateway_id: str) -> Event:
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


def format_health_response(connected: bool, client_count: int = 0) -> dict:
    return {
        "status": "running" if connected else "stopped",
        "connections": client_count,
    }


def format_agents_response(agents: list[dict]) -> list[dict]:
    if not agents:
        return []

    return [
        {
            "agent_id": agent.get("agent_id", agent.get("id", "")),
            "agent_name": agent.get("role_name", agent.get("name", agent.get("agent_id", ""))),
        }
        for agent in agents
    ]


def format_state_response(state: dict) -> dict:
    return {
        "turn": state.get("tick", 0),
        "imperial_treasury": state.get("treasury", 0) if state else 0,
        "base_tax_rate": state.get("base_tax_rate", 0.1) if state else 0.1,
        "tribute_rate": state.get("tribute_rate", 0.8) if state else 0.8,
        "fixed_expenditure": state.get("fixed_expenditure", 0) if state else 0,
        "provinces": state.get("provinces", {}),
    }
