import logging
from typing import Any
from dataclasses import dataclass, field
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class Incident:
    incident_id: str
    incident_type: str
    title: str
    description: str
    severity: str
    tick_created: int
    tick_expire: int | None = None
    status: str = "active"
    session_id: str = ""
    agent_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class IncidentManager:
    def __init__(self):
        self._incidents: dict[str, Incident] = {}

    async def create_incident(
        self,
        data: dict[str, Any],
    ) -> Incident:
        incident_id = data.get("incident_id") or f"inc_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        incident = Incident(
            incident_id=incident_id,
            incident_type=data.get("incident_type", "unknown"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            severity=data.get("severity", "medium"),
            tick_created=data.get("tick_created", 0),
            tick_expire=data.get("tick_expire"),
            status=data.get("status", "active"),
            session_id=data.get("session_id", ""),
            agent_id=data.get("agent_id", ""),
        )

        self._incidents[incident_id] = incident
        logger.info(f"Incident created: {incident_id}")

        return incident

    async def resolve_incident(self, incident_id: str) -> bool:
        if incident_id not in self._incidents:
            return False

        self._incidents[incident_id].status = "resolved"
        logger.info(f"Incident resolved: {incident_id}")
        return True

    def expire_incidents(self, current_tick: int) -> list[str]:
        expired = []

        for incident_id, incident in list(self._incidents.items()):
            if incident.tick_expire and incident.tick_expire <= current_tick:
                incident.status = "expired"
                expired.append(incident_id)
                logger.info(f"Incident expired: {incident_id}")

        return expired

    def get_incident(self, incident_id: str) -> Incident | None:
        return self._incidents.get(incident_id)

    def get_active_incidents(self) -> list[Incident]:
        return [i for i in self._incidents.values() if i.status == "active"]

    def get_all_incidents(self) -> list[Incident]:
        return list(self._incidents.values())
