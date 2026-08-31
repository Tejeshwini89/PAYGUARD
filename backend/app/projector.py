from __future__ import annotations

from typing import Iterable, List

from .models import Event, TransactionState
from .normalizer import normalize_event_type, canonical_payload


class StateProjector:
    """Projects a transaction state from event-time-ordered canonical events."""

    def project(self, transaction_id: str, events: Iterable[Event]) -> TransactionState:
        ordered: List[Event] = sorted(events, key=lambda e: (e.occurred_at, e.received_at, e.event_id))
        state = TransactionState(transaction_id=transaction_id)
        seen = set()

        for event in ordered:
            if event.event_id in seen:
                continue
            seen.add(event.event_id)
            kind = normalize_event_type(event.event_type)
            p = canonical_payload(event.payload)

            if kind == "PAYMENT_CREATED":
                state.payment.status = "CREATED"
                state.payment.payment_id = p["payment_id"]
            elif kind == "PAYMENT_AUTHORIZED":
                state.payment.status = "AUTHORIZED"
                state.payment.payment_id = p["payment_id"] or state.payment.payment_id
            elif kind == "PAYMENT_CAPTURED":
                state.payment.status = "CAPTURED"
                state.payment.payment_id = p["payment_id"] or state.payment.payment_id
                state.payment.amount = p["amount"]
                state.payment.currency = p["currency"]
                state.payment.method = p["method"]
            elif kind == "PAYMENT_FAILED":
                state.payment.status = "FAILED"
            elif kind == "PAYMENT_REFUNDED":
                state.payment.status = "REFUNDED"

            elif kind == "ORDER_CREATED":
                state.order.status = "CREATED"
                state.order.order_id = p["order_id"]
                state.order.amount = p["amount"]
                state.order.currency = p["currency"]
            elif kind == "ORDER_ATTEMPTED":
                state.order.status = "ATTEMPTED"
            elif kind == "ORDER_PAID":
                state.order.status = "PAID"
                state.order.order_id = p["order_id"] or state.order.order_id

            elif kind == "INVENTORY_RESERVED":
                state.inventory.status = "RESERVED"
                state.inventory.product_id = p["product_id"]
                if p["available_quantity"] is not None:
                    state.inventory.available_quantity = p["available_quantity"]
                if p["reserved_quantity"] is not None:
                    state.inventory.reserved_quantity = p["reserved_quantity"]
            elif kind == "INVENTORY_RELEASED":
                state.inventory.status = "AVAILABLE"

            if p.get("fraud_signal"):
                state.add_risk_flag(str(p["fraud_signal"]).upper())

            elif kind == "FULFILLMENT_STARTED":
                state.fulfillment.status = "PROCESSING"
                state.fulfillment.attempt_count += 1
            elif kind == "FULFILLMENT_FAILED":
                state.fulfillment.status = "FAILED"
                state.fulfillment.last_error = p["error"]
                state.fulfillment.attempt_count += 1
            elif kind == "FULFILLMENT_COMPLETED":
                state.fulfillment.status = "COMPLETED"
                state.fulfillment.attempt_count += 1

            state.event_ids_applied.append(event.event_id)
            state.last_occurred_at = event.occurred_at

        return state
