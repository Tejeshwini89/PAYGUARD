from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass(frozen=True)
class DecisionLedgerEntry:
    incident_id: str
    transaction_id: str
    action_type: str
    policy_decision: str
    execution_status: str
    verification_status: str
    revenue_recovered: int
    action_cost: int
    details: Dict[str, Any]
    created_at: str


@dataclass
class DecisionLedger:
    entries: List[DecisionLedgerEntry] = field(default_factory=list)

    def record(self, **kwargs: Any) -> DecisionLedgerEntry:
        entry = DecisionLedgerEntry(created_at=datetime.now(timezone.utc).isoformat(), **kwargs)
        self.entries.append(entry)
        return entry
