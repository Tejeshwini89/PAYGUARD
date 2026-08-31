from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from .models import Event

BASE = datetime(2026, 8, 25, 10, 0, tzinfo=timezone.utc)


def ev(event_id: str, tx: str, event_type: str, offset_s: int, received_offset_s: int, payload=None) -> Event:
    return Event(
        event_id=event_id,
        transaction_id=tx,
        event_type=event_type,
        source="simulator",
        entity_id=tx,
        occurred_at=BASE + timedelta(seconds=offset_s),
        received_at=BASE + timedelta(seconds=received_offset_s),
        payload=payload or {},
    )


def healthy() -> List[Event]:
    tx = "txn_healthy"
    return [
        ev("e1", tx, "order.created", 1, 1, {"order_id": "ord_1", "amount": 7499}),
        ev("e2", tx, "payment.captured", 2, 2, {"payment_id": "pay_1", "amount": 7499, "method": "upi"}),
        ev("e3", tx, "order.paid", 3, 3, {"order_id": "ord_1"}),
        ev("e4", tx, "inventory.reserved", 4, 4, {"product_id": "prod_1", "available_quantity": 10, "reserved_quantity": 1}),
        ev("e5", tx, "fulfillment.started", 5, 5),
        ev("e6", tx, "fulfillment.completed", 6, 6),
    ]


def orphaned_payment() -> List[Event]:
    tx = "txn_orphan"
    return [
        ev("o1", tx, "order.created", 1, 1, {"order_id": "ord_2", "amount": 7499}),
        ev("o2", tx, "payment.captured", 2, 2, {"payment_id": "pay_2", "amount": 7499, "method": "card"}),
    ]


def delayed_webhook() -> List[Event]:
    tx = "txn_delayed"
    return [
        ev("d1", tx, "order.created", 1, 1, {"order_id": "ord_3", "amount": 5000}),
        ev("d2", tx, "payment.captured", 2, 6, {"payment_id": "pay_3", "amount": 5000}),
        ev("d3", tx, "order.paid", 3, 4, {"order_id": "ord_3"}),
    ]


def duplicate_webhook() -> List[Event]:
    tx = "txn_duplicate_event"
    events = delayed_webhook()
    # Re-use a distinct arrival-time duplicate of the same external event.
    events.append(ev("d3", tx, "order.paid", 3, 10, {"order_id": "ord_3"}))
    return events


def fulfillment_failure() -> List[Event]:
    tx = "txn_fulfillment_failure"
    return [
        ev("f1", tx, "order.created", 1, 1, {"order_id": "ord_4", "amount": 12999}),
        ev("f2", tx, "payment.captured", 2, 2, {"payment_id": "pay_4", "amount": 12999}),
        ev("f3", tx, "order.paid", 3, 3, {"order_id": "ord_4"}),
        ev("f4", tx, "inventory.reserved", 4, 4, {"product_id": "prod_4", "available_quantity": 3, "reserved_quantity": 1}),
        ev("f5", tx, "fulfillment.failed", 5, 5, {"error": "carrier_timeout"}),
    ]


def orphaned_payment_inventory_available() -> List[Event]:
    tx = "txn_orphan_recoverable"
    return [
        ev("oa1", tx, "order.created", 1, 1, {"order_id": "ord_5", "amount": 7499}),
        ev("oa2", tx, "payment.captured", 2, 2, {"payment_id": "pay_5", "amount": 7499, "method": "upi"}),
        ev("oa3", tx, "inventory.released", 3, 3, {"product_id": "prod_5", "available_quantity": 8, "reserved_quantity": 0}),
    ]


def dangerous_orphan() -> List[Event]:
    tx = "txn_dangerous_orphan"
    return [
        ev("dg1", tx, "order.created", 1, 1, {"order_id": "ord_danger", "amount": 17999}),
        ev("dg2", tx, "payment.captured", 2, 2, {"payment_id": "pay_danger", "amount": 17999, "method": "card"}),
        ev("dg3", tx, "inventory.released", 3, 3, {"product_id": "prod_danger", "available_quantity": 0, "reserved_quantity": 0, "fraud_signal": "HIGH"}),
    ]
