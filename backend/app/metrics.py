from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict


@dataclass
class Metrics:
    events_ingested: int = 0
    duplicate_events: int = 0
    invalid_events: int = 0
    incidents_detected: int = 0
    autonomous_allowed: int = 0
    human_required: int = 0
    denied: int = 0
    execution_attempts: int = 0
    executions_verified: int = 0
    executions_failed: int = 0
    unsafe_autonomous_actions: int = 0
    revenue_at_risk: int = 0
    revenue_recovered: int = 0
    incidents_by_type: Dict[str, int] = field(default_factory=dict)

    def increment_incident(self, incident_type: str) -> None:
        self.incidents_detected += 1
        self.incidents_by_type[incident_type] = self.incidents_by_type.get(incident_type, 0) + 1

    def snapshot(self) -> dict:
        return asdict(self)


METRICS = Metrics()
