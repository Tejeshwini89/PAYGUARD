from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from .evidence import InvestigationBundle
from .models import Event, TransactionState


@dataclass
class InvestigationTools:
    """Read-only tools exposed to the AI investigator in the MVP."""

    state: TransactionState
    events: List[Event]
    bundle: InvestigationBundle

    def get_payment(self) -> Dict[str, Any]:
        p = self.state.payment
        return {
            "status": p.status,
            "payment_id": p.payment_id,
            "amount": p.amount,
            "currency": p.currency,
            "method": p.method,
        }

    def get_order(self) -> Dict[str, Any]:
        o = self.state.order
        return {
            "status": o.status,
            "order_id": o.order_id,
            "amount": o.amount,
            "currency": o.currency,
        }

    def get_inventory(self) -> Dict[str, Any]:
        i = self.state.inventory
        return {
            "status": i.status,
            "product_id": i.product_id,
            "available_quantity": i.available_quantity,
            "reserved_quantity": i.reserved_quantity,
        }

    def get_fulfillment(self) -> Dict[str, Any]:
        f = self.state.fulfillment
        return {
            "status": f.status,
            "attempt_count": f.attempt_count,
            "last_error": f.last_error,
        }

    def get_event_history(self) -> List[Dict[str, Any]]:
        return [
            {
                "event_id": e.event_id,
                "event_type": e.event_type,
                "occurred_at": e.occurred_at.isoformat(),
                "received_at": e.received_at.isoformat(),
                "payload": e.payload,
            }
            for e in sorted(self.events, key=lambda e: (e.occurred_at, e.received_at, e.event_id))
        ]

    def check_duplicate_payment(self) -> Dict[str, Any]:
        payment_ids: Dict[str, int] = {}
        for e in self.events:
            if e.event_type == "payment.captured":
                pid = e.payload.get("payment_id") or e.payload.get("id")
                if pid:
                    payment_ids[pid] = payment_ids.get(pid, 0) + 1
        duplicates = {k: v for k, v in payment_ids.items() if v > 1}
        return {"duplicate_detected": bool(duplicates), "payment_counts": duplicates}

    def list_evidence(self) -> List[Dict[str, Any]]:
        return [item.__dict__.copy() for item in self.bundle.evidence]
