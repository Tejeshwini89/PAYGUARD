from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .models import Event


def verify_razorpay_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """Verify Razorpay webhook signature against the raw request body."""
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _nested_entity(payload: Dict[str, Any], entity: str) -> Dict[str, Any]:
    try:
        return payload.get("payload", {}).get(entity, {}).get("entity", {}) or {}
    except AttributeError:
        return {}


def _first_entity(payload: Dict[str, Any], *names: str) -> Dict[str, Any]:
    for name in names:
        entity = _nested_entity(payload, name)
        if entity:
            return entity
    return {}


def razorpay_event_to_payguard_event(
    payload: Dict[str, Any],
    *,
    event_id: str,
    received_at: Optional[datetime] = None,
    signature_verified: bool = True,
) -> Event:
    event_type = str(payload.get("event", "unknown"))
    payment = _first_entity(payload, "payment")
    order = _first_entity(payload, "order")

    entity_id = payment.get("id") or order.get("id") or event_id
    transaction_id = payment.get("order_id") or order.get("id") or f"razorpay:{entity_id}"

    created_at = payload.get("created_at")
    if isinstance(created_at, (int, float)):
        occurred_at = datetime.fromtimestamp(created_at, tz=timezone.utc)
    else:
        occurred_at = received_at or datetime.now(timezone.utc)

    return Event(
        event_id=event_id,
        transaction_id=str(transaction_id),
        event_type=event_type,
        source="razorpay",
        entity_id=str(entity_id),
        occurred_at=occurred_at,
        received_at=received_at or datetime.now(timezone.utc),
        payload=payload,
        signature_verified=signature_verified,
    )


def build_webhook_event(raw_body: bytes, event_id: str, signature: str, secret: str, *, received_at: Optional[datetime] = None) -> Event:
    verified = verify_razorpay_signature(raw_body, signature, secret)
    payload = json.loads(raw_body.decode("utf-8"))
    return razorpay_event_to_payguard_event(
        payload,
        event_id=event_id,
        received_at=received_at,
        signature_verified=verified,
    )
