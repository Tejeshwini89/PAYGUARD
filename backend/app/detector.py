from __future__ import annotations

from typing import List

from .models import Event, Incident, TransactionState


class IncidentDetector:
    def detect(self, state: TransactionState, events: List[Event] | None = None) -> List[Incident]:
        incidents: List[Incident] = []
        amount = state.payment.amount or state.order.amount or 0

        # Merchant-side orphan: gateway/payment state is good, downstream order state is not.
        if state.payment.status == "CAPTURED" and state.order.status in {"UNKNOWN", "CREATED", "ATTEMPTED"}:
            inventory_blocked = state.inventory.status == "SOLD_OUT"
            incidents.append(
                Incident(
                    incident_type="ORPHANED_PAYMENT",
                    transaction_id=state.transaction_id,
                    severity="CRITICAL" if inventory_blocked else "HIGH",
                    expected_state={"payment": "CAPTURED", "order": "PAID"},
                    observed_state={"payment": state.payment.status, "order": state.order.status},
                    revenue_at_risk=amount,
                    reason=(
                        "Payment is captured but downstream order confirmation is incomplete and inventory is unavailable."
                        if inventory_blocked else
                        "Payment is captured but downstream order confirmation is incomplete."
                    ),
                    confidence=0.99 if inventory_blocked else 0.96,
                )
            )

        if state.payment.status == "CAPTURED" and state.order.status == "PAID" and state.fulfillment.status == "FAILED":
            incidents.append(
                Incident(
                    incident_type="FULFILLMENT_FAILURE",
                    transaction_id=state.transaction_id,
                    severity="HIGH",
                    expected_state={"fulfillment": "COMPLETED"},
                    observed_state={"fulfillment": state.fulfillment.status},
                    revenue_at_risk=amount,
                    reason="Paid order has a failed fulfillment state.",
                    confidence=0.98,
                )
            )

        if events:
            captured = [e for e in events if e.event_type == "payment.captured"]
            payment_ids = [e.payload.get("payment_id") for e in captured if e.payload.get("payment_id")]
            if len(set(payment_ids)) > 1:
                amount = state.payment.amount or state.order.amount or 0
                incidents.append(
                    Incident(
                        incident_type="DUPLICATE_PAYMENT",
                        transaction_id=state.transaction_id,
                        severity="CRITICAL",
                        expected_state={"payments": "ONE_CAPTURED"},
                        observed_state={"payments": f"{len(set(payment_ids))}_CAPTURED"},
                        revenue_at_risk=amount,
                        reason="Multiple distinct captured payment IDs exist for one transaction.",
                        confidence=0.99,
                    )
                )

        return incidents
