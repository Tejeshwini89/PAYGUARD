from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .models import Event, TransactionState


@dataclass(frozen=True)
class EvidenceItem:
    source: str
    fact: str
    value: Any
    trust: str
    event_id: str | None = None
    occurred_at: str | None = None


@dataclass
class InvestigationBundle:
    transaction_id: str
    state: TransactionState
    evidence: List[EvidenceItem] = field(default_factory=list)


def build_evidence(state: TransactionState, events: List[Event]) -> InvestigationBundle:
    evidence: List[EvidenceItem] = []

    evidence.append(EvidenceItem("projected_state", "payment.status", state.payment.status, "high"))
    evidence.append(EvidenceItem("projected_state", "order.status", state.order.status, "high"))
    evidence.append(EvidenceItem("projected_state", "inventory.status", state.inventory.status, "high"))
    evidence.append(EvidenceItem("projected_state", "fulfillment.status", state.fulfillment.status, "high"))

    for event in sorted(events, key=lambda e: (e.occurred_at, e.received_at, e.event_id)):
        evidence.append(
            EvidenceItem(
                source=event.source,
                fact=event.event_type,
                value=event.payload,
                trust="high" if event.signature_verified else "low",
                event_id=event.event_id,
                occurred_at=event.occurred_at.isoformat(),
            )
        )

    return InvestigationBundle(transaction_id=state.transaction_id, state=state, evidence=evidence)
