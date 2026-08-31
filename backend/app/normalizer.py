from __future__ import annotations

from typing import Dict

CANONICAL_EVENT_TYPES = {
    "payment.created": "PAYMENT_CREATED",
    "payment.authorized": "PAYMENT_AUTHORIZED",
    "payment.captured": "PAYMENT_CAPTURED",
    "payment.failed": "PAYMENT_FAILED",
    "payment.refunded": "PAYMENT_REFUNDED",
    "order.created": "ORDER_CREATED",
    "order.attempted": "ORDER_ATTEMPTED",
    "order.paid": "ORDER_PAID",
    "inventory.reserved": "INVENTORY_RESERVED",
    "inventory.released": "INVENTORY_RELEASED",
    "fulfillment.started": "FULFILLMENT_STARTED",
    "fulfillment.failed": "FULFILLMENT_FAILED",
    "fulfillment.completed": "FULFILLMENT_COMPLETED",
}


def normalize_event_type(event_type: str) -> str:
    return CANONICAL_EVENT_TYPES.get(event_type, event_type.upper().replace(".", "_"))


def canonical_payload(raw: Dict) -> Dict:
    """Map source-specific payload fields into PAYGUARD's small canonical shape."""
    return {
        "payment_id": raw.get("payment_id") or raw.get("id"),
        "order_id": raw.get("order_id"),
        "amount": raw.get("amount"),
        "currency": raw.get("currency", "INR"),
        "method": raw.get("method"),
        "product_id": raw.get("product_id"),
        "available_quantity": raw.get("available_quantity"),
        "reserved_quantity": raw.get("reserved_quantity"),
        "error": raw.get("error"),
    }
